"""Data models for CRM Builder."""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class InstanceRole(Enum):
    """Role of an EspoCRM instance in the workflow."""

    SOURCE = "source"
    TARGET = "target"
    BOTH = "both"


@dataclass
class InstanceProfile:
    """An EspoCRM instance connection profile.

    :param name: Human-readable instance name.
    :param url: Base URL of the EspoCRM instance.
    :param api_key: API key for authentication.
    :param auth_method: Authentication method ("api_key" or "hmac").
    :param secret_key: Secret key for HMAC authentication.
    :param project_folder: Path to client project directory.
    :param role: Instance role — source (audit), target (deploy/configure), or both.
    """

    name: str
    url: str
    api_key: str
    auth_method: str = "api_key"
    secret_key: str | None = None
    project_folder: str | None = None
    role: InstanceRole = InstanceRole.TARGET

    @property
    def programs_dir(self) -> Path | None:
        """Path to the programs directory for this instance."""
        if self.project_folder:
            return Path(self.project_folder) / "programs"
        return None

    @property
    def reports_dir(self) -> Path | None:
        """Path to the reports directory for this instance."""
        if self.project_folder:
            return Path(self.project_folder) / "reports"
        return None

    @property
    def docs_dir(self) -> Path | None:
        """Path to the Implementation Docs directory for this instance."""
        if self.project_folder:
            return Path(self.project_folder) / "Implementation Docs"
        return None

    @property
    def api_url(self) -> str:
        """Full API base URL."""
        return f"{self.url.rstrip('/')}/api/v1"

    @property
    def slug(self) -> str:
        """Filename-safe slug derived from name."""
        return self.name.lower().replace(" ", "_").replace("-", "_")


@dataclass
class FieldDefinition:
    """A single field specification from a YAML program file.

    :param name: Internal field name (lowerCamelCase).
    :param type: EspoCRM field type.
    :param label: Display label.
    :param optionsDeferred: When True on an enum/multiEnum field
        with empty `options`, the validator accepts the empty list.
        Used for fields where the value list cannot be expressed
        at Phase 9 generation time and is documented for
        post-deploy operator configuration in MANUAL-CONFIG.md.
        Default None (treated as False).
    :param link: Required on ``type: foreign`` fields. Name of the
        manyToOne or oneToOne link on this entity whose target
        record supplies the mirrored value. Declared in the
        top-level ``relationships:`` block (Section 8). YAML key
        is ``link:``.
    :param foreign_field: Required on ``type: foreign`` fields.
        Name of the field on the linked entity whose value is
        mirrored onto this entity's detail/list views. YAML key
        is ``field:`` (renamed in Python to avoid shadowing the
        ``dataclasses.field`` import).
    """

    name: str
    type: str
    label: str
    required: bool | None = None
    default: str | None = None
    readOnly: bool | None = None
    audited: bool | None = None
    copyToClipboard: bool | None = None
    options: list[str] | None = None
    optionDescriptions: dict[str, str] | None = None
    optionsDeferred: bool | None = None
    translatedOptions: dict[str, str] | None = None
    style: dict[str, str | None] | None = None
    isSorted: bool | None = None
    displayAsLabel: bool | None = None
    min: int | None = None
    max: int | None = None
    maxLength: int | None = None
    category: str | None = None
    description: str | None = None
    tooltip: str | None = None
    required_when_raw: list | dict | None = None
    visible_when_raw: list | dict | None = None
    required_when: Any = None  # ConditionNode from condition_expression
    visible_when: Any = None  # ConditionNode from condition_expression
    formula: Any = None  # Formula from models
    formula_raw: dict | None = None
    externally_populated: bool = False
    link: str | None = None
    foreign_field: str | None = None


@dataclass
class TabSpec:
    """A sub-tab within a panel, populated by field category."""

    label: str
    category: str
    rows: list | None = None


@dataclass
class ColumnSpec:
    """A column in a list view layout.

    :param field: The (natural, un-prefixed) field name shown in the column.
    :param width: Optional column width as a percentage.
    :param attrs: Passthrough of any other EspoCRM column attributes
        (``link``, ``align``, ``notSortable``, ``view``, ``widthPx``,
        ``hidden`` …) preserved verbatim for lossless round-trip. Field-name
        normalization (c-prefix) is applied to ``field`` only; ``attrs`` is
        emitted/compared as-is.
    """

    field: str
    width: int | None = None
    attrs: dict = field(default_factory=dict)


@dataclass
class PanelSpec:
    """A panel in a detail/edit layout."""

    label: str
    tabBreak: bool = False
    tabLabel: str | None = None
    style: str = "default"
    hidden: bool = False
    dynamicLogicVisible: dict | None = None
    visible_when_raw: list | dict | None = None
    visible_when: Any = None  # ConditionNode from condition_expression
    rows: list | None = None
    tabs: list[TabSpec] | None = None
    description: str | None = None
    attrs: dict = field(default_factory=dict)
    """Passthrough of other EspoCRM panel keys (``noteText``, ``noteStyle``,
    ``dynamicLogicStyled`` …) preserved verbatim for lossless round-trip."""


