# CRM Builder — YAML Schema Implementation Reference

**Version:** 1.2.2
**Status:** Current
**Last Updated:** 05-03-26
**Requirements:** PRDs/product/app-yaml-schema.md (v1.2.2)
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of YAML program-file
parsing, validation, and the in-memory data models that represent
program-file contents. It covers `core/config_loader.py`,
`core/models.py`, and the supporting parsers
(`core/condition_expression.py`, `core/relative_date.py`,
`core/formula_parser.py`).

### Companion product spec

The product specification for the schema — the YAML shape,
property tables, and semantic validation rules — lives in
`PRDs/product/app-yaml-schema.md`. That PRD is the contract; this
doc is the map of the code that satisfies it. They are maintained
as a pair.

### Keeping this impl doc and the PRD in sync

The PRD (`PRDs/product/app-yaml-schema.md`) is the **single source
of truth** for the schema's shape and its semantic validation rules.
This doc deliberately does **not** restate those rules — Section 4.6
is a function-name index that points back at PRD Section 10 instead.
This is intentional, to remove the drift surface that exists when
two docs carry the same rule list.

When you change the code — adding a new entity-level block, renaming
a validator function, introducing a new AST node, etc. — make a
matching update to the PRD in the same change set:

- New entity-level block (e.g., a future `reports:`) → write the
  PRD's Section 5.x (YAML form, property table, semantic rules) and
  add the rule list to PRD Section 10 *first*. Then come back here
  and add the dataclass to Section 3, the function-name entries to
  Section 4, and the test file to Section 7. Section 8 below has
  the full step-by-step recipe.
- Changed validation rule → update the rule's wording in PRD
  Section 10. No edit to this doc's rule text is required (this doc
  has none); only verify the function-name index in Section 4.6
  still names the validator that enforces the rule.
- Renamed validator function or moved code → update the
  function-name references in this doc's Section 4 and Section 4.6.
- New shared parser or AST node → add to this doc's Section 5 and
  describe its grammar / vocabulary in PRD Section 11.
- New `*Status` / `*Result` types or `RunSummary` counters → add
  to this doc's Section 3.10.

Every change bumps both this doc's version stamp + revision history
**and** the PRD's. Do them together — drift always starts with one
doc moving forward alone.

---

## 2. File Locations

```
espo_impl/core/config_loader.py        # YAML parsing + validation
espo_impl/core/models.py               # Data models for parsed contents
espo_impl/core/condition_expression.py # Section 11 filter AST
espo_impl/core/relative_date.py        # Section 11.4 token vocabulary
espo_impl/core/formula_parser.py       # Section 6.x arithmetic AST
```

The deploy-time managers that consume the parsed models live in
`core/*_manager.py` and are documented in their own impl docs (e.g.,
`impl-fields.md`, `impl-layouts.md`).

---

## 3. Data Models (`core/models.py`)

Models are `@dataclass` types. Optional scalar properties default to
`None` so the comparator can distinguish "not specified in YAML" from
"explicitly set to a value." Optional collections default to empty
lists/dicts via `field(default_factory=...)`.

### 3.1 Profile + roles

```python
class InstanceRole(Enum):
    SOURCE = "source"   # audit-only
    TARGET = "target"   # configure / deploy
    BOTH   = "both"

@dataclass
class InstanceProfile:
    name: str
    url: str
    api_key: str
    auth_method: str = "api_key"      # "api_key", "hmac", or "basic"
    secret_key: str | None = None
    project_folder: str | None = None
    role: InstanceRole = InstanceRole.TARGET

    @property
    def api_url(self) -> str: ...      # f"{url.rstrip('/')}/api/v1"
    @property
    def slug(self) -> str: ...
    @property
    def programs_dir(self) -> Path | None: ...
    @property
    def reports_dir(self) -> Path | None: ...
    @property
    def docs_dir(self) -> Path | None: ...
```

The three directory properties return `None` when `project_folder` is
not set; callers fall back to cwd-relative paths.

### 3.2 Top-level container

```python
@dataclass
class ProgramFile:
    version: str
    description: str
    entities: list[EntityDefinition]
    source_path: Path | None = None
    content_version: str = "1.0.0"
    relationships: list[RelationshipDefinition] = field(default_factory=list)
    deprecation_warnings: list[str] = field(default_factory=list)

    @property
    def has_delete_operations(self) -> bool: ...
```

