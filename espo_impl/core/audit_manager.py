"""CRM audit manager — reverse-engineers a live CRM into YAML program files.

Connects to a source EspoCRM instance, discovers its configuration
(entities, fields, layouts, relationships), and produces YAML program
files in the same schema the configure engine consumes.
"""

import json
import logging
import sqlite3
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.audit_utils import (
    EntityClass,
    FieldClass,
    classify_entity,
    classify_field,
    get_yaml_entity_name,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)
from espo_impl.core.condition_expression import (
    OPERATORS,
    AllNode,
    AnyNode,
    ConditionNode,
    LeafClause,
    render_condition,
)
from espo_impl.core.layout_types import (
    PANEL_MAP_LAYOUTS,
    LayoutClass,
    structure_class,
)
from espo_impl.core.models import ScopeAccess, SystemPermissions

logger = logging.getLogger(__name__)

# Callback signature: (message: str, color: str) -> None
ProgressCallback = Callable[[str, str], None]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AuditOptions:
    """Options controlling what the audit captures.

    :param include_custom_fields: Include custom fields on entities.
    :param include_native_custom_fields: Include custom fields on native entities.
    :param include_detail_layouts: Capture detail layouts.
    :param include_list_layouts: Capture list layouts.
    :param include_edit_layout: Capture the edit layout (when separately
        defined; EspoCRM derives it from detail otherwise).
    :param include_small_layouts: Capture detailSmall / listSmall layouts.
    :param include_detail_convert: Capture the detailConvert (lead-convert)
        layout.
    :param include_kanban: Capture the kanban layout.
    :param include_search_massupdate: Capture the filters (search) and
        massUpdate layouts.
    :param include_relationships_layout: Capture the ``relationships`` layout
        (relationship-panel ordering) — distinct from ``include_relationships``
        which discovers relationship edges.
    :param include_side_bottom_panels: Capture the side/bottom relationship
        panel placement layouts.
    :param include_relationships: Discover relationships.
    :param include_native_fields: Include native fields (normally excluded).
    :param include_security: Discover roles and teams (DEC-180).
    :param include_filtered_tabs: Discover filtered tabs (DEC-180).
    :param include_data_profile: Run the pass-2 data profiler after
        schema discovery, writing ``utilization-profile.json`` to the
        output directory (WTK-096). Default on, matching the DEC-180
        precedent that the audit's identity is full-configuration
        capture. Pass-2 failure is non-fatal to pass 1's output.
    :param selected_entities: Optional set of EspoCRM wire-name entities
        (e.g. ``{"Contact", "CEngagement"}``) to restrict the audit to.
        ``None`` means audit every discovered entity (existing behavior);
        a non-None set filters discovery to that subset post-
        classification. Per DEC-181.
    """

    include_custom_fields: bool = True
    include_native_custom_fields: bool = True
    include_detail_layouts: bool = True
    include_list_layouts: bool = True
    include_edit_layout: bool = True
    include_small_layouts: bool = True
    include_detail_convert: bool = True
    include_kanban: bool = True
    include_search_massupdate: bool = True
    include_relationships_layout: bool = True
    include_side_bottom_panels: bool = True
    include_relationships: bool = True
    include_native_fields: bool = False
    include_security: bool = True
    include_filtered_tabs: bool = True
    include_data_profile: bool = True
    selected_entities: set[str] | None = None


@dataclass
class FieldAuditResult:
    """Result of auditing a single field."""

    yaml_name: str
    api_name: str
    field_type: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class LayoutAuditResult:
    """Result of auditing a layout.

    ``data`` is the value emitted under the layout type in YAML: a
    ``{"panels": [...]}`` / ``{"columns": [...]}`` dict for PANELS/COLUMNS,
    a bare ``list[str]`` for FIELD_LIST, or the ``{name: cfg}`` dict for
    PANEL_MAP.
    """

    layout_type: str
    data: Any = field(default_factory=dict)


@dataclass
class RelationshipAuditResult:
    """Result of auditing a single relationship."""

    name: str
    entity: str
    entity_foreign: str
    link_type: str
    link: str
    link_foreign: str
    label: str
    label_foreign: str
    relation_name: str | None = None
    audited: bool = False
    audited_foreign: bool = False


@dataclass
class EntityAuditResult:
    """Result of auditing a single entity."""

    yaml_name: str
    espo_name: str
    entity_class: EntityClass
    entity_type: str | None = None
    label_singular: str | None = None
    label_plural: str | None = None
    stream: bool = False
    fields: list[FieldAuditResult] = field(default_factory=list)
    layouts: list[LayoutAuditResult] = field(default_factory=list)
    filtered_tabs: list["FilteredTabAuditResult"] = field(default_factory=list)


@dataclass
class RoleAuditResult:
    """Result of auditing a single role.

    Captures only the surface the v1.3 schema defines and Prompt D
    deploys. Fields the schema doesn't carry (e.g., the three
    EspoCRM-only permissions per DEC-2) are not captured.

    :param name: Role identity (server-assigned name).
    :param description: Role description text (None if not set).
    :param persona: Always None on capture — the source instance
        doesn't carry persona metadata (it's documentation in YAML
        only per DEC-178). Operators reattach personas manually
        when curating audited YAML.
    :param scope_access: Per-entity access scope, keyed by natural
        entity name (Engagement, Contact, etc.).
    :param system_permissions: The five schema-managed system
        permissions per Section 12.4. None when none of the five
        managed columns are present on the source record.
    """

    name: str
    description: str | None = None
    persona: str | None = None
    scope_access: dict[str, ScopeAccess] = field(default_factory=dict)
    system_permissions: SystemPermissions | None = None


@dataclass
class TeamAuditResult:
    """Result of auditing a single team."""

    name: str
    description: str | None = None


@dataclass
class FilteredTabAuditResult:
    """Result of auditing a single filtered tab.

    Mirrors the YAML-side :class:`espo_impl.core.models.FilteredTab`
    shape. The filter AST is captured in parsed form so YAML emission
    can render it canonically via :func:`render_condition`.

    :param id: Stable identifier (derived from the scope name, lower-
        camelCased — ``MyEngagements`` → ``myEngagements``).
    :param scope: PascalCase scope name from EspoCRM metadata
        (e.g., ``MyEngagements``).
    :param label: Human-readable label, from i18n
        ``Global.scopeNames`` when present, falling back to the Report
        Filter's ``name`` and finally to the scope name.
    :param filter: Parsed condition AST recovered from the Report
        Filter's ``data.where``. ``None`` when the filter contained
        an unknown where-item type (audit warning emitted; the
        operator hand-writes the missing filter post-import).
    :param nav_order: Ordinal position if recoverable from tabList
        metadata; ``None`` otherwise (the deploy half also treats this
        as optional).
    :param acl: ACL strategy from ``scopes/<Scope>.json``; defaults to
        ``"boolean"`` matching the deploy-side default.
    """

    id: str
    scope: str
    label: str
    filter: ConditionNode | None = None
    nav_order: int | None = None
    acl: str = "boolean"


@dataclass
class AuditReport:
    """Aggregate results of a full audit."""

    source_url: str
    source_name: str
    timestamp: str
    output_dir: str
    entities: list[EntityAuditResult] = field(default_factory=list)
    relationships: list[RelationshipAuditResult] = field(default_factory=list)
    roles: list[RoleAuditResult] = field(default_factory=list)
    teams: list[TeamAuditResult] = field(default_factory=list)
    files_written: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest serialization (WTK-090 §2.1)
# ---------------------------------------------------------------------------

MANIFEST_VERSION = 1
MANIFEST_FILENAME = "audit-report.json"