@dataclass
class LayoutVariant:
    """A single role-scoped layout variant (Section 12.5.2).

    The variant form lets different roles see structurally different
    layouts for the same entity. A layout type (``detail`` or
    ``edit``) may be declared as a list of variants instead of as a
    single block; each variant carries a required ``forRoles:`` list
    and the standard panel (or column) payload.

    Per DEC-6, deploy of variant-form layouts is NOT_SUPPORTED on
    EspoCRM 9.x — the loader accepts the YAML but the layout_manager
    emits NOT_SUPPORTED status for any layout type using the variant
    form. The dataclass is populated for audit round-trip and future
    v1.4 deploy support.

    :param for_roles: List of role names this variant applies to.
        Per §12.5.2 coverage rule, every role declared in
        ``program.roles`` must appear in exactly one variant's
        ``for_roles`` for each variant-form layout type (enforced at
        validate_program time).
    :param panels: Panel list (for detail / edit variants).
    :param columns: Column list (for list variants — also
        NOT_SUPPORTED in v1.3 per DEC-6; populated for round-trip
        only).
    """

    for_roles: list[str]
    panels: list[PanelSpec] = field(default_factory=list)
    columns: list[ColumnSpec] = field(default_factory=list)


@dataclass
class LayoutSpec:
    """Layout definition for one layout type.

    The carried payload depends on the type's structure class
    (``espo_impl.core.layout_types``):

    - **PANELS** (``detail``/``edit``/``detailSmall``/``detailConvert``) →
      ``panels``.
    - **COLUMNS** (``list``/``listSmall``/``kanban``) → ``columns``.
    - **FIELD_LIST** (``filters``/``massUpdate``/``relationships``) → ``raw``
      holds a ``list[str]`` of names.
    - **PANEL_MAP** (``sidePanels*``/``bottomPanels*``) → ``raw`` holds the
      ``{name: cfg}`` mapping verbatim.

    A PANELS/COLUMNS layout may instead carry ``variants`` (variant form,
    §12.5.2) — never together with ``panels``/``columns``.

    :param layout_type: Any recognized EspoCRM layout type.
    :param panels: Panel list for PANELS-class layouts.
    :param columns: Column list for COLUMNS-class layouts.
    :param raw: Verbatim structure for FIELD_LIST (list) / PANEL_MAP (dict)
        layouts — passthrough fidelity with field-name normalization applied
        at build/reverse time only.
    :param variants: LayoutVariant list for variant-form layouts.
    """

    layout_type: str
    panels: list[PanelSpec] | None = None
    columns: list[ColumnSpec] | None = None
    raw: Any = None
    variants: list[LayoutVariant] = field(default_factory=list)

    def has_variants(self) -> bool:
        """True if this layout uses the variant form (§12.5.2)."""
        return bool(self.variants)


class EntityAction(Enum):
    """Action to perform on an entity."""

    NONE = "none"
    CREATE = "create"
    DELETE = "delete"
    DELETE_AND_CREATE = "delete_and_create"


# ``BasePlus`` (REQ-337 / PI-297) is a Base entity that also carries the
# Activities/History/Tasks panels — the deploy validator accepts it and the
# EntityManager passes it through to ``createEntity`` unchanged.
SUPPORTED_ENTITY_TYPES: set[str] = {"Base", "BasePlus", "Person", "Company", "Event"}

VALID_SETTINGS_KEYS: set[str] = {
    "labelSingular", "labelPlural", "stream", "disabled",
    "autoPlaceName",
    # Collection-level settings (PI-300 / REQ-340) — the entity's default
    # sort, its quick-search text-filter fields, and its full-text search
    # configuration. All live in EspoCRM's entityDefs.<Entity>.collection.
    "orderBy", "order", "textFilterFields",
    "fullTextSearch", "fullTextSearchMinLength",
}

# Valid values for settings.order (the default sort direction).
VALID_ORDER_VALUES: set[str] = {"asc", "desc"}

VALID_NORMALIZE_VALUES: set[str] = {
    "none", "lowercase-trim", "case-fold-trim", "e164",
}

VALID_ON_MATCH_VALUES: set[str] = {"block", "warn"}

# Scope-style action vocabulary used by scope_access read/edit/delete/stream
# (Section 12.3) and by system_permissions assignment_permission /
# user_permission (Section 12.4). ``not-set`` mirrors EspoCRM's value for "no
# explicit restriction" — admitted so a live role using it round-trips through
# YAML faithfully (audit/reconcile capture -> deploy -> re-audit stays a no-op).
SCOPE_ACCESS_VALUES: frozenset[str] = frozenset({"all", "team", "own", "no", "not-set"})

# v1.3 system-permissions key enumeration (Section 12.4). Two scope-style
# keys take SCOPE_ACCESS_VALUES; four flag-style keys take bool.
SYSTEM_PERMISSION_SCOPE_KEYS: frozenset[str] = frozenset({
    "assignment_permission",
    "user_permission",
})
SYSTEM_PERMISSION_FLAG_KEYS: frozenset[str] = frozenset({
    "export",
    "mass_update",
    "portal",
})
VALID_SYSTEM_PERMISSION_KEYS: frozenset[str] = (
    SYSTEM_PERMISSION_SCOPE_KEYS | SYSTEM_PERMISSION_FLAG_KEYS
)