`deprecation_warnings` is populated at load time when v1.0 top-level
keys (`labelSingular`, `labelPlural`, `stream`, `disabled`,
panel-level `dynamicLogicVisible`) are merged forward into their v1.1
locations (see Section 4.5).

### 3.3 Entity-level

```python
class EntityAction(Enum):
    NONE = "none"
    CREATE = "create"
    DELETE = "delete"
    DELETE_AND_CREATE = "delete_and_create"

@dataclass
class EntityDefinition:
    # Core
    name: str
    fields: list[FieldDefinition]
    action: EntityAction = EntityAction.NONE
    type: str | None = None
    description: str | None = None

    # Settings (v1.0 top-level form, kept for back-compat;
    # canonical location is the EntitySettings block)
    labelSingular: str | None = None
    labelPlural: str | None = None
    stream: bool = False
    disabled: bool = False

    # Layouts
    layouts: dict[str, LayoutSpec] = field(default_factory=dict)

    # v1.1+ blocks (parsed)
    settings: EntitySettings | None = None
    duplicate_checks: list[DuplicateCheck] = field(default_factory=list)
    saved_views: list[SavedView] = field(default_factory=list)
    email_templates: list[EmailTemplate] = field(default_factory=list)
    workflows: list[Workflow] = field(default_factory=list)
    filtered_tabs: list[FilteredTab] = field(default_factory=list)

    # v1.1+ blocks (raw, for round-tripping / audit)
    settings_raw: dict | None = None
    duplicate_checks_raw: list | None = None
    saved_views_raw: list | None = None
    email_templates_raw: list | None = None
    workflows_raw: list | None = None
    filtered_tabs_raw: list | None = None
```

`settings.*` is the canonical location for `labelSingular`,
`labelPlural`, `stream`, and `disabled` in v1.1+. The top-level
fields are populated by the deprecation merge (Section 4.5) so that
managers reading either location continue to work.

### 3.4 Field-level

```python
@dataclass
class FieldDefinition:
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

    # v1.1+ field-level extensions
    required_when_raw: list | dict | None = None
    visible_when_raw: list | dict | None = None
    required_when: Any = None         # ConditionNode
    visible_when: Any = None          # ConditionNode
    formula: Formula | None = None
    formula_raw: dict | None = None
    externally_populated: bool = False
```

The parsed `required_when` / `visible_when` / `formula.aggregate.where`
forms reference AST node types from
`core/condition_expression.py` (`LeafClause`, `AllNode`, `AnyNode`).

### 3.5 Settings, duplicate checks, saved views

```python
VALID_SETTINGS_KEYS  = {"labelSingular", "labelPlural", "stream", "disabled"}
VALID_NORMALIZE_VALUES = {"none", "lowercase-trim", "case-fold-trim", "e164"}
VALID_ON_MATCH_VALUES  = {"block", "warn"}

@dataclass
class EntitySettings:
    labelSingular: str | None = None
    labelPlural:   str | None = None
    stream:        bool | None = None
    disabled:      bool | None = None

@dataclass
class DuplicateCheck:
    id: str
    fields: list[str]
    onMatch: str                       # "block" | "warn"
    message: str | None = None
    normalize: dict[str, str] | None = None
    alertTemplate: str | None = None   # email template id
    alertTo: str | None = None         # field | email | role:<id>

@dataclass
class OrderByClause:
    field: str
    direction: str = "asc"             # "asc" | "desc"

@dataclass
class SavedView:
    id: str
    name: str
    description: str | None = None
    columns: list[str] | None = None
    filter: Any = None                 # ConditionNode
    order_by: list[OrderByClause] = field(default_factory=list)
    filter_raw: Any = None             # round-trip
```

### 3.6 Filtered tabs (v1.2)

```python
@dataclass
class FilteredTab:
    id: str
    scope: str                         # PascalCase, globally unique
    label: str
    filter: Any = None                 # ConditionNode
    nav_order: int | None = None
    acl: str = "boolean"               # "boolean" | "team" | "strict"
    report_filter_id: str | None = None  # populated at run time
    filter_raw: Any = None
```

