"""Live-capture discovery and reverse-mapping core — extracted for PI-454.

The retained heart of the retired V1 Audit feature: the pieces the V1
**reconcile** feature still runs. When the V1 audit was removed (PI-454 /
REQ-549 — the V2 native audit reached parity, PRJ-112), the reconcile
feature's live reads still needed the discovery methods
(``_discover_relationships`` / ``_discover_roles`` / ``_discover_teams``),
the layout / dynamic-logic reverse-mapper family, the i18n label lookups,
the audited layout-type list, and the role/team YAML dict builders — so
exactly that surface moved here, behaviour-identical, keeping its class
name. The audit orchestration (``run_audit``), extraction, manifest and
YAML-file writers were deleted with the feature; the V2 audit
(``crmbuilder_v2/introspect/``) is the successor for auditing.

Consumers: ``live_state.py`` (relationship / role / team capture),
``layout_reverse.py`` (the reverse mappers), ``reconstruct.py`` (role/team
YAML dicts), and the V2 layout-type parity test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from espo_impl.core.api_client import EspoAdminClient
from espo_impl.core.audit_utils import (
    NATIVE_ENTITIES,
    EntityClass,
    strip_entity_c_prefix,
    strip_field_c_prefix,
)
from espo_impl.core.condition_expression import (
    AllNode,
    AnyNode,
    ConditionNode,
    LeafClause,
)
from espo_impl.core.layout_types import (
    PANEL_MAP_LAYOUTS,
)
from espo_impl.core.models import ScopeAccess, SystemPermissions

ProgressCallback = Callable[[str, str], None]



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
    :param include_email_templates: Discover per-entity email templates
        and emit an ``emailTemplates:`` block plus sidecar body files
        (REQ-124 / PI-168). Default on, matching the DEC-180 precedent
        that the audit's identity is full-configuration round-trip.
    :param include_field_dynamic_logic: Capture field-level conditional
        requirement / visibility (requiredWhen / visibleWhen) from
        clientDefs dynamic logic (REQ-123 / PI-170). Default on, matching
        the DEC-180 full-configuration round-trip precedent.
    :param include_formula_scripts: Capture entity-level EspoCRM formula
        scripts verbatim into a ``formulaScript:`` block (REQ-122 /
        Option A). Capture only — EspoCRM has no REST write path for
        entity formulas, so re-applying them on the target is manual.
        Default on, matching the DEC-180 full-configuration precedent.
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
    include_email_templates: bool = True
    include_field_dynamic_logic: bool = True
    include_formula_scripts: bool = True
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
    # Collection-level settings captured from entityDefs.<Entity>.collection
    # (PI-300 / REQ-340): default sort, text-filter fields, full-text search.
    order_by: str | None = None
    order: str | None = None
    text_filter_fields: list[str] | None = None
    full_text_search: bool | None = None
    full_text_search_min_length: int | None = None
    # Entity-level options captured for both-way reconcile (PI-312 / REQ-346):
    # icon/color/kanban from clientDefs, optimistic-concurrency/count from
    # entityDefs, and the derived multiple-assignment toggle.
    icon_class: str | None = None
    color: str | None = None
    kanban_view_mode: bool | None = None
    status_field: str | None = None
    optimistic_concurrency_control: bool | None = None
    count_disabled: bool | None = None
    multiple_assigned_users: bool | None = None
    fields: list[FieldAuditResult] = field(default_factory=list)
    layouts: list[LayoutAuditResult] = field(default_factory=list)
    filtered_tabs: list[FilteredTabAuditResult] = field(default_factory=list)
    email_templates: list[EmailTemplateAuditResult] = field(
        default_factory=list
    )
    # Entity-level EspoCRM formula scripts captured verbatim (REQ-122 /
    # Option A): {scriptKey: script}, e.g. {"beforeSaveCustomScript": "..."}.
    formula_scripts: dict[str, str] = field(default_factory=dict)


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
class EmailTemplateAuditResult:
    """Result of auditing a single email template.

    Mirrors the YAML-side :class:`espo_impl.core.models.EmailTemplate`.
    ``merge_fields`` are reverse-derived from the ``{{fieldName}}``
    placeholders in the captured subject and body, matching the
    placeholder grammar the deploy-side validator enforces, so the
    emitted block re-deploys without hand-editing.

    :param id: Stable identifier, slugified from the template name and
        made unique within the entity (the deploy side matches
        templates by ``name``, so this is YAML-local only).
    :param name: Server-assigned template name.
    :param subject: Subject line, possibly with ``{{field}}``
        placeholders.
    :param body: Raw HTML body captured from the source record; written
        to a sidecar ``.html`` file and referenced via ``bodyFile``.
    :param merge_fields: Field names used as ``{{...}}`` placeholders.
    """

    id: str
    name: str
    subject: str
    body: str
    merge_fields: list[str] = field(default_factory=list)


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



# EspoCRM metadata link type → YAML linkType
_LINK_TYPE_MAP: dict[str, str] = {
    "hasMany": "oneToMany",
    "hasOne": "oneToMany",
    "belongsTo": "manyToOne",
    "belongsToParent": "manyToOne",
}


# EspoCRM dynamic-logic conditionGroup operator → YAML condition-expression
# operator (REQ-123 / PI-170). Types that carry a value map straight to the
# §11 operator vocabulary; the four value-less / boolean types are translated
# (isEmpty→isNull, isNotEmpty→isNotNull, isTrue→equals true, isFalse→equals
# false). Any type not handled here poisons the field's dynamic logic (it is
# omitted with a warning rather than mis-translated).
_DYNAMIC_LOGIC_OP_MAP: dict[str, str] = {
    "equals": "equals",
    "notEquals": "notEquals",
    "contains": "contains",
    "in": "in",
    "notIn": "notIn",
    "greaterThan": "greaterThan",
    "lessThan": "lessThan",
    "greaterThanOrEquals": "greaterThanOrEqual",
    "lessThanOrEquals": "lessThanOrEqual",
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
    # Field-level dynamic logic (requiredWhen / visibleWhen) — PI-170
    # ------------------------------------------------------------------


    def _reverse_dynamic_logic_group(
        self,
        condition_group: Any,
        custom_names: set[str],
        report: AuditReport,
        context: str,
    ) -> ConditionNode | None:
        """Reverse an EspoCRM dynamic-logic conditionGroup to an AST root.

        Multiple top-level items are an implicit ``and`` (EspoCRM's
        default), so they wrap in an :class:`AllNode`; a single item
        unwraps to its bare node. Returns ``None`` (the field's dynamic
        logic is then skipped) when the group is empty or contains any
        operator outside the §11 vocabulary.

        :param condition_group: The ``conditionGroup`` list from clientDefs.
        :param custom_names: Custom field API names, for name reversal.
        :param report: For warning accumulation.
        :param context: Label (entity.field.kind) for warning attribution.
        :returns: Root AST node, or ``None``.
        """
        if not isinstance(condition_group, list) or not condition_group:
            return None
        converted: list[ConditionNode] = []
        for item in condition_group:
            node = self._reverse_dynamic_logic_item(
                item, custom_names, report, context,
            )
            if node is None:
                return None
            converted.append(node)
        if len(converted) == 1:
            return converted[0]
        return AllNode(children=converted)

    def _reverse_dynamic_logic_item(
        self,
        item: Any,
        custom_names: set[str],
        report: AuditReport,
        context: str,
    ) -> ConditionNode | None:
        """Reverse a single dynamic-logic condition item to an AST node.

        Handles ``and`` / ``or`` groups (children under ``value``), the
        value-less ``isEmpty`` / ``isNotEmpty`` (→ ``isNull`` / ``isNotNull``)
        and boolean ``isTrue`` / ``isFalse`` (→ ``equals`` true / false)
        types, and the value-carrying operators in
        :data:`_DYNAMIC_LOGIC_OP_MAP`. Returns ``None`` for any unknown
        type so the caller drops the whole field's logic.
        """
        if not isinstance(item, dict):
            return None
        item_type = item.get("type")
        if item_type == "and":
            return self._reverse_dynamic_logic_subgroup(
                item, custom_names, report, context, AllNode,
            )
        if item_type == "or":
            return self._reverse_dynamic_logic_subgroup(
                item, custom_names, report, context, AnyNode,
            )

        attribute = item.get("attribute")
        if not isinstance(attribute, str) or not attribute:
            return None
        field = self._reverse_field_name(attribute, custom_names)

        if item_type == "isEmpty":
            return LeafClause(field=field, op="isNull")
        if item_type == "isNotEmpty":
            return LeafClause(field=field, op="isNotNull")
        if item_type == "isTrue":
            return LeafClause(field=field, op="equals", value=True)
        if item_type == "isFalse":
            return LeafClause(field=field, op="equals", value=False)

        mapped = _DYNAMIC_LOGIC_OP_MAP.get(item_type)
        if mapped is None:
            report.warnings.append(
                f"{context}: dynamic logic uses unsupported condition type "
                f"'{item_type}'; field logic omitted from YAML output"
            )
            return None
        return LeafClause(field=field, op=mapped, value=item.get("value"))

    def _reverse_dynamic_logic_subgroup(
        self,
        item: dict,
        custom_names: set[str],
        report: AuditReport,
        context: str,
        node_cls: type,
    ) -> ConditionNode | None:
        """Reverse an ``and`` / ``or`` dynamic-logic group to a node."""
        children_data = item.get("value", [])
        if not isinstance(children_data, list) or not children_data:
            return None
        children: list[ConditionNode] = []
        for child in children_data:
            child_node = self._reverse_dynamic_logic_item(
                child, custom_names, report, context,
            )
            if child_node is None:
                return None
            children.append(child_node)
        return node_cls(children=children)

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

                # Reverse-map link names by stripping the platform c-prefix
                # that EspoCRM applies to custom links ONLY on native entities
                # (REQ-344 / PI-309). Emitting the prefixed form (cChildAccounts)
                # makes the next deploy double-prefix it (cCChildAccounts) since
                # EspoCRM re-applies the prefix. Custom-entity links keep their
                # natural names. Symmetric to the field fix in PI-307; keyed off
                # the link's own entity, not the field custom-name set.
                yaml_link = strip_field_c_prefix(
                    link_name,
                    entity_is_native=(entity.espo_name in NATIVE_ENTITIES),
                )
                yaml_link_foreign = strip_field_c_prefix(
                    foreign_link,
                    entity_is_native=(foreign_entity in NATIVE_ENTITIES),
                )

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