@dataclass
class EntitySettings:
    """Typed representation of the entity-level ``settings:`` block.

    :param labelSingular: Singular display name for the entity.
    :param labelPlural: Plural display name for the entity.
    :param stream: Whether the activity-feed Stream panel is enabled.
    :param disabled: Whether the entity is disabled in the CRM UI.
    :param autoPlaceName: Whether LayoutManager auto-prepends the
        required system `name` field to detail/edit layouts when the
        YAML does not explicitly place it. Default True. Set False
        for entities whose `name` is computed via formula or
        workflow and should not surface as a manual input.
    :param orderBy: Default sort field for the entity's list view
        (EspoCRM ``collection.orderBy``). Deployed via the Entity
        Manager ``sortBy`` parameter.
    :param order: Default sort direction, ``"asc"`` or ``"desc"``
        (EspoCRM ``collection.order``). Deployed via ``sortDirection``.
    :param textFilterFields: Field names searched by the quick-search
        text filter (EspoCRM ``collection.textFilterFields``).
    :param fullTextSearch: Whether full-text search is enabled for the
        entity (EspoCRM ``collection.fullTextSearch``).
    :param fullTextSearchMinLength: Minimum query length before
        full-text search engages (EspoCRM
        ``collection.fullTextSearchMinLength``); ``None`` leaves the
        platform default.
    """

    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool | None = None
    disabled: bool | None = None
    autoPlaceName: bool | None = None
    orderBy: str | None = None
    order: str | None = None
    textFilterFields: list[str] | None = None
    fullTextSearch: bool | None = None
    fullTextSearchMinLength: int | None = None


@dataclass
class DuplicateCheck:
    """A single duplicate-detection rule from the ``duplicateChecks:`` block.

    :param id: Stable identifier for drift detection; unique within the entity.
    :param fields: Field names whose combined values must be unique.
    :param onMatch: Action on duplicate detection — ``block`` or ``warn``.
    :param message: User-facing message (required when onMatch is ``block``).
    :param normalize: Per-field normalization before comparison.
    :param alertTemplate: Email template ID to send on match.
    :param alertTo: Recipient — field name, literal email, or ``role:<role-id>``.
    """

    id: str
    fields: list[str]
    onMatch: str
    message: str | None = None
    normalize: dict[str, str] | None = None
    alertTemplate: str | None = None
    alertTo: str | None = None


@dataclass
class OrderByClause:
    """A single sort specification in a saved view.

    :param field: Field name to sort by.
    :param direction: Sort direction — ``asc`` or ``desc``.
    """

    field: str
    direction: str = "asc"


@dataclass
class SavedView:
    """A predefined list-view filter from the ``savedViews:`` block.

    :param id: Stable identifier for drift detection; unique within the entity.
    :param name: User-visible label shown in the CRM's list-view selector.
    :param description: Optional descriptive text.
    :param columns: Field names to show in display order.
    :param filter: Parsed condition expression AST (from Section 11).
    :param order_by: Sort specification(s).
    :param filter_raw: Original raw filter data (for round-tripping).
    """

    id: str
    name: str
    description: str | None = None
    columns: list[str] | None = None
    filter: Any = None  # ConditionNode from condition_expression
    order_by: list[OrderByClause] = field(default_factory=list)
    filter_raw: Any = None


@dataclass
class FilteredTab:
    """A left-navigation filtered list view from the ``filteredTabs:`` block.

    A filtered tab is the YAML representation of EspoCRM's "Report Filter
    plus custom scope" pattern: a Report Filter (Advanced Pack) defines
    the criteria, and three metadata files (scopes, clientDefs, i18n)
    register that filter as a top-level navigation entry. The
    :class:`FilteredTabManager` creates the Report Filter via API and
    emits the three metadata files into a deploy bundle for the operator
    to install.

    :param id: Stable identifier; unique within the entity.
    :param scope: PascalCase metadata scope name (no spaces). Becomes the
        filename for ``scopes/<scope>.json`` and ``clientDefs/<scope>.json``.
    :param label: Human-readable label that appears in the left nav and
        the Tab List configuration screen.
    :param filter: Parsed condition expression AST (Section 11). Reused
        verbatim for the Report Filter criteria.
    :param nav_order: Optional ordinal position in the Tab List; lower
        numbers sort earlier. None means "operator decides at install".
    :param acl: ACL strategy for the scope. Defaults to ``"boolean"``.
    :param report_filter_id: Populated at run time after the Report
        Filter is created via API; used to build ``defaultFilter:
        reportFilter<id>`` in the clientDef bundle file.
    :param filter_raw: Original raw filter data (for round-tripping).
    """

    id: str
    scope: str
    label: str
    filter: Any = None  # ConditionNode from condition_expression
    nav_order: int | None = None
    acl: str = "boolean"
    report_filter_id: str | None = None
    filter_raw: Any = None


@dataclass
class EmailTemplate:
    """An email template from the ``emailTemplates:`` block.

    :param id: Stable identifier; unique within the entity.
    :param name: Human-readable template name.
    :param entity: Entity the template operates against.
    :param subject: Subject line (may contain ``{{mergeField}}`` placeholders).
    :param body_file: Path to HTML body file, relative to program YAML.
    :param merge_fields: Field names used as merge placeholders.
    :param description: Optional business rationale.
    :param audience: Documentation hint for recipients (free-form in v1.1).
    :param body_content: Body HTML content (populated at load/validation time).
    :param body_hash: SHA-256 hash of body content (for drift detection).
    """

    id: str
    name: str
    entity: str
    subject: str
    body_file: str
    merge_fields: list[str]
    description: str | None = None
    audience: str | None = None
    body_content: str | None = None
    body_hash: str | None = None


@dataclass
class AggregateFormula:
    """An aggregate formula specification (count, sum, avg, min, max, first, last).

    :param function: Aggregate function name.
    :param related_entity: Name of the related entity to aggregate over.
    :param via: Relationship link name connecting to the related entity.
    :param field: Field to aggregate (required for sum/avg/min/max).
    :param pick_field: Field to pick (required for first/last).
    :param order_by: Sort specification (required for first/last).
    :param join: Multi-hop join path (list of dicts).
    :param where: Parsed condition expression for filtering.
    :param where_raw: Raw where clause data (for round-tripping).
    """

    function: str  # count, sum, avg, min, max, first, last
    related_entity: str
    via: str
    field: str | None = None
    pick_field: str | None = None
    order_by: Any = None  # OrderByClause or None (for first/last)
    join: list[dict] | None = None
    where: Any = None  # ConditionNode from condition_expression
    where_raw: Any = None