`report_filter_id` is set by `core/filtered_tab_manager.py` after the
Report Filter record is created over `/api/v1/ReportFilter`. It is
not populated during loading; the loader leaves it as `None`.

### 3.7 Email templates and workflows

```python
@dataclass
class EmailTemplate:
    id: str
    name: str
    entity: str
    subject: str
    body_file: str
    merge_fields: list[str]
    description: str | None = None
    audience: str | None = None
    body_content: str | None = None    # populated at load time
    body_hash: str | None = None       # SHA-256 of body_content

@dataclass
class WorkflowTrigger:
    event: str                         # onCreate | onUpdate | onFieldChange
                                       # | onFieldTransition | onDelete
    field: str | None = None
    from_values: list[str] | str | None = None  # onFieldTransition
    to_values:   list[str] | str | None = None  # onFieldChange / onFieldTransition

@dataclass
class WorkflowAction:
    type: str                          # setField | clearField | sendEmail
                                       # | sendInternalNotification
    field: str | None = None
    value: Any = None
    template: str | None = None        # email template id
    to: str | None = None              # field | email | role:<id> | user:<id>

@dataclass
class Workflow:
    id: str
    name: str
    trigger: WorkflowTrigger | None = None
    where: Any = None                  # ConditionNode
    where_raw: Any = None
    actions: list[WorkflowAction] = field(default_factory=list)
    description: str | None = None
```

### 3.8 Formulas

```python
@dataclass
class AggregateFormula:
    function: str                      # count | sum | avg | min | max | first | last
    related_entity: str
    via: str                           # relationship link name
    field: str | None = None           # required for sum/avg/min/max
    pick_field: str | None = None      # required for first/last
    order_by: OrderByClause | None = None
    join: list[dict] | None = None     # multi-hop path
    where: Any = None                  # ConditionNode
    where_raw: Any = None

@dataclass
class ArithmeticFormula:
    expression: str
    parsed: Any = None                 # ArithNode from formula_parser

@dataclass
class ConcatFormula:
    parts: list[dict]                  # {literal} | {field} | {lookup: {via, field}}

@dataclass
class Formula:
    type: str                          # "aggregate" | "arithmetic" | "concat"
    aggregate:  AggregateFormula  | None = None
    arithmetic: ArithmeticFormula | None = None
    concat:     ConcatFormula     | None = None
```

### 3.9 Layouts and relationships

```python
@dataclass
class TabSpec:
    label: str
    category: str
    rows: list | None = None

@dataclass
class ColumnSpec:
    field: str
    width: int | None = None

@dataclass
class PanelSpec:
    label: str
    tabBreak: bool = False
    tabLabel: str | None = None
    style: str = "default"
    hidden: bool = False
    dynamicLogicVisible: dict | None = None    # deprecated v1.1
    visible_when_raw: list | dict | None = None
    visible_when: Any = None                   # ConditionNode
    rows: list | None = None
    tabs: list[TabSpec] | None = None
    description: str | None = None

@dataclass
class LayoutSpec:
    layout_type: str                   # "detail" | "edit" | "list"
    panels: list[PanelSpec] | None = None
    columns: list[ColumnSpec] | None = None

@dataclass
class RelationshipDefinition:
    name: str
    entity: str
    entity_foreign: str
    link_type: str                     # oneToMany | manyToOne | manyToMany
    link: str
    link_foreign: str
    label: str
    label_foreign: str
    description: str | None = None
    relation_name: str | None = None   # required for manyToMany
    audited: bool = False
    audited_foreign: bool = False
    action: str | None = None          # None = deploy, "skip" = record only
```

### 3.10 Result + status types

Each manager emits a per-item `*Result` and a `*Status` enum.
Aggregated counts live on `RunSummary`; the per-step pipeline outcome
is `StepResult`/`StepStatus`. The umbrella container is `RunReport`.
The full list (kept here for greppability):