def write_manifest(report: AuditReport, output_dir: Path) -> Path:
    """Serialize ``report`` to ``audit-report.json`` in ``output_dir``.

    The manifest is the seam the V2 deposit transform consumes
    (``crmbuilder-v2-deposit-audit``): a ``dataclasses.asdict`` of the
    report tree plus ``manifest_version``, with enums serialized as
    their ``.value`` strings and each filtered tab's parsed filter AST
    rendered to the canonical structured form (``{all: [...]}``) or
    ``null`` when the audit could not recover it.
    """
    manifest = asdict(report)
    manifest["manifest_version"] = MANIFEST_VERSION
    # asdict recurses into the ConditionNode dataclasses; replace each
    # filtered tab's filter with its render_condition structured form,
    # which is what the transform (and the deploy-side YAML) read.
    for entity, entity_dict in zip(
        report.entities, manifest["entities"], strict=True
    ):
        for tab, tab_dict in zip(
            entity.filtered_tabs,
            entity_dict.get("filtered_tabs") or [],
            strict=False,
        ):
            tab_dict["filter"] = (
                render_condition(tab.filter) if tab.filter is not None else None
            )

    def _default(obj: Any) -> Any:
        value = getattr(obj, "value", None)
        if value is not None:  # Enum members
            return value
        raise TypeError(f"not JSON serializable: {type(obj).__name__}")

    path = Path(output_dir) / MANIFEST_FILENAME
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(manifest, indent=2, default=_default) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------