@dataclass
class ArithmeticFormula:
    """An arithmetic formula specification.

    :param expression: Raw arithmetic expression string.
    :param parsed: Parsed AST node from formula_parser.
    """

    expression: str
    parsed: Any = None  # ArithNode from formula_parser


@dataclass
class ConcatFormula:
    """A string-concatenation formula specification.

    :param parts: List of parts; each is ``{literal: str}``,
        ``{field: str}``, or ``{lookup: {via: str, field: str}}``.
    """

    parts: list[dict]


@dataclass
class Formula:
    """A parsed formula block attached to a field.

    Exactly one of ``aggregate``, ``arithmetic``, or ``concat`` is set.

    :param type: Formula type — ``"aggregate"``, ``"arithmetic"``, or ``"concat"``.
    :param aggregate: Aggregate formula details (when type is ``"aggregate"``).
    :param arithmetic: Arithmetic formula details (when type is ``"arithmetic"``).
    :param concat: Concatenation formula details (when type is ``"concat"``).
    """

    type: str  # "aggregate", "arithmetic", "concat"
    aggregate: AggregateFormula | None = None
    arithmetic: ArithmeticFormula | None = None
    concat: ConcatFormula | None = None


@dataclass
class WorkflowTrigger:
    """Trigger specification for a workflow rule.

    :param event: Trigger event — one of ``onCreate``, ``onUpdate``,
        ``onFieldChange``, ``onFieldTransition``, ``onDelete``.
    :param field: Field name (required for ``onFieldChange``/``onFieldTransition``).
    :param from_values: Source value(s) for ``onFieldTransition``.
    :param to_values: Target value(s) for ``onFieldChange``/``onFieldTransition``.
    """

    event: str  # onCreate, onUpdate, onFieldChange, onFieldTransition, onDelete
    field: str | None = None
    from_values: list[str] | str | None = None  # for onFieldTransition
    to_values: list[str] | str | None = None  # for onFieldChange/onFieldTransition


@dataclass
class WorkflowAction:
    """A single action within a workflow rule.

    :param type: Action type — ``setField``, ``clearField``, ``sendEmail``,
        or ``sendInternalNotification``.
    :param field: Target field (for ``setField``/``clearField``).
    :param value: Value to set (literal, ``"now"``, or arithmetic expression).
    :param template: Email template id reference (for send actions).
    :param to: Recipient (for send actions).
    """

    type: str  # setField, clearField, sendEmail, sendInternalNotification
    field: str | None = None
    value: Any = None
    template: str | None = None
    to: str | None = None


@dataclass
class Workflow:
    """A workflow rule from the ``workflows:`` block.

    :param id: Stable identifier for drift detection; unique within the entity.
    :param name: Human-readable workflow name.
    :param trigger: Trigger specification.
    :param where: Parsed condition expression AST.
    :param where_raw: Original raw where data (for round-tripping).
    :param actions: List of actions to execute.
    :param description: Optional business rationale.
    """

    id: str
    name: str
    trigger: WorkflowTrigger | None = None
    where: Any = None  # ConditionNode
    where_raw: Any = None
    actions: list[WorkflowAction] = field(default_factory=list)
    description: str | None = None


@dataclass
class EntityDefinition:
    """Entity definition from a YAML program file.

    :param name: Entity name (e.g., "Contact", "Engagement").
    :param fields: List of field definitions for this entity.
    :param action: Entity-level action (create, delete, delete_and_create, or none).
    :param type: Entity type for creation (Base, Person, Company, Event).
    :param labelSingular: Singular display name.
    :param labelPlural: Plural display name.
    :param stream: Whether to enable the Stream panel.
    :param disabled: Whether the entity is disabled.
    """

    name: str
    fields: list[FieldDefinition]
    action: EntityAction = EntityAction.NONE
    type: str | None = None
    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool = False
    disabled: bool = False
    layouts: dict[str, LayoutSpec] = field(default_factory=dict)
    description: str | None = None
    settings: EntitySettings | None = None
    duplicate_checks: list[DuplicateCheck] = field(default_factory=list)
    saved_views: list[SavedView] = field(default_factory=list)
    email_templates: list[EmailTemplate] = field(default_factory=list)
    workflows: list[Workflow] = field(default_factory=list)
    filtered_tabs: list[FilteredTab] = field(default_factory=list)
    settings_raw: dict | None = None
    duplicate_checks_raw: list | None = None
    saved_views_raw: list | None = None
    email_templates_raw: list | None = None
    workflows_raw: list | None = None
    filtered_tabs_raw: list | None = None


@dataclass
class RelationshipDefinition:
    """A relationship between two entities.

    :param name: Identifier for this relationship.
    :param entity: Primary entity (natural name).
    :param entity_foreign: Foreign entity (natural name).
    :param link_type: oneToMany, manyToOne, manyToMany, or oneToOne.
    :param link: Link name on the primary entity.
    :param link_foreign: Link name on the foreign entity.
    :param label: Panel label on the primary entity.
    :param label_foreign: Panel label on the foreign entity.
    """

    name: str
    entity: str
    entity_foreign: str
    link_type: str
    link: str
    link_foreign: str
    label: str
    label_foreign: str
    description: str | None = None
    relation_name: str | None = None
    audited: bool = False
    audited_foreign: bool = False
    action: str | None = None