| Status enum | Result dataclass | Owner |
|---|---|---|
| `FieldStatus` | `FieldResult` | `field_manager.py` |
| `EntityLayoutStatus` | `LayoutResult` | `layout_manager.py` |
| `RelationshipStatus` | `RelationshipResult` | `relationship_manager.py` |
| `TooltipStatus` | `TooltipResult` | `tooltip_manager.py` |
| `SettingsStatus` | `SettingsResult` | `entity_settings_manager.py` |
| `DuplicateCheckStatus` | `DuplicateCheckResult` | `duplicate_check_manager.py` |
| `SavedViewStatus` | `SavedViewResult` | `saved_view_manager.py` |
| `EmailTemplateStatus` | `EmailTemplateResult` | `email_template_manager.py` |
| `WorkflowStatus` | `WorkflowResult` | `workflow_manager.py` |
| `FilteredTabStatus` | `FilteredTabResult` | `filtered_tab_manager.py` |
| `StepStatus` | `StepResult` | `workers/run_worker.py` |

Statuses include `NOT_SUPPORTED` for any rule whose deploy artifact
cannot be written via REST (saved views, duplicate checks, workflows,
filtered tabs when the Advanced Pack is missing). The run worker
collects these into a `MANUAL CONFIGURATION REQUIRED` block at the
end of the run.

---

## 4. Config Loader (`core/config_loader.py`)

### 4.1 Public API

```python
class ConfigLoader:
    def load_program(self, path: Path) -> ProgramFile:
        """Parse a YAML file. Raises ValueError on YAML syntax errors."""

    def validate_program(self, program: ProgramFile) -> list[str]:
        """Return a list of human-readable error strings; empty = valid."""
```

The two phases are separate so the UI can show a parse error before
running validation, and so tests can validate hand-built `ProgramFile`
fixtures without going through YAML. There is no `load_program_file`
free function.

Parsing uses `yaml.safe_load`. All v1.1+ blocks are stored in both
parsed (`saved_views`) and raw (`saved_views_raw`) form on the entity;
the raw copy lets the audit and reporter modules round-trip without
re-serializing the AST.

### 4.2 Vocabulary constants

```python
SUPPORTED_FIELD_TYPES = {
    "varchar", "text", "wysiwyg", "enum", "multiEnum",
    "bool", "int", "float", "date", "datetime",
    "currency", "url", "email", "phone",
}
ENUM_TYPES        = {"enum", "multiEnum"}
VALID_ACTIONS     = {"create", "delete", "delete_and_create"}
VALID_LAYOUT_TYPES = {"detail", "edit", "list"}
VALID_LINK_TYPES   = {"oneToMany", "manyToOne", "manyToMany"}
SUPPORTED_ENTITY_TYPES = {"Base", "Person", "Company", "Event"}  # in models.py
```

### 4.3 Parse pipeline

`load_program(path)` calls these helpers in order:

1. `yaml.safe_load(path.read_text())`
2. `_parse_field` — per field
3. `_parse_layout` / `_parse_panel` / `_parse_tab` / `_parse_column`
4. `_parse_settings` — entity-level settings block
5. `_deprecation_merge` — moves v1.0 top-level keys into `settings:`,
   appends a warning to `ProgramFile.deprecation_warnings`
6. `_parse_duplicate_checks`
7. `_parse_saved_views`
8. `_parse_email_templates` — also reads body files relative to the
   YAML, computes SHA-256 into `body_hash`
9. `_parse_workflows` (with `_parse_trigger`, `_parse_action`)
10. `_parse_filtered_tabs`
11. `_parse_relationship` — per relationship
12. `_parse_formula` (with `_parse_aggregate_formula`,
    `_parse_arithmetic_formula`, `_parse_concat_formula`)

Condition-expression filters (`requiredWhen`, `visibleWhen`,
`savedViews[].filter`, `workflows[].where`, `filteredTabs[].filter`,
`formula.aggregate.where`) are parsed by `parse_condition()` from
`core/condition_expression.py`. A `ValueError` from the parser is
swallowed at parse time; the same input is re-parsed in the
validator so the user sees a single canonical error message.

Arithmetic formulas are parsed by `parse_arithmetic()` from
`core/formula_parser.py`, which produces an `ArithNode` AST. Field
references are extracted with `extract_field_refs()` for downstream
validation.

### 4.4 Validate pipeline

`validate_program(program)` calls per-entity, per-relationship, and
program-level validators:

```
validate_program
├── _validate_entity (per entity)
│   ├── (top-level entity rules)
│   ├── _validate_field (per field)
│   ├── _validate_field_conditions   # requiredWhen, visibleWhen
│   ├── _validate_formula_fields     # delegates to _validate_formula
│   ├── _validate_settings
│   ├── _validate_duplicate_checks   #  + _validate_alert_to
│   ├── _validate_saved_views
│   ├── _validate_email_templates
│   ├── _validate_workflows          #  + _validate_workflow_trigger
│   │                                #  + _validate_workflow_action
│   ├── _validate_filtered_tabs
│   └── _validate_layout (per layout)
├── _validate_alert_template_refs    # cross-block: dup checks → templates
├── _validate_workflow_template_refs # cross-block: workflows → templates
├── _validate_filtered_tab_scopes    # cross-entity scope uniqueness
└── _validate_relationship (per relationship)
```

All validators return `list[str]`. The aggregator concatenates them
in declaration order and the UI renders them line-by-line. Validation
failure prevents Run from proceeding; preview/verify skips validation
errors that are non-fatal at read time but uses the same rules.

### 4.5 Deprecation merge

`_deprecation_merge(entity_name, entity_data, settings, warnings)`
moves the four v1.0 top-level keys (`labelSingular`, `labelPlural`,
`stream`, `disabled`) into the `EntitySettings` block when the
settings block does not already carry the value. A warning of the
form
`"Entity '<name>': '<key>' at top level is deprecated; move into settings:"`
is appended to `ProgramFile.deprecation_warnings`. Both the top-level
fields and the settings block are populated on the returned
`EntityDefinition` so downstream managers reading either location
continue to work.

The same pattern handles panel-level `dynamicLogicVisible:` →
`visibleWhen:` in `_parse_panel`.

### 4.6 Validator function index

The semantic validation rules are owned by
`PRDs/product/app-yaml-schema.md` **Section 10**. This doc does
**not** restate them — that was the source of the v1.0 → v1.2 drift
the rewrite corrected. What this section provides is the index from
each block to the validator function(s) that enforce its rules, so a
developer reading PRD Section 10 knows where to look in the code (and
a developer renaming a function knows which lines of this index to
update).

| YAML block | PRD rules | Enforcing function(s) in `config_loader.py` |
|---|---|---|
| Top-level | Section 10 "Top-level" | `validate_program` |
| Entity | Section 10 "Entity-level" | `_validate_entity` |
| Field | Section 10 "Field-level" | `_validate_field`, `_validate_field_conditions` |
| `settings:` | Section 10 "Settings-level" | `_validate_settings` |
| `duplicateChecks:` | Section 10 "Duplicate-detection-level" | `_validate_duplicate_checks`, `_validate_alert_to`, `_validate_alert_template_refs` (cross-block) |
| `savedViews:` | Section 10 "Saved-view-level" | `_validate_saved_views` |
| `emailTemplates:` | Section 10 "Email-template-level" | `_validate_email_templates` |
| `workflows:` | Section 10 "Workflow-level" | `_validate_workflows`, `_validate_workflow_trigger`, `_validate_workflow_action`, `_validate_workflow_template_refs` (cross-block) |
| `filteredTabs:` | Section 10 "Filtered-tab-level" | `_validate_filtered_tabs`, `_validate_filtered_tab_scopes` (cross-entity uniqueness) |
| `layout:` | Section 10 "Layout-level" | `_validate_layout` |
| `relationships:` | Section 10 "Relationship-level" | `_validate_relationship` |
| `formula:` (aggregate / arithmetic / concat) | Section 10 "Field-level" formula bullets | `_validate_formula`, `_validate_aggregate_formula`, `_validate_arithmetic_formula`, `_validate_concat_formula` |

If you are renaming a validator or moving its rules to a different
function, update the corresponding row(s) above. If you are adding a
new block, add a new row here as part of step 7c of Section 8 below.

The shared `parse_condition` / `validate_condition` calls that all
condition-expression filters delegate to are documented in
Section 5.1.

### 4.7 Error format

Errors are returned as human-readable strings carrying enough context
to locate and fix each issue:

```
"Engagement.savedViews[mentor-active]: missing required property 'name'"
"Engagement.savedViews[mentor-active].filter: field 'foo' not found on entity 'Engagement'"
"Engagement.filteredTabs[my-open].scope: 'my open' must be PascalCase, ..."
"Contact.workflows[w1].actions[0]: setField requires 'field' on Contact"
"Relationship 'duesToMentor': missing required property 'description'"
```

---

## 5. Shared Parsers

