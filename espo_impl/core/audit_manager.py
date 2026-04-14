"""CRM audit manager — reverse-engineers a live CRM into YAML program files.

Connects to a source EspoCRM instance, discovers its configuration
(entities, fields, layouts, relationships), and produces YAML program
files in the same schema the configure engine consumes.
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
    :param include_relationships: Discover relationships.
    :param include_native_fields: Include native fields (normally excluded).
    """

    include_custom_fields: bool = True
    include_native_custom_fields: bool = True
    include_detail_layouts: bool = True
    include_list_layouts: bool = True
    include_relationships: bool = True
    include_native_fields: bool = False


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
    """Result of auditing a layout."""

    layout_type: str
    data: dict[str, Any] = field(default_factory=dict)


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


@dataclass
class AuditReport:
    """Aggregate results of a full audit."""

    source_url: str
    source_name: str
    timestamp: str
    output_dir: str
    entities: list[EntityAuditResult] = field(default_factory=list)
    relationships: list[RelationshipAuditResult] = field(default_factory=list)
    files_written: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


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
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        report = AuditReport(
            source_url=self._client.profile.url,
            source_name=self._client.profile.name,
            timestamp=timestamp,
            output_dir=str(output_dir),
        )

        # Step 1: Discover entities
        self._cb("[AUDIT]    Discovering entities ...", "cyan")
        entities = self._discover_entities(report)
        if not entities:
            self._cb("[AUDIT]    No auditable entities found.", "yellow")
            return report

        custom_count = sum(1 for e in entities if e.entity_class == EntityClass.CUSTOM)
        native_count = sum(1 for e in entities if e.entity_class == EntityClass.NATIVE)
        self._cb(
            f"[AUDIT]    Found {custom_count} custom entities, "
            f"{native_count} native entities with custom fields",
            "cyan",
        )

        # Step 2: Extract fields and layouts per entity
        for i, entity in enumerate(entities, 1):
            self._cb(
                f"[AUDIT]    {entity.yaml_name} — extracting fields "
                f"({i} of {len(entities)}) ...",
                "white",
            )
            self._extract_fields(entity, report)

            if self._options.include_detail_layouts:
                self._extract_layout(entity, "detail", report)
            if self._options.include_list_layouts:
                self._extract_layout(entity, "list", report)

        # Step 3: Discover relationships
        relationships: list[RelationshipAuditResult] = []
        if self._options.include_relationships:
            self._cb("[AUDIT]    Discovering relationships ...", "cyan")
            relationships = self._discover_relationships(entities, report)
            self._cb(
                f"[AUDIT]    Found {len(relationships)} relationships",
                "cyan",
            )

        report.entities = entities
        report.relationships = relationships

        # Step 4: Write YAML files
        self._cb(
            f"[AUDIT]    Writing YAML files to {output_dir.name}/ ...",
            "cyan",
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        files_written = self._write_yaml_files(entities, relationships, output_dir, report)
        report.files_written = files_written

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

        results: list[EntityAuditResult] = []
        for scope_name, scope_meta in scopes.items():
            if not isinstance(scope_meta, dict):
                continue

            entity_class = classify_entity(scope_name, scope_meta)

            if entity_class == EntityClass.SYSTEM:
                continue

            if entity_class == EntityClass.NATIVE and not self._options.include_native_custom_fields:
                continue

            yaml_name = get_yaml_entity_name(scope_name)
            entity_type = scope_meta.get("type")

            # Fetch labels from full metadata
            label_singular = None
            label_plural = None
            meta_status, meta = self._client.get_entity_full_metadata(scope_name)
            if meta_status == 200 and isinstance(meta, dict):
                label_singular = meta.get("fields", {}).get("name", {}).get("label") or scope_name
                # Try to get labels from the scope or metadata
                # EspoCRM doesn't always have these in entityDefs
            label_singular = label_singular or yaml_name
            label_plural = label_plural or f"{yaml_name}s"

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
            label = meta.get("label", yaml_name)

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
                if translated and translated != dict(zip(options or [], options or [])):
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

    def _extract_layout(
        self,
        entity: EntityAuditResult,
        layout_type: str,
        report: AuditReport,
    ) -> None:
        """Fetch and reverse-map a layout for an entity.

        :param entity: Entity to extract layout for.
        :param layout_type: "detail" or "list".
        :param report: Report to append errors/warnings to.
        """
        status, layout_data = self._client.get_layout(entity.espo_name, layout_type)
        if status != 200 or layout_data is None:
            msg = f"{entity.yaml_name}: failed to fetch {layout_type} layout (HTTP {status})"
            report.warnings.append(msg)
            self._cb(f"[AUDIT]    WARNING: {msg}", "yellow")
            return

        custom_names = self._custom_field_names.get(entity.espo_name, set())

        if layout_type == "list":
            columns = self._reverse_list_layout(layout_data, custom_names)
            if columns:
                entity.layouts.append(LayoutAuditResult(
                    layout_type="list",
                    data={"columns": columns},
                ))
                self._cb(
                    f"[AUDIT]    {entity.yaml_name} — list layout "
                    f"({len(columns)} columns)",
                    "white",
                )
        else:
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
                rows: list[list[str | None]] = []
                for raw_row in raw_rows:
                    if not isinstance(raw_row, list):
                        continue
                    row: list[str | None] = []
                    for cell in raw_row:
                        if isinstance(cell, dict) and "name" in cell:
                            row.append(
                                self._reverse_field_name(cell["name"], custom_names)
                            )
                        elif cell is False or cell is None:
                            row.append(None)
                        elif isinstance(cell, str):
                            row.append(
                                self._reverse_field_name(cell, custom_names)
                            )
                        else:
                            row.append(None)
                    rows.append(row)
                if rows:
                    panel["rows"] = rows

            panels.append(panel)

        return panels

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
            columns.append(col)

        return columns

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
        # Track which entity espo names are in scope
        in_scope = {e.espo_name for e in entities}
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

                # Labels — use link name as fallback
                label = link_meta.get("label", yaml_link)
                label_foreign = ""
                if foreign_link_meta and isinstance(foreign_link_meta, dict):
                    label_foreign = foreign_link_meta.get("label", yaml_link_foreign)
                else:
                    label_foreign = yaml_link_foreign

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
            if not entity.fields and not entity.layouts:
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

        return files_written

    def _build_entity_yaml(self, entity: EntityAuditResult) -> dict[str, Any]:
        """Build the YAML dict for a single entity.

        :param entity: Audited entity.
        :returns: YAML-serializable dict.
        """
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
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