@dataclass
class ScopeAccess:
    """Per-entity access scope for a role (Section 12.3).

    All fields default to the most-restrictive value (denied) so
    that an entity entry with omitted actions defaults to "no
    access for that action". The whitelist-semantics rule —
    entities not listed are denied entirely — is enforced at the
    role level, not in this dataclass.

    :param create: Whether the role may create new records of this
        entity. ``yes`` and ``no`` only (the record does not exist
        at create time, so ``team`` / ``own`` have no meaning).
    :param read: Which records the role may view. One of ``all``,
        ``team``, ``own``, ``no``.
    :param edit: Same vocabulary as ``read``, applied to record
        modification.
    :param delete: Same vocabulary as ``read``, applied to record
        deletion.
    :param stream: Same vocabulary as ``read``, applied to the
        record's activity stream.
    """

    create: bool = False
    read: str = "no"
    edit: str = "no"
    delete: str = "no"
    stream: str = "no"


@dataclass
class SystemPermissions:
    """System-level (non-entity) permissions for a role (Section 12.4).

    All fields default to the most-restrictive value (denied) per
    Section 12.4's "Omission defaults to deny" rule.

    :param assignment_permission: Whom the role may assign records
        to. One of ``all``, ``team``, ``own``, ``no``.
    :param user_permission: Which other users the role may view in
        the user directory. Same vocabulary as
        ``assignment_permission``.
    :param export: Whether the role may export records.
    :param mass_update: Whether the role may perform bulk updates.
    :param portal: Whether the role may log in via the customer
        portal interface.
    """

    assignment_permission: str = "no"
    user_permission: str = "no"
    export: bool = False
    mass_update: bool = False
    portal: bool = False


@dataclass
class RoleDefinition:
    """A role declared in the top-level ``roles:`` list.

    Roles declare entity-level scope access (Section 12.3) and
    system-level permissions (Section 12.4). The structured
    ``scope_access`` and ``system_permissions`` fields are
    populated by the loader's structured parsers; the
    ``*_raw`` passthroughs preserve the original YAML for
    round-tripping and audit-side reverse-engineering.

    :param name: Role identity. Unique across the program batch
        (uniqueness enforced via ``ProgramContext``).
    :param description: Business rationale for the role. Optional
        block-scalar prose; no schema interpretation.
    :param persona: Master PRD persona identifier (e.g.,
        ``MST-PER-005``). Documentation metadata only — the loader
        does not cross-check the identifier against any source
        (per DEC-178 / planning doc §9.1).
    :param scope_access: Per-entity access scope, keyed on entity
        natural name. Empty dict when the YAML has no
        ``scope_access:`` block or an empty one. Whitelist
        semantics — entities not present are denied entirely.
    :param system_permissions: Typed system-permissions block.
        ``None`` when the YAML omits the block (the deploy-side
        manager treats ``None`` as "every-flag-denied" by
        constructing a default ``SystemPermissions()``).
    :param scope_access_raw: Original raw per-entity access scope
        block from YAML. Preserved verbatim alongside the
        structured field.
    :param system_permissions_raw: Original raw system-level
        permissions block from YAML. Preserved verbatim alongside
        the structured field.
    """

    name: str
    description: str | None = None
    persona: str | None = None
    scope_access: dict[str, ScopeAccess] = field(default_factory=dict)
    system_permissions: SystemPermissions | None = None
    scope_access_raw: dict | None = None
    system_permissions_raw: dict | None = None


@dataclass
class TeamDefinition:
    """A team declared in the top-level ``teams:`` list.

    Teams group users for the purpose of team-level access scope
    on records (the ``team`` value in ``scope_access:``).
    Team-to-user assignment is runtime data managed in the target
    CRM admin UI, not in YAML.

    :param name: Team identity. Unique across the program batch
        (uniqueness enforced by a later prompt via
        ``ProgramContext``).
    :param description: Business rationale for the team. Optional
        block-scalar prose; no schema interpretation.
    """

    name: str
    description: str | None = None


class TeamStatus(Enum):
    """Outcome status for a team operation.

    Values mirror the canonical Status enum precedent. Team
    operations do not need ``DRIFT`` (there is only one mutable
    field — ``description`` — so a CHECK that detects difference
    is always reconcilable via PATCH) or ``NOT_SUPPORTED`` (Team
    is a native EspoCRM record type with full REST support).
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TeamResult:
    """Result of processing a single team.

    :param name: Team name from YAML (also the match key).
    :param status: Outcome status.
    :param team_id: Server-assigned record ID. Populated after
        a successful CREATE; available from CHECK on
        SKIPPED / UPDATED for already-existing teams.
    :param error: Error message if status is ERROR.
    """

    name: str
    status: TeamStatus
    team_id: str | None = None
    error: str | None = None


class RoleStatus(Enum):
    """Outcome status for a role operation.

    Uses the 5-value variant: CREATED / UPDATED / SKIPPED / ERROR /
    NOT_SUPPORTED. No DRIFT because the role manager always
    reconciles via PATCH; NOT_SUPPORTED reserved for any role whose
    declarations cannot be translated to EspoCRM (e.g., references
    to features not implemented in this workstream — currently
    none, but the slot leaves room for future schema additions).
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class RoleResult:
    """Result of processing a single role.

    :param name: Role name from YAML (also the match key).
    :param status: Outcome status.
    :param role_id: Server-assigned record ID. Populated after
        a successful CREATE; available from CHECK on
        SKIPPED / UPDATED for already-existing roles.
    :param error: Error message if status is ERROR.
    """

    name: str
    status: RoleStatus
    role_id: str | None = None
    error: str | None = None