### 5.1 Condition expressions (`condition_expression.py`)

Used by `requiredWhen`, `visibleWhen`, `savedViews[].filter`,
`workflows[].where`, `filteredTabs[].filter`, and
`formula.aggregate.where`.

```python
OPERATORS = {
    "equals", "notEquals", "contains", "in", "notIn",
    "lessThan", "greaterThan", "lessThanOrEqual", "greaterThanOrEqual",
    "isNull", "isNotNull",
}
OPERATORS_REQUIRING_LIST = {"in", "notIn"}
OPERATORS_NO_VALUE       = {"isNull", "isNotNull"}
OPERATORS_COMPARISON     = {"lessThan", "greaterThan",
                            "lessThanOrEqual", "greaterThanOrEqual"}

# AST
@dataclass
class LeafClause:
    field: str
    op: str
    value: Any = field(default=_MISSING)  # sentinel for "no value"

@dataclass
class AllNode:
    children: list[LeafClause | AllNode | AnyNode]

@dataclass
class AnyNode:
    children: list[LeafClause | AllNode | AnyNode]

ConditionNode = LeafClause | AllNode | AnyNode

# Public API
def parse_condition(raw: Any) -> ConditionNode: ...
def validate_condition(parsed: ConditionNode,
                       entity_field_names: set[str],
                       related_entity_field_names: set[str] | None = None,
                       ) -> list[str]: ...
def evaluate_condition(parsed: ConditionNode,
                       record: dict,
                       today: date | None = None) -> bool: ...
def render_condition(parsed: ConditionNode) -> list | dict:
    """Always emits structured ({all: [...]}) form, even for shorthand."""
```

`parse_condition` accepts both shorthand (a flat list of leaves =
implicit AND) and structured (`{all: [...]}` / `{any: [...]}`,
nestable) form. `render_condition` always emits structured form.

### 5.2 Relative dates (`relative_date.py`)

Used inside leaf-clause `value:` fields when comparing against a
date/datetime field.

```python
RELATIVE_DATE_TOKENS = {"today", "yesterday", "thisMonth", "lastMonth"}
# Plus: "lastNDays:N", "nextNDays:N"  (regex-matched)

def is_relative_date(value: str) -> bool: ...
def resolve_relative_date(value: str,
                          today: date | None = None) -> date: ...
```

`evaluate_condition` calls `resolve_relative_date` lazily so an
override `today=` can be threaded through tests.
`filtered_tab_manager.py` resolves these tokens at deploy time
(EspoCRM's Report Filter does not re-resolve over time, so
declarative sliding windows are not supported via this path; see
Section 5.9 of the PRD).

### 5.3 Arithmetic formulas (`formula_parser.py`)

```python
@dataclass class NumberLiteral: value: float
@dataclass class FieldRef:      name: str
@dataclass class BinaryOp:      op: str; left: ArithNode; right: ArithNode

ArithNode = NumberLiteral | FieldRef | BinaryOp

def parse_arithmetic(expression: str) -> ArithNode: ...
def extract_field_refs(node: ArithNode) -> set[str]: ...
def render_arithmetic(node: ArithNode) -> str:
    """Re-renders with minimal parentheses based on operator precedence."""
```

Recursive-descent parser; supports `+`, `-`, `*`, `/`, parens, integer
and decimal literals, and field-name identifiers. Used by both
`formula: { type: arithmetic }` blocks and by `setField.value:` in
workflows.

---

## 6. EspoCRM Naming Conventions

### 6.1 Entity name mapping

The mapping lives in
`espo_impl/ui/confirm_delete_dialog.py::get_espo_entity_name`. Per
CLAUDE.md, this placement is intentional and should not be refactored
without updating every caller.

```python
ENTITY_NAME_MAP = {
    "Engagement":         "CEngagement",
    "Session":            "CSessions",          # irregular plural
    "Workshop":           "CWorkshops",
    "WorkshopAttendance": "CWorkshopAttendee",
    "NpsSurveyResponse":  "CNpsSurveyResponse",
    "Dues":               "CDues",
}
NATIVE_ENTITIES = {
    "Contact", "Account", "Lead", "Opportunity",
    "Case", "Task", "Meeting", "Call", "Email", "Document",
}

def get_espo_entity_name(yaml_name: str) -> str:
    if yaml_name in NATIVE_ENTITIES:
        return yaml_name
    if yaml_name in ENTITY_NAME_MAP:
        return ENTITY_NAME_MAP[yaml_name]
    return f"C{yaml_name}"             # default fallback
```