def _yaml_str_representer(dumper: yaml.Dumper, data: str) -> yaml.Node:
    """Use literal block style for multi-line strings."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _yaml_none_representer(dumper: yaml.Dumper, _data: None) -> yaml.Node:
    """Represent None as empty string (tilde-free)."""
    return dumper.represent_scalar("tag:yaml.org,2002:null", "null")


def _make_dumper() -> type[yaml.Dumper]:
    """Create a YAML dumper with custom representers."""
    dumper = yaml.Dumper
    dumper.add_representer(str, _yaml_str_representer)
    dumper.add_representer(type(None), _yaml_none_representer)
    return dumper


# ---------------------------------------------------------------------------
# Link type mapping
# ---------------------------------------------------------------------------

# EspoCRM metadata link type → YAML linkType
_LINK_TYPE_MAP: dict[str, str] = {
    "hasMany": "oneToMany",
    "hasOne": "oneToMany",
    "belongsTo": "manyToOne",
    "belongsToParent": "manyToOne",
}


def _resolve_link_type(
    link_meta: dict[str, Any], foreign_link_meta: dict[str, Any] | None
) -> str | None:
    """Determine the YAML linkType from EspoCRM link metadata.

    :param link_meta: Link metadata for the primary side.
    :param foreign_link_meta: Link metadata for the foreign side, if available.
    :returns: YAML linkType string, or None if unresolvable.
    """
    meta_type = link_meta.get("type", "")

    # manyToMany: indicated by relationName in the metadata
    if link_meta.get("relationName"):
        return "manyToMany"

    if meta_type == "hasMany":
        # Could be oneToMany or manyToMany — check foreign side
        if foreign_link_meta and foreign_link_meta.get("relationName"):
            return "manyToMany"
        return "oneToMany"

    if meta_type == "belongsTo":
        return "manyToOne"

    if meta_type == "hasOne":
        return "oneToMany"

    return _LINK_TYPE_MAP.get(meta_type)


# ---------------------------------------------------------------------------
# AuditManager
# ---------------------------------------------------------------------------

class AuditManager:
    """Orchestrates a full CRM audit.

    :param client: EspoAdminClient connected to the source instance.
    :param options: Audit options controlling scope.
    :param callback: Progress callback for UI updates.
    """

    def __init__(
        self,
        client: EspoAdminClient,
        options: AuditOptions | None = None,
        callback: ProgressCallback | None = None,
    ) -> None:
        self._client = client
        self._options = options or AuditOptions()
        self._cb = callback or (lambda msg, color: None)
        self._custom_field_names: dict[str, set[str]] = {}
        # i18n payload (full /I18n tree) fetched lazily and reused across
        # all label lookups during an audit. EspoCRM stores entity, field,
        # and link display labels here — entityDefs has none of them. See
        # `_ensure_i18n` for the fetch and `_field_label`/`_link_label`/
        # `_scope_labels` for the lookups.
        self._i18n: dict[str, Any] = {}
        self._i18n_fetched: bool = False

    # ------------------------------------------------------------------
    # i18n label lookups
    # ------------------------------------------------------------------

    def _ensure_i18n(self) -> None:
        """Fetch the i18n tree once per audit run.

        Logs a yellow warning on failure but doesn't abort — every
        lookup falls back to a yaml-derived name.
        """
        if self._i18n_fetched:
            return
        self._i18n_fetched = True
        status, body = self._client.get_i18n()
        if status == 200 and isinstance(body, dict):
            self._i18n = body
        else:
            self._cb(
                f"[AUDIT]    WARNING: failed to fetch i18n labels "
                f"(HTTP {status}); falling back to internal names",
                "yellow",
            )

    def _scope_labels(self, scope: str) -> tuple[str | None, str | None]:
        """Look up an entity's singular/plural display labels.

        :param scope: Internal scope name (e.g. ``CEngagement``, ``Contact``).
        :returns: (singular, plural) — either may be None if absent.
        """
        self._ensure_i18n()
        global_block = self._i18n.get("Global")
        if not isinstance(global_block, dict):
            return None, None
        sn = global_block.get("scopeNames", {})
        snp = global_block.get("scopeNamesPlural", {})
        singular = sn.get(scope) if isinstance(sn, dict) else None
        plural = snp.get(scope) if isinstance(snp, dict) else None
        return singular, plural

    def _field_label(self, scope: str, field_name: str, fallback: str) -> str:
        """Look up a field's display label with entity → Global fallback.

        :param scope: Internal entity scope (e.g. ``CMentorProfile``).
        :param field_name: API field name (e.g. ``cMentorStatus``).
        :param fallback: Value to return if no label is found.
        """
        return self._i18n_lookup(scope, "fields", field_name, fallback)

    def _link_label(self, scope: str, link_name: str, fallback: str) -> str:
        """Look up a link's display label with entity → Global fallback."""
        return self._i18n_lookup(scope, "links", link_name, fallback)

    def _i18n_lookup(
        self, scope: str, category: str, key: str, fallback: str
    ) -> str:
        """Look up ``i18n[scope][category][key]`` then ``i18n.Global[category][key]``."""
        self._ensure_i18n()
        entity_block = self._i18n.get(scope)
        if isinstance(entity_block, dict):
            cat = entity_block.get(category)
            if isinstance(cat, dict):
                value = cat.get(key)
                if value:
                    return value
        global_block = self._i18n.get("Global")
        if isinstance(global_block, dict):
            cat = global_block.get(category)
            if isinstance(cat, dict):
                value = cat.get(key)
                if value:
                    return value
        return fallback

    def run_audit(
        self,
        output_dir: Path,
        db_conn: sqlite3.Connection | None = None,
        instance_id: int | None = None,
    ) -> AuditReport:
        """Execute the full audit and write YAML files.

        :param output_dir: Directory to write YAML files into.
        :param db_conn: Optional client DB connection for record insertion.
        :param instance_id: Optional Instance table row ID for ConfigurationRun.
        :returns: AuditReport with results.
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        report = AuditReport(
            source_url=self._client.profile.url,
            source_name=self._client.profile.name,
            timestamp=timestamp,
            output_dir=str(output_dir),
        )

        # Step 1: Discover entities
        self._cb("[AUDIT]    Discovering entities ...", "cyan")
        entities = self._discover_entities(report)

        if entities:
            custom_count = sum(
                1 for e in entities if e.entity_class == EntityClass.CUSTOM
            )
            native_count = sum(
                1 for e in entities if e.entity_class == EntityClass.NATIVE
            )
            self._cb(
                f"[AUDIT]    Found {custom_count} custom entities, "
                f"{native_count} native entities with custom fields",
                "cyan",
            )
        else:
            self._cb("[AUDIT]    No auditable entities found.", "yellow")

        # Step 2: Extract fields and layouts per entity
        for i, entity in enumerate(entities, 1):
            self._cb(
                f"[AUDIT]    {entity.yaml_name} — extracting fields "
                f"({i} of {len(entities)}) ...",
                "white",
            )
            self._extract_fields(entity, report)

            for layout_type in self._layout_types_to_extract():
                self._extract_layout(entity, layout_type, report)

        # Step 3: Discover relationships
        relationships: list[RelationshipAuditResult] = []
        if self._options.include_relationships and entities:
            self._cb("[AUDIT]    Discovering relationships ...", "cyan")
            relationships = self._discover_relationships(entities, report)
            self._cb(
                f"[AUDIT]    Found {len(relationships)} relationships",
                "cyan",
            )

        # Step 3.4: Discover filtered tabs per DEC-180
        if self._options.include_filtered_tabs and entities:
            self._cb("[AUDIT]    Discovering filtered tabs ...", "cyan")
            self._discover_filtered_tabs(entities, report)
            total_tabs = sum(len(e.filtered_tabs) for e in entities)
            entity_count = sum(1 for e in entities if e.filtered_tabs)
            self._cb(
                f"[AUDIT]    Found {total_tabs} filtered tabs across "
                f"{entity_count} entities",
                "cyan",
            )

        # Step 3.5: Discover security (teams + roles) per DEC-180
        teams: list[TeamAuditResult] = []
        roles: list[RoleAuditResult] = []
        if self._options.include_security:
            self._cb("[AUDIT]    Discovering teams ...", "cyan")
            teams = self._discover_teams(report)
            self._cb(
                f"[AUDIT]    Found {len(teams)} teams",
                "cyan",
            )
            self._cb("[AUDIT]    Discovering roles ...", "cyan")
            roles = self._discover_roles(report)
            self._cb(
                f"[AUDIT]    Found {len(roles)} roles",
                "cyan",
            )
            # Per DEC-6: §12.5 role-aware visibility is NOT_AUDITABLE on
            # EspoCRM 9.x. Dynamic Logic JSON has no role-condition type;
            # Layout Sets bind to Teams rather than Roles. Manually-
            # configured role-aware visibility on the target instance is
            # not round-tripped by this audit.
            self._cb(
                "[AUDIT]    NOTE: Section 12.5 role-aware visibility is "
                "NOT_AUDITABLE on EspoCRM 9.x (DEC-6). Any manually-"
                "configured role-aware visibility on the target is "
                "not captured by this audit.",
                "yellow",
            )

        report.entities = entities
        report.relationships = relationships
        report.teams = teams
        report.roles = roles

        # Step 4: Write YAML files
        self._cb(
            f"[AUDIT]    Writing YAML files to {output_dir.name}/ ...",
            "cyan",
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        files_written = self._write_yaml_files(entities, relationships, output_dir, report)
        report.files_written = files_written

        # Step 4.5: Data-profiling pass (pass 2, WTK-096) — consumes
        # the just-assembled report as its work-list and writes
        # utilization-profile.json beside the YAML output. Failure is
        # non-fatal to pass 1's output (WTK-096 §2.2).
        if self._options.include_data_profile and entities:
            self._cb("[AUDIT]    Profiling record data (pass 2) ...", "cyan")
            try:
                from espo_impl.core.data_profiler import DataProfiler
                profiler = DataProfiler(
                    self._client, report, callback=self._cb,
                )
                profile = profiler.run()
                report.warnings.extend(profile.warning_lines())
                profile_path = profile.write(output_dir)
                if profile_path is not None:
                    entity_count = len(profile.data.get("entities", {}))
                    self._cb(
                        f"[AUDIT]    Utilization profile written for "
                        f"{entity_count} entities → {profile_path.name}",
                        "green" if not profile.aborted else "yellow",
                    )
                else:
                    self._cb(
                        "[AUDIT]    WARNING: data profiling aborted before "
                        "any entity completed — no profile written",
                        "yellow",
                    )
            except Exception as exc:
                msg = f"Data profiling failed: {exc}"
                report.warnings.append(msg)
                self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")

        # Step 4.6: Manifest serialization (WTK-090 §2.1) — the seam the
        # V2 deposit transform consumes. Failure is non-fatal to the
        # YAML output already written.
        try:
            manifest_path = write_manifest(report, output_dir)
            self._cb(
                f"[AUDIT]    Manifest written → {manifest_path.name}",
                "green",
            )
        except Exception as exc:
            msg = f"Manifest serialization failed: {exc}"
            report.warnings.append(msg)
            self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")

        # Step 5: Insert database records
        db_records = 0
        if db_conn is not None:
            self._cb("[AUDIT]    Inserting database records ...", "cyan")
            try:
                from espo_impl.core.audit_db import insert_audit_records
                db_records = insert_audit_records(db_conn, report, instance_id)
                self._cb(
                    f"[AUDIT]    {db_records} database records inserted.",
                    "white",
                )
            except Exception as exc:
                msg = f"Database insertion failed: {exc}"
                report.errors.append(msg)
                self._cb(f"[AUDIT]    ERROR: {msg}", "red")

        self._cb(
            f"[AUDIT]    Audit complete — {files_written} files written, "
            f"{db_records} DB records.",
            "green",
        )
        return report

    # ------------------------------------------------------------------
    # Entity discovery
    # ------------------------------------------------------------------

    def _discover_entities(
        self, report: AuditReport
    ) -> list[EntityAuditResult]:
        """Query all scopes and classify entities.

        :param report: Report to append errors/warnings to.
        :returns: List of auditable entity results.
        """
        status, scopes = self._client.get_all_scopes()
        if status != 200 or not isinstance(scopes, dict):
            msg = f"Failed to fetch scopes (HTTP {status})"
            report.errors.append(msg)
            self._cb(f"[AUDIT]    ERROR: {msg}", "red")
            return []

        # Warm the i18n cache so the entity/field/link label lookups in
        # this method and the field/relationship extractors that run later
        # all share a single /I18n fetch. EspoCRM does NOT store
        # labelSingular/labelPlural in entityDefs — labels POSTed at create
        # time land in i18n under Global.scopeNames / scopeNamesPlural.
        self._ensure_i18n()

        results: list[EntityAuditResult] = []
        for scope_name, scope_meta in scopes.items():
            if not isinstance(scope_meta, dict):
                continue

            entity_class = classify_entity(scope_name, scope_meta)

            if entity_class == EntityClass.SYSTEM:
                continue

            if entity_class == EntityClass.NATIVE and not self._options.include_native_custom_fields:
                continue

            # Per DEC-181: operator may restrict the audit to a subset
            # of entities chosen in the UI picker. Filter is applied
            # post-classification so the entity-type rules above still
            # gate the picker's selections (e.g., a SYSTEM scope the
            # operator somehow named is still skipped).
            if (
                self._options.selected_entities is not None
                and scope_name not in self._options.selected_entities
            ):
                continue

            yaml_name = get_yaml_entity_name(scope_name)
            entity_type = scope_meta.get("type")

            singular, plural = self._scope_labels(scope_name)
            label_singular = singular or yaml_name
            label_plural = plural or f"{yaml_name}s"

            results.append(EntityAuditResult(
                yaml_name=yaml_name,
                espo_name=scope_name,
                entity_class=entity_class,
                entity_type=entity_type,
                label_singular=label_singular,
                label_plural=label_plural,
                stream=scope_meta.get("stream", False),
            ))

        return results

    # ------------------------------------------------------------------
    # Field extraction
    # ------------------------------------------------------------------

    def _extract_fields(
        self, entity: EntityAuditResult, report: AuditReport
    ) -> None:
        """Fetch and classify fields for an entity.

        :param entity: Entity to extract fields for.
        :param report: Report to append errors/warnings to.
        """
        status, fields_meta = self._client.get_entity_field_list(entity.espo_name)
        if status != 200 or not isinstance(fields_meta, dict):
            msg = f"{entity.yaml_name}: failed to fetch fields (HTTP {status})"
            report.warnings.append(msg)
            self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")
            return

        custom_names: set[str] = set()

        for api_name, meta in fields_meta.items():
            if not isinstance(meta, dict):
                continue

            field_class = classify_field(api_name, meta, entity.entity_type)

            if field_class == FieldClass.SYSTEM:
                continue

            if field_class == FieldClass.NATIVE and not self._options.include_native_fields:
                continue

            if field_class == FieldClass.CUSTOM:
                yaml_name = strip_field_c_prefix(api_name)
                custom_names.add(api_name)
            else:
                yaml_name = api_name

            field_type = meta.get("type", "varchar")
            # Field labels live in i18n, not entityDefs (which has no
            # `label` key at all on this server). Look up
            # `i18n[Entity].fields[apiName]` first so per-entity overrides
            # win, falling back to `i18n.Global.fields[apiName]` for
            # native fields like firstName/lastName, then to yaml_name as
            # a final cosmetic fallback.
            label = self._field_label(entity.espo_name, api_name, yaml_name)

            # Build properties dict with non-None values
            props: dict[str, Any] = {}
            if meta.get("required"):
                props["required"] = True
            if meta.get("default") is not None:
                props["default"] = meta["default"]
            if meta.get("readOnly"):
                props["readOnly"] = True
            if meta.get("audited"):
                props["audited"] = True
            if meta.get("copyToClipboard"):
                props["copyToClipboard"] = True

            # Enum/multiEnum properties
            if field_type in ("enum", "multiEnum"):
                options = meta.get("options")
                if options:
                    props["options"] = options
                translated = meta.get("translatedOptions")
                if translated and translated != dict(
                    zip(options or [], options or [], strict=True)
                ):
                    props["translatedOptions"] = translated
                style = meta.get("style")
                if style:
                    # Filter out default/empty styles
                    filtered = {k: v for k, v in style.items() if v and v != "default"}
                    if filtered:
                        props["style"] = filtered
                if meta.get("isSorted"):
                    props["isSorted"] = True
                if meta.get("displayAsLabel"):
                    props["displayAsLabel"] = True

            # Numeric properties
            if meta.get("min") is not None:
                props["min"] = meta["min"]
            if meta.get("max") is not None:
                props["max"] = meta["max"]

            # Varchar properties
            if meta.get("maxLength") is not None:
                props["maxLength"] = meta["maxLength"]

            # Foreign field — mirrors a scalar from a linked entity
            # (Section 6.8 / REQ-121 / PI-169). Capture the link it reads
            # through and the linked-entity field it mirrors so the field
            # re-deploys. Values are emitted verbatim: the deploy side
            # re-applies the c-prefix on the relationship the link points
            # at, so a verbatim reference stays consistent across the
            # round-trip. Foreign fields are read-only mirrors, so any
            # stray ``required`` flag is dropped — the deploy validator
            # rejects ``required: true`` on a foreign field.
            if field_type == "foreign":
                props.pop("required", None)
                link = meta.get("link")
                foreign_field = meta.get("field")
                if link:
                    props["link"] = link
                if foreign_field:
                    props["field"] = foreign_field
                if not link or not foreign_field:
                    msg = (
                        f"{entity.yaml_name}.{yaml_name}: foreign field is "
                        f"missing link/field in metadata; emitted YAML will "
                        f"need manual completion before re-deploy"
                    )
                    report.warnings.append(msg)
                    self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")

            entity.fields.append(FieldAuditResult(
                yaml_name=yaml_name,
                api_name=api_name,
                field_type=field_type,
                label=label,
                properties=props,
            ))

        self._custom_field_names[entity.espo_name] = custom_names

        field_count = len(entity.fields)
        self._cb(
            f"[AUDIT]    {entity.yaml_name} — {field_count} fields extracted",
            "white",
        )

    # ------------------------------------------------------------------
    # Layout extraction
    # ------------------------------------------------------------------

    def _layout_types_to_extract(self) -> list[str]:
        """Build the ordered list of layout types to audit per the options.

        :returns: Layout type names, in a stable order.
        """
        o = self._options
        plan: list[str] = []
        if o.include_detail_layouts:
            plan.append("detail")
        if o.include_edit_layout:
            plan.append("edit")
        if o.include_detail_convert:
            plan.append("detailConvert")
        if o.include_small_layouts:
            plan.append("detailSmall")
        if o.include_list_layouts:
            plan.append("list")
        if o.include_small_layouts:
            plan.append("listSmall")
        if o.include_kanban:
            plan.append("kanban")
        if o.include_search_massupdate:
            plan.extend(("filters", "massUpdate"))
        if o.include_relationships_layout:
            plan.append("relationships")
        if o.include_side_bottom_panels:
            plan.extend(sorted(PANEL_MAP_LAYOUTS))
        return plan

    def _extract_layout(
        self,
        entity: EntityAuditResult,
        layout_type: str,
        report: AuditReport,
    ) -> None:
        """Fetch and reverse-map a layout for an entity.

        Dispatches by the type's structure class. An empty / ``false``
        response means the layout is not separately defined (e.g. ``edit``
        derives from ``detail``) and is skipped silently.

        :param entity: Entity to extract layout for.
        :param layout_type: Any recognized EspoCRM layout type.
        :param report: Report to append errors/warnings to.
        """
        status, layout_data = self._client.get_layout(
            entity.espo_name, layout_type
        )
        if status != 200:
            msg = (
                f"{entity.yaml_name}: failed to fetch {layout_type} "
                f"layout (HTTP {status})"
            )
            report.warnings.append(msg)
            self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")
            return
        # Empty / derived layout (false, [], {}, null) — nothing to capture.
        if not layout_data:
            return

        custom_names = self._custom_field_names.get(entity.espo_name, set())
        cls = structure_class(layout_type)

        if cls is LayoutClass.COLUMNS:
            columns = self._reverse_list_layout(layout_data, custom_names)
            if columns:
                entity.layouts.append(LayoutAuditResult(
                    layout_type=layout_type,
                    data={"columns": columns},
                ))
                self._cb(
                    f"[AUDIT]    {entity.yaml_name} — {layout_type} layout "
                    f"({len(columns)} columns)",
                    "white",
                )
        elif cls is LayoutClass.PANELS:
            panels = self._reverse_detail_layout(layout_data, custom_names)
            if panels:
                total_rows = sum(len(p.get("rows", [])) for p in panels)
                entity.layouts.append(LayoutAuditResult(
                    layout_type=layout_type,
                    data={"panels": panels},
                ))
                self._cb(
                    f"[AUDIT]    {entity.yaml_name} — {layout_type} layout "
                    f"({len(panels)} panels, {total_rows} rows)",
                    "white",
                )
        elif cls is LayoutClass.FIELD_LIST:
            names = self._reverse_field_list_layout(layout_data, custom_names)
            if names:
                entity.layouts.append(LayoutAuditResult(
                    layout_type=layout_type,
                    data=names,
                ))
                self._cb(
                    f"[AUDIT]    {entity.yaml_name} — {layout_type} layout "
                    f"({len(names)} names)",
                    "white",
                )
        elif cls is LayoutClass.PANEL_MAP:
            mapping = self._reverse_panel_map_layout(layout_data)
            if mapping:
                entity.layouts.append(LayoutAuditResult(
                    layout_type=layout_type,
                    data=mapping,
                ))
                self._cb(
                    f"[AUDIT]    {entity.yaml_name} — {layout_type} layout "
                    f"({len(mapping)} panels)",
                    "white",
                )

    def _reverse_field_name(self, api_name: str, custom_names: set[str]) -> str:
        """Reverse a field name from API format to YAML format.

        :param api_name: Field name from the API.
        :param custom_names: Set of known custom field API names.
        :returns: YAML natural field name.
        """
        if api_name in custom_names:
            return strip_field_c_prefix(api_name)
        return api_name

    def _reverse_detail_layout(
        self, layout_data: Any, custom_names: set[str]
    ) -> list[dict[str, Any]]:
        """Reverse-map a detail layout from API format to YAML format.

        :param layout_data: Raw layout data from the API.
        :param custom_names: Set of custom field API names for this entity.
        :returns: List of panel dicts in YAML format.
        """
        if not isinstance(layout_data, list):
            return []

        panels: list[dict[str, Any]] = []
        for panel_data in layout_data:
            if not isinstance(panel_data, dict):
                continue

            panel: dict[str, Any] = {}

            label = panel_data.get("customLabel") or panel_data.get("label", "")
            if label:
                panel["label"] = label

            if panel_data.get("tabBreak"):
                panel["tabBreak"] = True
            tab_label = panel_data.get("tabLabel")
            if tab_label:
                panel["tabLabel"] = tab_label

            style = panel_data.get("style", "default")
            if style and style != "default":
                panel["style"] = style

            if panel_data.get("hidden"):
                panel["hidden"] = True

            # Dynamic logic
            dlv = panel_data.get("dynamicLogicVisible")
            if dlv:
                panel["dynamicLogicVisible"] = self._reverse_dynamic_logic(
                    dlv, custom_names
                )

            # Rows
            raw_rows = panel_data.get("rows", [])
            if isinstance(raw_rows, list):
                rows: list[list[Any]] = []
                for raw_row in raw_rows:
                    if not isinstance(raw_row, list):
                        continue
                    row: list[Any] = []
                    for cell in raw_row:
                        row.append(
                            self._reverse_cell(cell, custom_names)
                        )
                    rows.append(row)
                if rows:
                    panel["rows"] = rows

            # Preserve any other panel keys (noteText, noteStyle,
            # dynamicLogicStyled, …) verbatim for lossless round-trip. The
            # loader stores them in PanelSpec.attrs and the builder re-emits.
            handled = {
                "customLabel", "label", "tabBreak", "tabLabel", "style",
                "hidden", "dynamicLogicVisible", "rows", "tabs",
            }
            for key, val in panel_data.items():
                if key not in handled:
                    panel[key] = val

            panels.append(panel)

        return panels

    def _reverse_cell(self, cell: Any, custom_names: set[str]) -> Any:
        """Reverse one detail-layout cell to YAML form.

        A plain ``{"name": field}`` cell collapses to the bare field-name
        string; a cell carrying extra attributes (``fullWidth``, ``noLabel``,
        ``view`` …) is preserved as a dict with the field name reversed.

        :param cell: Raw cell from the API.
        :param custom_names: Custom field API names for this entity.
        :returns: ``None``, a field-name string, or an attribute dict.
        """
        if cell is False or cell is None:
            return None
        if isinstance(cell, str):
            return self._reverse_field_name(cell, custom_names)
        if isinstance(cell, dict) and "name" in cell:
            reversed_name = self._reverse_field_name(cell["name"], custom_names)
            if len(cell) == 1:
                return reversed_name
            new_cell = dict(cell)
            new_cell["name"] = reversed_name
            return new_cell
        return None

    def _reverse_list_layout(
        self, layout_data: Any, custom_names: set[str]
    ) -> list[dict[str, Any]]:
        """Reverse-map a list layout from API format to YAML format.

        :param layout_data: Raw layout data from the API.
        :param custom_names: Set of custom field API names for this entity.
        :returns: List of column dicts in YAML format.
        """
        if not isinstance(layout_data, list):
            return []

        columns: list[dict[str, Any]] = []
        for col_data in layout_data:
            if not isinstance(col_data, dict):
                continue
            name = col_data.get("name", "")
            if not name:
                continue
            col: dict[str, Any] = {
                "field": self._reverse_field_name(name, custom_names),
            }
            width = col_data.get("width")
            if width is not None:
                col["width"] = width
            # Preserve other column attributes (link, notSortable, align,
            # view, …) verbatim for lossless round-trip.
            for key, val in col_data.items():
                if key not in ("name", "width"):
                    col[key] = val
            columns.append(col)

        return columns

    def _reverse_field_list_layout(
        self, layout_data: Any, custom_names: set[str]
    ) -> list[str]:
        """Reverse a FIELD_LIST layout (filters / massUpdate / relationships).

        :param layout_data: Raw list of name strings from the API.
        :param custom_names: Custom field API names for this entity.
        :returns: List of YAML names (field names reversed; relationship link
            names pass through).
        """
        if not isinstance(layout_data, list):
            return []
        return [
            self._reverse_field_name(n, custom_names)
            for n in layout_data
            if isinstance(n, str)
        ]

    def _reverse_panel_map_layout(self, layout_data: Any) -> dict[str, Any]:
        """Reverse a PANEL_MAP layout (side / bottom relationship panels).

        The mapping is preserved verbatim — its keys are relationship link
        names plus ``_delimiter_`` / ``_tabBreak_N`` meta keys, all
        deterministic from the configuration.

        :param layout_data: Raw ``{name: cfg}`` mapping from the API.
        :returns: The mapping (a shallow copy), or ``{}``.
        """
        return dict(layout_data) if isinstance(layout_data, dict) else {}

    def _reverse_dynamic_logic(
        self, dlv: dict[str, Any], custom_names: set[str]
    ) -> dict[str, Any]:
        """Reverse-map dynamic logic from API format to YAML shorthand.

        :param dlv: Dynamic logic visible dict from the API.
        :param custom_names: Set of custom field API names.
        :returns: YAML shorthand dict.
        """
        condition_group = dlv.get("conditionGroup", [])
        if (
            isinstance(condition_group, list)
            and len(condition_group) == 1
            and isinstance(condition_group[0], dict)
        ):
            cond = condition_group[0]
            attr = cond.get("attribute", "")
            value = cond.get("value")
            if attr:
                return {
                    "attribute": self._reverse_field_name(attr, custom_names),
                    "value": value,
                }
        # Complex logic — return as-is
        return dlv

    # ------------------------------------------------------------------
    # Relationship discovery
    # ------------------------------------------------------------------

    def _discover_relationships(
        self,
        entities: list[EntityAuditResult],
        report: AuditReport,
    ) -> list[RelationshipAuditResult]:
        """Discover relationships across all audited entities.

        :param entities: List of audited entities.
        :param report: Report to append errors/warnings to.
        :returns: Deduplicated list of relationship results.
        """
        espo_to_yaml = {e.espo_name: e.yaml_name for e in entities}

        # Deduplication: track seen relationship pairs
        seen: set[frozenset[str]] = set()
        results: list[RelationshipAuditResult] = []

        # Cache all links for all entities
        all_links: dict[str, dict[str, dict]] = {}
        for entity in entities:
            status, links = self._client.get_all_links(entity.espo_name)
            if status == 200 and isinstance(links, dict):
                all_links[entity.espo_name] = links
            else:
                msg = f"{entity.yaml_name}: failed to fetch links (HTTP {status})"
                report.warnings.append(msg)
                self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")

        for entity in entities:
            links = all_links.get(entity.espo_name, {})

            for link_name, link_meta in links.items():
                if not isinstance(link_meta, dict):
                    continue

                foreign_entity = link_meta.get("entity", "")
                if not foreign_entity:
                    continue

                # Skip parent-type polymorphic links
                if link_meta.get("type") == "belongsToParent":
                    continue
                if link_meta.get("type") == "hasChildren":
                    continue

                foreign_link = link_meta.get("foreign", "")
                if not foreign_link:
                    continue

                # Deduplication key
                dedup_key = frozenset({
                    f"{entity.espo_name}.{link_name}",
                    f"{foreign_entity}.{foreign_link}",
                })
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                # Get foreign side metadata for type resolution
                foreign_link_meta = all_links.get(foreign_entity, {}).get(foreign_link)

                link_type = _resolve_link_type(link_meta, foreign_link_meta)
                if not link_type:
                    msg = (
                        f"Could not resolve linkType for "
                        f"{entity.yaml_name}.{link_name}"
                    )
                    report.warnings.append(msg)
                    continue

                # Reverse-map names
                yaml_entity = espo_to_yaml.get(
                    entity.espo_name, strip_entity_c_prefix(entity.espo_name)
                )
                yaml_foreign = espo_to_yaml.get(
                    foreign_entity, strip_entity_c_prefix(foreign_entity)
                )

                custom_names = self._custom_field_names.get(entity.espo_name, set())
                yaml_link = self._reverse_field_name(link_name, custom_names)

                foreign_custom = self._custom_field_names.get(foreign_entity, set())
                yaml_link_foreign = self._reverse_field_name(foreign_link, foreign_custom)

                # Build a descriptive name
                rel_name = f"{yaml_entity.lower()}To{yaml_foreign}"

                # Link labels live in i18n (`i18n[Entity].links[linkName]`)
                # with `i18n.Global.links[linkName]` as fallback for native
                # links. The link_meta dict (from entityDefs.links) has no
                # `label` key on this server, so the prior reads always
                # collapsed to the link's API name.
                label = self._link_label(entity.espo_name, link_name, yaml_link)
                label_foreign = self._link_label(
                    foreign_entity, foreign_link, yaml_link_foreign
                )

                rel = RelationshipAuditResult(
                    name=rel_name,
                    entity=yaml_entity,
                    entity_foreign=yaml_foreign,
                    link_type=link_type,
                    link=yaml_link,
                    link_foreign=yaml_link_foreign,
                    label=label,
                    label_foreign=label_foreign,
                    relation_name=link_meta.get("relationName"),
                    audited=link_meta.get("audited", False),
                    audited_foreign=(
                        foreign_link_meta.get("audited", False)
                        if isinstance(foreign_link_meta, dict) else False
                    ),
                )
                results.append(rel)

        return results

    # ------------------------------------------------------------------
    # Filtered-tab discovery
    # ------------------------------------------------------------------

    def _discover_filtered_tabs(
        self,
        entities: list[EntityAuditResult],
        report: AuditReport,
    ) -> None:
        """Discover filtered tabs on the source instance.

        Walks all scopes to find custom tab-scopes, queries clientDefs
        for each to recover the entity binding and Report Filter ID,
        then matches against Report Filter records per audited entity.
        Mutates each :class:`EntityAuditResult.filtered_tabs` in place.

        HTTP 404 from :meth:`EspoAdminClient.list_report_filters` means
        the Advanced Pack extension is not installed; the method
        records an informational log line and skips silently for that
        entity rather than treating the absence as an error.

        Inverse of
        :class:`espo_impl.core.filtered_tab_manager.FilteredTabManager`
        on the deploy side. Per Section 11, relative-date tokens are
        not reverse-engineered: by the time a filter is deployed the
        date values are absolute ``YYYY-MM-DD`` strings, and the audit
        emits them verbatim. Operators who want relative tokens edit
        the YAML by hand after import.

        :param entities: Audited entities to attach filtered tabs to.
        :param report: For warning / error accumulation.
        """
        status, all_scopes = self._client.get_all_scopes()
        if status != 200 or not isinstance(all_scopes, dict):
            report.warnings.append(
                f"Failed to fetch scopes for filtered-tab discovery "
                f"(HTTP {status})"
            )
            return

        tab_scopes: list[str] = []
        for scope_name, scope_def in all_scopes.items():
            if not isinstance(scope_def, dict):
                continue
            if (
                scope_def.get("tab") is True
                and scope_def.get("isCustom") is True
                and scope_def.get("entity") is False
            ):
                tab_scopes.append(scope_name)

        if not tab_scopes:
            return

        bindings_by_entity: dict[str, list[tuple[str, str, str]]] = {}
        for scope_name in tab_scopes:
            status, client_defs = self._client.get_client_defs(scope_name)
            if status != 200 or not isinstance(client_defs, dict):
                report.warnings.append(
                    f"Failed to fetch clientDefs for scope '{scope_name}' "
                    f"(HTTP {status}); skipped"
                )
                continue
            entity_wire = client_defs.get("entity")
            default_filter = client_defs.get("defaultFilter", "")
            if not isinstance(entity_wire, str) or not entity_wire:
                continue
            if (
                not isinstance(default_filter, str)
                or not default_filter.startswith("reportFilter")
            ):
                continue
            report_filter_id = default_filter[len("reportFilter"):]
            acl = "boolean"
            scope_def = all_scopes.get(scope_name, {})
            if isinstance(scope_def, dict):
                acl_val = scope_def.get("acl")
                if isinstance(acl_val, str) and acl_val:
                    acl = acl_val
            bindings_by_entity.setdefault(entity_wire, []).append(
                (scope_name, report_filter_id, acl),
            )

        if not bindings_by_entity:
            return

        for entity in entities:
            entity_bindings = bindings_by_entity.get(entity.espo_name)
            if not entity_bindings:
                continue

            status, body = self._client.list_report_filters(entity.espo_name)
            if status == 404:
                self._cb(
                    "[AUDIT]    Note: Advanced Pack not installed; "
                    "filtered-tab criteria not auditable.",
                    "yellow",
                )
                continue
            if status != 200 or not isinstance(body, dict):
                report.warnings.append(
                    f"Failed to fetch Report Filters for "
                    f"'{entity.yaml_name}' (HTTP {status})"
                )
                continue

            filters_by_id: dict[str, dict[str, Any]] = {}
            items = body.get("list")
            if isinstance(items, list):
                for rf in items:
                    if isinstance(rf, dict) and isinstance(rf.get("id"), str):
                        filters_by_id[rf["id"]] = rf

            for scope_name, report_filter_id, acl in entity_bindings:
                rf = filters_by_id.get(report_filter_id)
                if rf is None:
                    report.warnings.append(
                        f"Scope '{scope_name}' binds to Report Filter "
                        f"'{report_filter_id}' but that record was not "
                        f"found; skipped"
                    )
                    continue

                data = rf.get("data") or {}
                where = data.get("where") if isinstance(data, dict) else None
                filter_ast = self._reverse_where_items(
                    where, report, scope_name,
                )

                label = scope_name
                rf_name = rf.get("name")
                if isinstance(rf_name, str) and rf_name:
                    label = rf_name
                global_block = (
                    self._i18n.get("Global", {})
                    if isinstance(self._i18n, dict) else {}
                )
                scope_names = (
                    global_block.get("scopeNames", {})
                    if isinstance(global_block, dict) else {}
                )
                label_from_i18n = (
                    scope_names.get(scope_name)
                    if isinstance(scope_names, dict) else None
                )
                if isinstance(label_from_i18n, str) and label_from_i18n:
                    label = label_from_i18n

                tab_id = (
                    scope_name[0].lower() + scope_name[1:]
                    if scope_name else scope_name
                )
                entity.filtered_tabs.append(FilteredTabAuditResult(
                    id=tab_id,
                    scope=scope_name,
                    label=label,
                    filter=filter_ast,
                    nav_order=None,
                    acl=acl,
                ))

    def _reverse_where_items(
        self,
        where: list | None,
        report: AuditReport,
        context_label: str,
    ) -> ConditionNode | None:
        """Reverse-translate a list of EspoCRM where-items to an AST root.

        Inverse of
        :meth:`espo_impl.core.filtered_tab_manager.FilteredTabManager._to_where_items`.

        Top-level wrapping follows the deploy side's contract: a
        single-item list unwraps to the bare child (so a single leaf
        round-trips as :class:`LeafClause` rather than
        ``AllNode([LeafClause])``); multiple items wrap in an implicit
        :class:`AllNode` (the schema's shorthand-list form).

        Unknown where-item types poison the whole filter — the method
        returns ``None`` with a warning so the caller emits the tab
        without a ``filter:`` block. Partial filters are unsafe.

        :param where: The Report Filter's ``data.where`` list.
        :param report: For warning accumulation on unknown types.
        :param context_label: Tab label/scope for warning attribution.
        :returns: Root AST node, or ``None`` if the list is empty or
            contained any unknown where-item type.
        """
        if not isinstance(where, list) or not where:
            return None

        converted: list[ConditionNode] = []
        for item in where:
            node = self._reverse_where_item(item, report, context_label)
            if node is None:
                report.warnings.append(
                    f"Filtered tab '{context_label}': filter contained "
                    f"unknown where-item types; filter omitted from YAML "
                    f"output (tab still captured with label and scope)"
                )
                return None
            converted.append(node)

        if len(converted) == 1:
            return converted[0]
        return AllNode(children=converted)

    def _reverse_where_item(
        self,
        item: Any,
        report: AuditReport,
        context_label: str,
    ) -> ConditionNode | None:
        """Reverse-translate a single EspoCRM where-item to an AST node.

        Inverse of
        :meth:`espo_impl.core.filtered_tab_manager.FilteredTabManager._node_to_where`
        and ``_leaf_to_where``. Returns ``None`` for any unknown
        where-item type so the caller can poison the whole filter.

        :param item: Single where-item dict.
        :param report: For warning accumulation.
        :param context_label: Tab label/scope for warning attribution.
        :returns: AST node, or ``None`` when the type is not in the
            schema's leaf-operator vocabulary.
        """
        if not isinstance(item, dict):
            return None

        item_type = item.get("type")
        if not isinstance(item_type, str):
            return None

        if item_type == "and":
            children_data = item.get("value", [])
            if not isinstance(children_data, list):
                return None
            children: list[ConditionNode] = []
            for child in children_data:
                child_node = self._reverse_where_item(
                    child, report, context_label,
                )
                if child_node is None:
                    return None
                children.append(child_node)
            return AllNode(children=children)
        if item_type == "or":
            children_data = item.get("value", [])
            if not isinstance(children_data, list):
                return None
            children = []
            for child in children_data:
                child_node = self._reverse_where_item(
                    child, report, context_label,
                )
                if child_node is None:
                    return None
                children.append(child_node)
            return AnyNode(children=children)

        attribute = item.get("attribute")
        if not isinstance(attribute, str) or not attribute:
            return None

        if item_type == "currentUser":
            return LeafClause(field=attribute, op="equals", value="$user")
        if item_type == "notCurrentUser":
            return LeafClause(field=attribute, op="notEquals", value="$user")

        if item_type in ("isNull", "isNotNull"):
            return LeafClause(field=attribute, op=item_type)

        if item_type not in OPERATORS:
            report.warnings.append(
                f"Filtered tab '{context_label}': unknown where-item "
                f"type '{item_type}' on attribute '{attribute}'"
            )
            return None

        value = item.get("value")
        return LeafClause(field=attribute, op=item_type, value=value)

    # ------------------------------------------------------------------
    # Security discovery (roles + teams)
    # ------------------------------------------------------------------

    def _discover_teams(
        self, report: AuditReport,
    ) -> list[TeamAuditResult]:
        """Discover all teams on the source instance.

        Each team becomes a TeamAuditResult with name and description.
        Per DEC-1 (audit_log removed) and DEC-2 (EspoCRM-only
        permissions preserved), team_to_user membership is not
        captured — it's runtime data per Schema §12.2.

        :param report: Audit report for error accumulation.
        :returns: List of TeamAuditResult. Empty list on no teams
            or on API failure (with the failure logged to the
            audit report).
        """
        status, body = self._client.get_teams()
        if status != 200 or not isinstance(body, dict):
            msg = f"Failed to fetch teams (HTTP {status})"
            report.errors.append(msg)
            self._cb(f"[AUDIT]    ERROR: {msg}", "red")
            return []
        server_teams = body.get("list") or []
        if not isinstance(server_teams, list):
            return []
        results: list[TeamAuditResult] = []
        for record in server_teams:
            if not isinstance(record, dict):
                continue
            name = record.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            description = record.get("description")
            if description is not None and not isinstance(description, str):
                description = None
            results.append(TeamAuditResult(
                name=name,
                description=description if description else None,
            ))
        return results

    def _discover_roles(
        self, report: AuditReport,
    ) -> list[RoleAuditResult]:
        """Discover all roles on the source instance.

        Translates each Role record's wire shape to the schema's
        structured form via :meth:`_reverse_scope_access` and
        :meth:`_reverse_system_permissions`.

        Per DEC-179, captures with empty scope_access produce an
        informational warning in the audit log; the YAML output is
        unaffected.

        :param report: Audit report for error/warning accumulation.
        :returns: List of RoleAuditResult. Empty on API failure
            (with the failure logged to the audit report).
        """
        status, body = self._client.get_roles()
        if status != 200 or not isinstance(body, dict):
            msg = f"Failed to fetch roles (HTTP {status})"
            report.errors.append(msg)
            self._cb(f"[AUDIT]    ERROR: {msg}", "red")
            return []
        server_roles = body.get("list") or []
        if not isinstance(server_roles, list):
            return []
        results: list[RoleAuditResult] = []
        for record in server_roles:
            if not isinstance(record, dict):
                continue
            name = record.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            description = record.get("description")
            if description is not None and not isinstance(description, str):
                description = None
            scope_access = self._reverse_scope_access(
                record.get("data") or {}, report, role_name=name,
            )
            system_permissions = self._reverse_system_permissions(record)

            if not scope_access:
                report.warnings.append(
                    f"Role '{name}' has empty scope_access; this role "
                    f"grants no entity access on the source instance"
                )

            results.append(RoleAuditResult(
                name=name,
                description=description if description else None,
                persona=None,
                scope_access=scope_access,
                system_permissions=system_permissions,
            ))
        return results

    def _reverse_scope_access(
        self,
        data: dict,
        report: AuditReport,
        role_name: str,
    ) -> dict[str, ScopeAccess]:
        """Reverse-translate EspoCRM Role.data to schema scope_access.

        Inverse of ``role_manager._translate_data_block``.

        :param data: Raw ``data`` field from the Role record (dict of
            per-scope permission objects).
        :param report: Audit report for warnings on skipped scopes.
        :param role_name: Role name for warning attribution.
        :returns: Mapping of natural entity name to ScopeAccess.
        """
        result: dict[str, ScopeAccess] = {}
        if not isinstance(data, dict):
            return result
        for wire_name, value in data.items():
            if not isinstance(wire_name, str):
                continue
            natural_name = strip_entity_c_prefix(wire_name)
            if not isinstance(value, dict):
                report.warnings.append(
                    f"Role '{role_name}': scope '{natural_name}' has "
                    f"non-mapping value {value!r}; skipped (not "
                    f"representable in v1.3 schema)"
                )
                continue
            try:
                scope = ScopeAccess(
                    create=value.get("create") == "yes",
                    read=str(value.get("read") or "no"),
                    edit=str(value.get("edit") or "no"),
                    delete=str(value.get("delete") or "no"),
                    stream=str(value.get("stream") or "no"),
                )
                result[natural_name] = scope
            except (ValueError, TypeError) as exc:
                report.warnings.append(
                    f"Role '{role_name}': scope '{natural_name}' "
                    f"failed to translate ({exc}); skipped"
                )
        return result

    def _reverse_system_permissions(
        self,
        record: dict,
    ) -> SystemPermissions | None:
        """Reverse-translate EspoCRM Role columns to SystemPermissions.

        Inverse of ``role_manager._translate_system_permissions``.
        Reads only the five schema-managed camelCase columns; the
        three EspoCRM-only permissions (DEC-2 preservation list) are
        not captured.

        :param record: Full Role record from the EspoCRM API.
        :returns: SystemPermissions instance, or None if none of the
            five managed columns are present on the record.
        """
        managed_columns = (
            "assignmentPermission", "userPermission",
            "exportPermission", "massUpdatePermission",
            "portalPermission",
        )
        has_any = any(record.get(col) is not None for col in managed_columns)
        if not has_any:
            return None

        return SystemPermissions(
            assignment_permission=str(
                record.get("assignmentPermission") or "no"
            ),
            user_permission=str(
                record.get("userPermission") or "no"
            ),
            export=record.get("exportPermission") == "yes",
            mass_update=record.get("massUpdatePermission") == "yes",
            portal=record.get("portalPermission") == "yes",
        )

    # ------------------------------------------------------------------
    # YAML generation
    # ------------------------------------------------------------------

    def _write_yaml_files(
        self,
        entities: list[EntityAuditResult],
        relationships: list[RelationshipAuditResult],
        output_dir: Path,
        report: AuditReport,
    ) -> int:
        """Serialize audit results to YAML files.

        :param entities: Audited entities.
        :param relationships: Audited relationships.
        :param output_dir: Output directory.
        :param report: Report to append errors to.
        :returns: Number of files written.
        """
        files_written = 0

        # One file per entity
        for entity in entities:
            if not entity.fields and not entity.layouts and not entity.filtered_tabs:
                continue

            yaml_dict = self._build_entity_yaml(entity)
            file_path = output_dir / f"{entity.yaml_name}.yaml"

            try:
                self._write_yaml_file(file_path, yaml_dict)
                files_written += 1
            except OSError as exc:
                msg = f"Failed to write {file_path.name}: {exc}"
                report.errors.append(msg)
                self._cb(f"[AUDIT]    ERROR: {msg}", "red")

        # Relationships file
        if relationships:
            rel_dict = self._build_relationships_yaml(relationships)
            file_path = output_dir / "relationships.yaml"

            try:
                self._write_yaml_file(file_path, rel_dict)
                files_written += 1
            except OSError as exc:
                msg = f"Failed to write relationships.yaml: {exc}"
                report.errors.append(msg)
                self._cb(f"[AUDIT]    ERROR: {msg}", "red")

        # Security file (roles + teams) — DEC-182 places under security/
        if report.roles or report.teams:
            security_dir = output_dir / "security"
            security_dir.mkdir(parents=True, exist_ok=True)
            security_dict = self._build_security_yaml(report.roles, report.teams)
            file_path = security_dir / "security.yaml"

            try:
                self._write_yaml_file(file_path, security_dict)
                files_written += 1
            except OSError as exc:
                msg = f"Failed to write security/security.yaml: {exc}"
                report.errors.append(msg)
                self._cb(f"[AUDIT]    ERROR: {msg}", "red")

        return files_written

    def _build_entity_yaml(self, entity: EntityAuditResult) -> dict[str, Any]:
        """Build the YAML dict for a single entity.

        :param entity: Audited entity.
        :returns: YAML-serializable dict.
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_url = self._client.profile.url

        entity_block: dict[str, Any] = {}

        # Entity-level properties for custom entities
        if entity.entity_class == EntityClass.CUSTOM:
            entity_block["action"] = "create"
            if entity.entity_type:
                entity_block["type"] = entity.entity_type
            if entity.label_singular:
                entity_block["labelSingular"] = entity.label_singular
            if entity.label_plural:
                entity_block["labelPlural"] = entity.label_plural
            entity_block["stream"] = entity.stream

        # Fields
        if entity.fields:
            fields_list: list[dict[str, Any]] = []
            for f in entity.fields:
                field_dict: dict[str, Any] = {
                    "name": f.yaml_name,
                    "type": f.field_type,
                    "label": f.label,
                }
                field_dict.update(f.properties)
                fields_list.append(field_dict)
            entity_block["fields"] = fields_list

        # Layouts
        if entity.layouts:
            layout_block: dict[str, Any] = {}
            for layout_result in entity.layouts:
                layout_block[layout_result.layout_type] = layout_result.data
            entity_block["layout"] = layout_block

        # Filtered tabs
        if entity.filtered_tabs:
            entity_block["filteredTabs"] = [
                self._filtered_tab_to_yaml_dict(t)
                for t in entity.filtered_tabs
            ]

        return {
            "version": "1.0",
            "content_version": "1.0.0",
            "description": (
                f"Audit snapshot of {entity.yaml_name} captured from "
                f"{source_url} on {timestamp}."
            ),
            "entities": {entity.yaml_name: entity_block},
        }

    def _build_relationships_yaml(
        self, relationships: list[RelationshipAuditResult]
    ) -> dict[str, Any]:
        """Build the YAML dict for the relationships file.

        :param relationships: Audited relationships.
        :returns: YAML-serializable dict.
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_url = self._client.profile.url

        rels_list: list[dict[str, Any]] = []
        for rel in relationships:
            rel_dict: dict[str, Any] = {
                "name": rel.name,
                "entity": rel.entity,
                "entityForeign": rel.entity_foreign,
                "linkType": rel.link_type,
                "link": rel.link,
                "linkForeign": rel.link_foreign,
                "label": rel.label,
                "labelForeign": rel.label_foreign,
            }
            if rel.relation_name:
                rel_dict["relationName"] = rel.relation_name
            if rel.audited:
                rel_dict["audited"] = True
            if rel.audited_foreign:
                rel_dict["auditedForeign"] = True
            rels_list.append(rel_dict)

        return {
            "version": "1.0",
            "content_version": "1.0.0",
            "description": (
                f"Relationships audit snapshot captured from "
                f"{source_url} on {timestamp}."
            ),
            "relationships": rels_list,
        }

    def _build_security_yaml(
        self,
        roles: list[RoleAuditResult],
        teams: list[TeamAuditResult],
    ) -> dict[str, Any]:
        """Build the YAML dict for the security file.

        Emits a ``teams:`` block when teams were captured and a
        ``roles:`` block when roles were captured. Per DEC-182 the
        caller writes the result to ``security/security.yaml``.

        :param roles: Audited roles.
        :param teams: Audited teams.
        :returns: YAML-serializable dict.
        """
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        source_url = self._client.profile.url

        result: dict[str, Any] = {
            "version": "1.0",
            "content_version": "1.0.0",
            "description": (
                f"Security audit snapshot (roles and teams) captured "
                f"from {source_url} on {timestamp}."
            ),
        }

        if teams:
            result["teams"] = [self._team_to_yaml_dict(t) for t in teams]
        if roles:
            result["roles"] = [self._role_to_yaml_dict(r) for r in roles]

        return result

    def _filtered_tab_to_yaml_dict(
        self, tab: FilteredTabAuditResult,
    ) -> dict[str, Any]:
        """Serialize a FilteredTabAuditResult to its YAML dict form.

        Mirrors the schema's ``filteredTabs:`` entry shape. The
        ``filter:`` key is omitted when no filter could be recovered
        (an unknown where-item type triggered the all-or-nothing
        skip in :meth:`_reverse_where_items`) so the operator hand-
        writes the missing filter post-import.
        """
        tab_dict: dict[str, Any] = {
            "id": tab.id,
            "scope": tab.scope,
            "label": tab.label,
            "acl": tab.acl,
        }
        if tab.nav_order is not None:
            tab_dict["navOrder"] = tab.nav_order
        if tab.filter is not None:
            tab_dict["filter"] = render_condition(tab.filter)
        return tab_dict

    def _team_to_yaml_dict(self, team: TeamAuditResult) -> dict[str, Any]:
        """Serialize a TeamAuditResult to its YAML dict form."""
        team_dict: dict[str, Any] = {"name": team.name}
        if team.description:
            team_dict["description"] = team.description
        return team_dict

    def _role_to_yaml_dict(self, role: RoleAuditResult) -> dict[str, Any]:
        """Serialize a RoleAuditResult to its YAML dict form.

        Mirrors Schema §12.1 / §12.3 / §12.4. The five-action
        ``scope_access`` blocks are keyed by natural entity name;
        ``system_permissions`` carries only the five schema-managed
        keys when present.
        """
        role_dict: dict[str, Any] = {"name": role.name}
        if role.description:
            role_dict["description"] = role.description
        if role.persona:
            role_dict["persona"] = role.persona
        if role.scope_access:
            scope_block: dict[str, dict[str, Any]] = {}
            for entity_name, scope in role.scope_access.items():
                scope_block[entity_name] = {
                    "create": scope.create,
                    "read": scope.read,
                    "edit": scope.edit,
                    "delete": scope.delete,
                    "stream": scope.stream,
                }
            role_dict["scope_access"] = scope_block
        if role.system_permissions is not None:
            perms = role.system_permissions
            role_dict["system_permissions"] = {
                "assignment_permission": perms.assignment_permission,
                "user_permission": perms.user_permission,
                "export": perms.export,
                "mass_update": perms.mass_update,
                "portal": perms.portal,
            }
        return role_dict

    def _write_yaml_file(self, path: Path, data: dict[str, Any]) -> None:
        """Write a YAML dict to a file with clean formatting.

        :param path: File path to write.
        :param data: YAML-serializable dict.
        """
        content = yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )
        path.write_text(content, encoding="utf-8")