class TooltipStatus(Enum):
    """Outcome status for a tooltip import operation."""

    UPDATED = "updated"
    SKIPPED = "skipped"
    NO_CHANGE = "no_change"
    ERROR = "error"


@dataclass
class TooltipResult:
    """Result of processing a single field tooltip."""

    entity: str
    field: str
    status: TooltipStatus
    error: str | None = None


class RelationshipStatus(Enum):
    """Outcome status for a relationship operation."""

    CREATED = "created"
    SKIPPED = "skipped"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class RelationshipResult:
    """Result of processing a single relationship."""

    name: str
    entity: str
    entity_foreign: str
    link: str
    status: RelationshipStatus
    verified: bool = False
    message: str | None = None


@dataclass
class ProgramFile:
    """Parsed YAML program file.

    :param version: Program file format version.
    :param description: Human-readable description.
    :param entities: List of entity definitions.
    :param source_path: Path to the source YAML file.
    :param relationships: List of relationship definitions.
    :param condition_warnings: Soft warnings raised during validation
        for ``requiredWhen`` / ``visibleWhen`` conditions that
        reference fields not yet present in the deployment batch.
        The referenced condition is dropped from the field's payload
        for this run; a re-run after the referenced field has been
        created will apply the condition.
    """

    version: str
    description: str
    entities: list[EntityDefinition]
    source_path: Path | None = None
    content_version: str = "1.0.0"
    relationships: list[RelationshipDefinition] = field(default_factory=list)
    roles: list[RoleDefinition] = field(default_factory=list)
    teams: list[TeamDefinition] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)
    condition_warnings: list[str] = field(default_factory=list)

    @property
    def has_delete_operations(self) -> bool:
        """Whether any entity in this program has a delete action."""
        return any(
            e.action in (EntityAction.DELETE, EntityAction.DELETE_AND_CREATE)
            for e in self.entities
        )