EspoCRM's auto-generated C-prefixed names do not always follow a
consistent rule (e.g., `Session` → `CSessions` with an extra `s`).
The mapping table handles these irregularities. New custom entities
should be added to the map explicitly rather than relying on the
default fallback.

### 6.2 Field name mapping

Custom fields receive a `c` prefix with the first letter capitalized:

```python
def _custom_field_name(name: str) -> str:
    return f"c{name[0].upper()}{name[1:]}"
# "contactType" → "cContactType"
# "isMentor"    → "cIsMentor"
```

Native entity fields keep their natural names with no prefix.

### 6.3 When each name form is used

| Operation | Entity name | Field name |
|---|---|---|
| Entity CREATE (POST) | Natural (`Engagement`) | N/A |
| Entity DELETE (POST) | C-prefixed | N/A |
| Entity CHECK (GET) | C-prefixed | N/A |
| Field CREATE (POST) | C-prefixed | Natural (`contactType`) |
| Field UPDATE (PUT) | C-prefixed | c-prefixed |
| Field CHECK (GET) | C-prefixed | c-prefixed first, then natural fallback |
| Layout READ (GET) | C-prefixed | N/A |
| Layout SAVE (PUT) | C-prefixed | c-prefixed in row cells |
| Relationship CHECK / CREATE | C-prefixed | N/A |
| ReportFilter CRUD (filtered tabs) | C-prefixed `entityType` | natural in `data.where[].attribute` |

---

## 7. Testing

The schema-related test files:

| File | Coverage |
|---|---|
| `tests/test_models.py` | Dataclass shapes, enum values |
| `tests/test_config_loader.py` | Top-level / entity / field / layout / relationship validators |
| `tests/test_condition_expression.py` | Parse / validate / evaluate / render of the AST |
| `tests/test_relative_date.py` | Token recognition + resolution |
| `tests/test_formula.py` | Arithmetic parsing + field-ref extraction; aggregate / arithmetic / concat validators |
| `tests/test_required_when.py` | Field-level `requiredWhen:` plumbing |
| `tests/test_visible_when.py` | Field- and panel-level `visibleWhen:` plumbing |
| `tests/test_entity_settings.py` | `settings:` block + deprecation merge |
| `tests/test_duplicate_checks.py` | Duplicate-check validators + cross-block alert template refs |
| `tests/test_saved_views.py` | Saved-view parsing / validation / NOT_SUPPORTED manager path |
| `tests/test_email_templates.py` | Body-file resolution, merge-field validation |
| `tests/test_workflows.py` | Trigger + action validators, cross-block template refs |
| `tests/test_filtered_tabs.py` | FilteredTab parsing, validation, cross-entity scope uniqueness, manager bundle generation, Advanced Pack absent path |

The test idiom uses pytest's `tmp_path` fixture with an inline YAML
string fed through `ConfigLoader().load_program()`:

```python
def test_validate_missing_id(tmp_path):
    content = dedent("""\
        version: "1.1"
        description: "Test"
        entities:
          Engagement:
            filteredTabs:
              - scope: NoId
                label: "No Id"
                filter:
                  - { field: status, op: equals, value: "Open" }
            fields:
              - { name: status, type: enum, label: "Status",
                  options: ["Open"] }
    """)
    path = tmp_path / "p.yaml"
    path.write_text(content)
    program = ConfigLoader().load_program(path)
    errors = ConfigLoader().validate_program(program)
    assert any("missing required property 'id'" in e for e in errors)
```

For manager-level tests that need to drive a `*Manager` without
hitting a real EspoCRM, the api_client is replaced with a `MagicMock`
configured per scenario; see `tests/test_filtered_tabs.py::_make_manager`
for the canonical pattern.

---

## 8. Adding a New v1.x Block

To add a new entity-level block (e.g., a future `reports:` or
`dashboards:` block), do the work in this order. Step 1 (the PRD)
comes first deliberately — write the contract before writing the code
that satisfies it, and before writing the impl-doc entries that
reference it.

