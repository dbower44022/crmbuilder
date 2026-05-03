"""Data models for CRM Builder."""

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


@dataclass
class TabSpec:
    """A sub-tab within a panel, populated by field category."""

    label: str
    category: str
    rows: list | None = None


@dataclass
class ColumnSpec:
    """A column in a list view layout."""

    field: str
    width: int | None = None


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


@dataclass
class LayoutSpec:
    """Layout definition for one layout type (detail, edit, or list)."""

    layout_type: str
    panels: list[PanelSpec] | None = None
    columns: list[ColumnSpec] | None = None


class EntityAction(Enum):
    """Action to perform on an entity."""

    NONE = "none"
    CREATE = "create"
    DELETE = "delete"
    DELETE_AND_CREATE = "delete_and_create"


SUPPORTED_ENTITY_TYPES: set[str] = {"Base", "Person", "Company", "Event"}

VALID_SETTINGS_KEYS: set[str] = {
    "labelSingular", "labelPlural", "stream", "disabled",
    "autoPlaceName",
}

VALID_NORMALIZE_VALUES: set[str] = {
    "none", "lowercase-trim", "case-fold-trim", "e164",
}

VALID_ON_MATCH_VALUES: set[str] = {"block", "warn"}


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
    """

    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool | None = None
    disabled: bool | None = None
    autoPlaceName: bool | None = None


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
    :param link_type: oneToMany, manyToOne, or manyToMany.
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
    """

    version: str
    description: str
    entities: list[EntityDefinition]
    source_path: Path | None = None
    content_version: str = "1.0.0"
    relationships: list[RelationshipDefinition] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)

    @property
    def has_delete_operations(self) -> bool:
        """Whether any entity in this program has a delete action."""
        return any(
            e.action in (EntityAction.DELETE, EntityAction.DELETE_AND_CREATE)
            for e in self.entities
        )


class EntityLayoutStatus(Enum):
    """Outcome status for a layout operation."""

    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFICATION_FAILED = "verification_failed"
    ERROR = "error"


@dataclass
class LayoutResult:
    """Result of processing a single layout."""

    entity: str
    layout_type: str
    status: EntityLayoutStatus
    verified: bool = False
    error: str | None = None


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
    """Per-step pipeline outcome status used by RunWorker."""

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"


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