@dataclass(frozen=True)
class ProgramContext:
    """Cross-file context used during validation.

    A deployment batch is a set of YAML program files all targeting
    the same EspoCRM instance. Domain-owned YAMLs commonly extend
    a shared native entity (Contact, Account, etc.) with
    domain-specific fields, and reference each others' fields via
    requiredWhen, visibleWhen, panel conditions, savedView filters,
    filteredTab conditions, and workflow conditions.

    ``ProgramContext`` exposes the union of field names per entity
    across the entire batch, so single-file validation can resolve
    references that are satisfied by sibling files. It also tracks
    cross-batch role/team/entity name sets and per-name occurrence
    counts so cross-block validators (``_validate_roles``,
    ``_validate_teams``) can detect duplicate identifiers and
    resolve entity-name references inside ``scope_access:`` blocks
    against the union of all entities declared anywhere in the
    batch.

    :param fields_by_entity: Mapping of entity natural name (e.g.
        ``Contact``, ``Account``, ``Engagement``) to the set of all
        field names declared for that entity across the batch.
        Custom-entity names appear in their natural form (without
        the ``C`` prefix EspoCRM applies on the wire).
    :param categories_by_entity: Mapping of entity natural name to
        the set of all field ``category`` values declared for that
        entity across the batch. Used by ``_validate_layout`` to
        resolve ``TabSpec.category`` references against the union
        of categories from every YAML in the deploy batch — a
        layout in YAML A can reference a category declared by a
        field in YAML B as long as both sit in the same batch.
        Empty-string and ``None`` categories are excluded.
    :param entity_names: Frozenset of every entity natural name
        declared in the batch. Subset of
        ``fields_by_entity.keys()`` when every entity declares at
        least one field; can be strictly larger if a program lists
        an entity with no ``fields:`` block.
    :param role_names: Frozenset of every role name declared in
        the batch (deduplicated).
    :param team_names: Frozenset of every team name declared in
        the batch (deduplicated).
    :param role_count_by_name: Mapping of role name to the number
        of times it appears across the batch. A value > 1 marks a
        cross-batch duplicate.
    :param team_count_by_name: Mapping of team name to the number
        of times it appears across the batch. A value > 1 marks a
        cross-batch duplicate.
    :param server_fields_by_entity: Mapping of entity natural name to
        the set of field names already present on the live target
        instance (discovered via the Metadata API at Configure time),
        keyed and normalised to the same natural form as
        ``fields_by_entity`` — custom fields with their ``c`` prefix
        stripped. Lets a field reference resolve against a field that
        was created by an earlier deploy or by a sibling YAML not in
        the current batch, instead of being rejected. Empty when no
        instance is connected or discovery failed (batch-only
        behaviour).
    """

    fields_by_entity: dict[str, frozenset[str]]
    categories_by_entity: dict[str, frozenset[str]] = field(
        default_factory=dict
    )
    entity_names: frozenset[str] = frozenset()
    role_names: frozenset[str] = frozenset()
    team_names: frozenset[str] = frozenset()
    role_count_by_name: dict[str, int] = field(default_factory=dict)
    team_count_by_name: dict[str, int] = field(default_factory=dict)
    server_fields_by_entity: dict[str, frozenset[str]] = field(
        default_factory=dict
    )

    def field_names_for(self, entity_name: str) -> frozenset[str]:
        """Return the union of known field names for ``entity_name``.

        Combines fields declared anywhere in the deploy batch with
        fields already present on the live target instance (when an
        instance was connected at Configure time). The server-side
        union is why a reference to a field deployed by an earlier
        run — or by a YAML outside this batch — resolves instead of
        being rejected.

        :param entity_name: Entity natural name.
        :returns: Frozenset of field names, or an empty frozenset if
            neither the batch nor the live instance contributes any
            fields for the named entity.
        """
        return self.fields_by_entity.get(
            entity_name, frozenset()
        ) | self.server_fields_by_entity.get(entity_name, frozenset())

    def field_categories_for(self, entity_name: str) -> frozenset[str]:
        """Return the union of declared field categories for ``entity_name``.

        Categories are the YAML-side grouping label fields use to
        populate tabbed layouts (``TabSpec.category``). The validator
        resolves a ``TabSpec.category`` reference against the union
        of categories declared on the named entity in every YAML in
        the deploy batch, mirroring the cross-file resolution model
        already in place for field names.

        :param entity_name: Entity natural name.
        :returns: Frozenset of category strings, or an empty frozenset
            if no program in this context declares any categories on
            the named entity.
        """
        return self.categories_by_entity.get(entity_name, frozenset())

    @classmethod
    def from_programs(
        cls,
        programs: list["ProgramFile"],
        server_fields_by_entity: dict[str, frozenset[str]] | None = None,
    ) -> "ProgramContext":
        """Build a context from a list of parsed programs.

        Iterates every entity in every program and unions field
        names by entity natural name. Self-referential — a single
        program counted in this context will have all of its own
        fields available too, so callers can pass a single program
        and use the same code path.

        Roles and teams are accumulated with counts so callers can
        detect cross-batch duplicates by checking for entries with
        ``count > 1``.

        :param programs: List of parsed programs to union.
        :param server_fields_by_entity: Optional mapping of entity
            natural name to field names already present on the live
            target instance (natural form, ``c`` prefix stripped). When
            supplied, references to these fields resolve during
            validation even if no YAML in the batch declares them. None
            or empty preserves batch-only behaviour.
        :returns: New ``ProgramContext``.
        """
        fields_by_entity: dict[str, set[str]] = defaultdict(set)
        categories_by_entity: dict[str, set[str]] = defaultdict(set)
        entity_names: set[str] = set()
        role_counts: dict[str, int] = defaultdict(int)
        team_counts: dict[str, int] = defaultdict(int)
        for program in programs:
            for entity in program.entities:
                entity_names.add(entity.name)
                for field_def in entity.fields:
                    fields_by_entity[entity.name].add(field_def.name)
                    if field_def.category:
                        categories_by_entity[entity.name].add(
                            field_def.category
                        )
            for role in program.roles:
                role_counts[role.name] += 1
            for team in program.teams:
                team_counts[team.name] += 1
        return cls(
            fields_by_entity={
                k: frozenset(v) for k, v in fields_by_entity.items()
            },
            categories_by_entity={
                k: frozenset(v) for k, v in categories_by_entity.items()
            },
            entity_names=frozenset(entity_names),
            role_names=frozenset(role_counts.keys()),
            team_names=frozenset(team_counts.keys()),
            role_count_by_name=dict(role_counts),
            team_count_by_name=dict(team_counts),
            server_fields_by_entity=dict(server_fields_by_entity or {}),
        )


class EntityLayoutStatus(Enum):
    """Outcome status for a layout operation."""

    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFICATION_FAILED = "verification_failed"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class LayoutResult:
    """Result of processing a single layout."""

    entity: str
    layout_type: str
    status: EntityLayoutStatus
    verified: bool = False
    error: str | None = None


@dataclass
class NotSupportedRoleClauseRecord:
    """A field or panel whose visibleWhen contained role clauses and so
    was skipped at deploy time (DEC-6 — deferred to v1.4).

    The owning field or panel still deploys normally; only the
    dynamic-logic visibility block is omitted from the payload.
    The record exists so the run report can surface affected
    items in the MANUAL CONFIGURATION REQUIRED advisory block.

    :param entity_name: Owning entity name.
    :param field_name: Field name, or panel label when ``is_panel``
        is True.
    :param is_panel: True for panel-level visibleWhen, False for
        field-level visibleWhen.
    :param reason: Human-readable explanation surfaced in the
        advisory block.
    """

    entity_name: str
    field_name: str
    is_panel: bool = False
    reason: str = (
        "visibleWhen contains role clauses; EspoCRM 9.x Dynamic Logic "
        "has no role-condition type (DEC-6 — deferred to v1.4)"
    )


class SettingsStatus(Enum):
    """Outcome status for an entity settings operation."""

    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class SettingsResult:
    """Result of applying settings for a single entity."""

    entity: str
    status: SettingsStatus
    changes: list[str] | None = None
    error: str | None = None


class DuplicateCheckStatus(Enum):
    """Outcome status for a duplicate-check rule operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class DuplicateCheckResult:
    """Result of processing a single duplicate-check rule."""

    entity: str
    rule_id: str
    status: DuplicateCheckStatus
    error: str | None = None


class EmailTemplateStatus(Enum):
    """Outcome status for an email-template operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"


@dataclass
class EmailTemplateResult:
    """Result of processing a single email template."""

    entity: str
    template_id: str
    status: EmailTemplateStatus
    error: str | None = None