1. **PRD — write the spec first** (`PRDs/product/app-yaml-schema.md`):
   - Add a Section 5.x covering the YAML form, a properties table,
     and the run-time / cross-block behavior.
   - Add the validation rules under Section 10 with a heading like
     "**Foo-level** ..." in the same style as the existing blocks.
   - Bump the version stamp at the top of the PRD and append a
     revision-history row.

2. **Model** (`models.py`): add the dataclass, status enum, result
   dataclass, and counters on `RunSummary`. Add a list field and
   `*_raw` field on `EntityDefinition`. Add a `*_results` list on
   `RunReport`.

3. **Loader** (`config_loader.py`): add `_parse_<block>` that returns
   typed instances; pass the raw block through unchanged. Wire it
   into the entity-construction path.

4. **Validator** (`config_loader.py`): add `_validate_<block>` and
   call it from `_validate_entity`. Add cross-program validators
   (e.g., uniqueness, cross-block refs) at the program level. Each
   validator enforces the rules you wrote in PRD Section 10 in
   step 1; do not duplicate the rule wording in code comments.

5. **Manager** (`core/<block>_manager.py`): mirror an existing manager
   (saved views or filtered tabs are good templates). Always raise a
   `<Block>ManagerError` on HTTP 401 so the run worker can hard-abort.

6. **Worker step** (`workers/run_worker.py`): add the manager error
   class to `_MANAGER_ERROR_TYPES`, the canonical step name to
   `_STEP_DISPLAY_NAMES`, the step body, the `_attach_<block>_results`
   helper, and (if applicable) entries in `_emit_manual_config_block`.

7. **Tests** (`tests/test_<block>.py`): cover parse, validate, and
   manager paths. Update `tests/test_run_worker.py` to extend the
   `expected_steps` set if you added a step.

8. **Impl doc + user guide** — keep this file and the user guide
   in step with the code:
   a. **This file** — add the dataclass to Section 3, a row to the
      Section 4.6 validator-function index, the shared parser
      to Section 5 if any was introduced, and the test file to
      Section 7. Bump the version stamp at the top and append a
      revision-history row to Section 9.
   b. **User guide** (`docs/user/user-guide.md`) — add an
      end-user-facing subsection under "Writing YAML Program Files"
      covering declaration, behavior, and any operator follow-up
      steps. The user guide does *not* restate validation rules;
      it shows YAML examples and what the user sees on Run.

The `filteredTabs:` block (v1.2) is the most recent worked example;
see commits + `tests/test_filtered_tabs.py` for the end-to-end shape.

### Sync checklist for any change

For any change to the schema or its validators, before merging:

- [ ] PRD `app-yaml-schema.md` version stamp + revision history bumped
- [ ] PRD Section 5/10 wording reflects the new behavior
- [ ] This doc's version stamp + revision history bumped (matching date)
- [ ] This doc's Section 4.6 function-name index still accurate
- [ ] User guide has user-facing coverage if the change is observable
- [ ] CLAUDE.md "YAML Schema v1.x" status block updated if the
      version label changed

---

## 9. Revision History

| Version | Date | Summary |
|---|---|---|
| 1.0 | March 2026 | Initial impl reference covering v1.0 schema only. |
| 1.2 | 05-03-26 | Full rewrite to match current code. Documents all v1.1 models (`EntitySettings`, `DuplicateCheck`, `SavedView`, `EmailTemplate`, `Workflow`, `Formula` and its three sub-types) plus the v1.2 `FilteredTab`. Replaces the non-existent `load_program_file()` with the actual `ConfigLoader.load_program()` / `.validate_program()` API. Adds Section 5 for the shared parsers (condition expressions, relative dates, arithmetic). Updates Section 6 to reflect that `get_espo_entity_name` placement is intentional. Replaces Section 7's stale test list with the current set. Adds Section 8 ("Adding a New v1.x Block"). |
| 1.2.2 | 05-03-26 | Demoted Section 4.6 from a parallel rule list to a function-name index pointing at PRD Section 10 — the parallel restatement was the source of past drift. Added explicit "Companion product spec" + "Keeping this impl doc and the PRD in sync" subsections in Section 1, mirrored by the same in the PRD. Reordered Section 8 so the PRD update is step 1 (write the contract before writing the code that satisfies it) and added a sync checklist. Bumped to match PRD v1.2.2. |