class SavedViewStatus(Enum):
    """Outcome status for a saved-view operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class SavedViewResult:
    """Result of processing a single saved view."""

    entity: str
    view_id: str
    status: SavedViewStatus
    error: str | None = None


class FilteredTabStatus(Enum):
    """Outcome status for a filtered-tab operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class FilteredTabResult:
    """Result of processing a single filtered tab.

    :param entity: Natural entity name (e.g., "Engagement").
    :param tab_id: The YAML ``id`` for this tab.
    :param scope: The PascalCase scope name from YAML.
    :param status: Outcome status.
    :param report_filter_id: Populated after a successful API create.
    :param error: Error message if status is ERROR.
    """

    entity: str
    tab_id: str
    scope: str
    status: FilteredTabStatus
    report_filter_id: str | None = None
    error: str | None = None


class WorkflowStatus(Enum):
    """Outcome status for a workflow operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    DRIFT = "drift"
    ERROR = "error"
    NOT_SUPPORTED = "not_supported"


@dataclass
class WorkflowResult:
    """Result of processing a single workflow."""

    entity: str
    workflow_id: str
    status: WorkflowStatus
    error: str | None = None


class FieldStatus(Enum):
    """Outcome status for a single field operation."""

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFIED = "verified"
    VERIFICATION_FAILED = "verification_failed"
    SKIPPED_TYPE_CONFLICT = "skipped_type_conflict"
    ERROR = "error"


@dataclass
class FieldResult:
    """Result of processing a single field.

    :param entity: Entity name.
    :param field: Field name.
    :param status: Outcome status.
    :param verified: Whether post-action verification passed.
    :param changes: List of changed property names (for updates).
    :param error: Error message if status is ERROR.
    """

    entity: str
    field: str
    status: FieldStatus
    verified: bool = False
    changes: list[str] | None = None
    error: str | None = None


@dataclass
class RunSummary:
    """Aggregate summary of a run or verify operation."""

    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    verification_failed: int = 0
    errors: int = 0
    layouts_updated: int = 0
    layouts_skipped: int = 0
    layouts_failed: int = 0
    relationships_created: int = 0
    relationships_skipped: int = 0
    relationships_failed: int = 0
    tooltips_updated: int = 0
    tooltips_skipped: int = 0
    tooltips_failed: int = 0
    settings_updated: int = 0
    settings_skipped: int = 0
    settings_failed: int = 0
    duplicate_checks_created: int = 0
    duplicate_checks_updated: int = 0
    duplicate_checks_skipped: int = 0
    duplicate_checks_drift: int = 0
    duplicate_checks_failed: int = 0
    saved_views_created: int = 0
    saved_views_updated: int = 0
    saved_views_skipped: int = 0
    saved_views_drift: int = 0
    saved_views_failed: int = 0
    email_templates_created: int = 0
    email_templates_updated: int = 0
    email_templates_skipped: int = 0
    email_templates_drift: int = 0
    email_templates_failed: int = 0
    workflows_created: int = 0
    workflows_updated: int = 0
    workflows_skipped: int = 0
    workflows_drift: int = 0
    workflows_failed: int = 0
    filtered_tabs_created: int = 0
    filtered_tabs_skipped: int = 0
    filtered_tabs_drift: int = 0
    filtered_tabs_failed: int = 0
    filtered_tabs_not_supported: int = 0


class StepStatus(Enum):
    """Per-step pipeline outcome status used by RunWorker.

    NO_WORK is distinct from SKIPPED: NO_WORK means the YAML
    declared nothing for this step (a legitimate, by-design
    outcome), whereas SKIPPED means the user explicitly opted
    out of the step (e.g. via the field-update-mode flag that
    bypasses entity deletions). Both render in gray in the
    STEP SUMMARY block but with different labels so an operator
    reading the log can tell the two cases apart at a glance.
    """

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    NO_WORK = "no_work"


@dataclass
class StepResult:
    """Outcome of one phase in the RunWorker pipeline.

    :param step_name: Canonical snake_case step name (e.g.
        ``"saved_views"``, ``"fields"``).
    :param status: OK, FAILED, or SKIPPED.
    :param error: Human-readable error detail when status is FAILED.
    :param details: Optional extra metadata about the step.
    """

    step_name: str
    status: StepStatus
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    """Complete report for a run or verify operation.

    :param timestamp: ISO 8601 timestamp of the operation.
    :param instance_name: Name of the target instance.
    :param espocrm_url: URL of the target instance.
    :param program_file: Name of the program file used.
    :param operation: Either "run" or "verify".
    :param summary: Aggregate result counts.
    :param results: Per-field results.
    """

    timestamp: str
    instance_name: str
    espocrm_url: str
    program_file: str
    operation: str
    content_version: str = ""
    summary: RunSummary = field(default_factory=RunSummary)
    results: list[FieldResult] = field(default_factory=list)
    layout_results: list[LayoutResult] = field(default_factory=list)
    relationship_results: list[RelationshipResult] = field(default_factory=list)
    tooltip_results: list[TooltipResult] = field(default_factory=list)
    settings_results: list[SettingsResult] = field(default_factory=list)
    duplicate_check_results: list[DuplicateCheckResult] = field(default_factory=list)
    saved_view_results: list[SavedViewResult] = field(default_factory=list)
    email_template_results: list[EmailTemplateResult] = field(default_factory=list)
    workflow_results: list[WorkflowResult] = field(default_factory=list)
    filtered_tab_results: list[FilteredTabResult] = field(default_factory=list)
    step_results: list[StepResult] = field(default_factory=list)
    not_supported_role_clauses: list[NotSupportedRoleClauseRecord] = field(
        default_factory=list,
    )


