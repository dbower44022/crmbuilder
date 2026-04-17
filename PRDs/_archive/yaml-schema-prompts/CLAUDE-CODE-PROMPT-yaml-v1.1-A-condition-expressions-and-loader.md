# CLAUDE-CODE-PROMPT — yaml-v1.1-A — Condition Expressions and Loader Plumbing

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-14-26 20:30
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 (commit 7a0abfd) —
in particular Section 11 "Shared Condition Expressions".
**Background:** `PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`
(commit 05b36dc) — explains the design rationale.

## Position in the Series

This is **Prompt A — the foundation**. It establishes:

- The condition-expression parser, validator, and evaluator
- The relative-date vocabulary
- Loader plumbing for the new entity-level blocks that all later
  prompts will populate
- Test fixtures and conventions later prompts will reuse

Because the seven later prompts all depend on what lands here, this
prompt is the only one given step-by-step prescriptive treatment.
Prompts B–H reference the patterns established here and the spec
document.

**This prompt does NOT implement any specific entity-level block
(settings, duplicateChecks, savedViews, emailTemplates, workflows)
or any specific field-level property (requiredWhen, visibleWhen,
formula, externallyPopulated). Those are the subject of Prompts
B–H. This prompt builds only the shared infrastructure.**

## Scope

In scope:

1. New module `espo_impl/core/condition_expression.py` — pure-logic
   parser, validator, evaluator, and string-rendering for the
   condition-expression construct described in spec Section 11.
2. New module `espo_impl/core/relative_date.py` — pure-logic
   resolver for the relative-date vocabulary in spec Section 11.4.
3. Loader plumbing in `espo_impl/core/config_loader.py` — accept
   the new top-level entity-level keys (`settings`, `duplicateChecks`,
   `savedViews`, `emailTemplates`, `workflows`) as raw dicts/lists
   without parsing their internals. Later prompts add the
   per-block parsing.
4. Loader plumbing for the new field-level keys (`requiredWhen`,
   `visibleWhen`, `formula`, `externallyPopulated`) — accept them
   on `FieldDefinition` as raw dicts/lists/booleans without
   parsing internals.
5. Schema-version detection and deprecation-warning emission for
   the v1.0 → v1.1 migration of `labelSingular` / `labelPlural` /
   `stream` / `disabled` (still accepted but warned). Same for
   panel-level `dynamicLogicVisible:` (still accepted but warned).
6. Tests for condition expressions, relative-date resolution,
   loader acceptance of the new keys, and deprecation warnings.

Out of scope:

- Any per-block validation beyond shape (Prompts B–H)
- Any deploy-manager CHECK→ACT logic for the new blocks (Prompts B–H)
- Any UI changes (none planned in v1.1)
- The migration helper script `tools/migrate-yaml-v1.0-to-v1.1.py`
  (mentioned in spec but deferred — out of scope for this series)

## Working Method

Standard CRM Builder Python conventions:

```bash
# After changes:
uv run ruff check espo_impl/ tests/
uv run pytest tests/ -v
```

All new code: no GUI dependencies, fully testable pure logic. No
direct source edits to any other file beyond what is enumerated
below — this is a surgical addition, not a refactor.

## Files to Create

### 1. `espo_impl/core/condition_expression.py`

A new pure-logic module implementing the spec Section 11 construct.

**Public API (module-level functions or a small class — your call,
but keep it Qt-free and import-free except for stdlib + the existing
`models.py`):**

- `parse_condition(raw)` — Accept a flat list (shorthand) or a
  dict containing `all:` or `any:` (structured). Return a
  parsed-AST representation. Raise a clear `ValueError` with a
  user-readable message on malformed input.
- `validate_condition(parsed, entity_field_names, related_entity_field_names=None)` —
  Walk the AST. For each leaf, confirm `field` is in
  `entity_field_names` (or in `related_entity_field_names` for
  aggregate `where:` clauses — see Prompt F context). Confirm
  `op` is one of the spec Section 11.3 operators. Confirm
  `value` shape matches the operator (list for `in`/`notIn`,
  numeric/date/relative-date string for the comparison ops,
  absent for `isNull`/`isNotNull`). Return `list[str]` of error
  messages; empty list means valid.
- `evaluate_condition(parsed, record)` — Walk the AST with a
  record dict. Return bool. Used at runtime by the deploy
  manager to decide whether a rule applies. Implement faithfully
  per Section 11.3 semantics.
- `render_condition(parsed)` — Round-trip back to YAML-ready
  dict/list form. Used by drift detection to compare a parsed
  rule against the CRM's current state.

**AST shape suggestion** (you have latitude — pick what's clean):

```python
@dataclass
class LeafClause:
    field: str
    op: str            # one of OPERATORS
    value: Any         # absent for isNull/isNotNull (None sentinel ok)

@dataclass
class AllNode:
    children: list  # list[LeafClause | AllNode | AnyNode]

@dataclass
class AnyNode:
    children: list

# Parsed root is one of LeafClause | AllNode | AnyNode
# Shorthand (flat list) parses to AllNode wrapping the leaves.
```

**Module-level constants:**

```python
OPERATORS: set[str] = {
    "equals", "notEquals", "contains",
    "in", "notIn",
    "lessThan", "greaterThan", "lessThanOrEqual", "greaterThanOrEqual",
    "isNull", "isNotNull",
}

OPERATORS_REQUIRING_LIST: set[str] = {"in", "notIn"}
OPERATORS_NO_VALUE: set[str] = {"isNull", "isNotNull"}
OPERATORS_COMPARISON: set[str] = {
    "lessThan", "greaterThan", "lessThanOrEqual", "greaterThanOrEqual",
}
```

**Parser rules** (per spec 11.5):

- A flat list at the root → wrap as `AllNode`. Empty list is an
  error.
- A dict with key `all` → that key's value must be a non-empty
  list; recurse on each child.
- A dict with key `any` → same for `any`.
- A dict containing both `all` and `any` at the same level is an
  error.
- A dict containing `field` is a leaf clause; recurse on its
  required keys.
- Anything else → clear error message.

### 2. `espo_impl/core/relative_date.py`

A new pure-logic module implementing spec Section 11.4.

**Public API:**

- `RELATIVE_DATE_TOKENS: set[str]` — the bare tokens (`today`,
  `yesterday`, `thisMonth`, `lastMonth`).
- `is_relative_date(value: str) -> bool` — `True` if the string
  matches one of the bare tokens or the `lastNDays:N` /
  `nextNDays:N` patterns.
- `resolve_relative_date(value: str, today: date | None = None) -> date` —
  Return the resolved `datetime.date`. The optional `today`
  parameter exists for testability; defaults to
  `datetime.date.today()`. Raise `ValueError` on any string that
  is not a valid relative-date token.

**Implementation note:** `lastNDays:30` resolves to today − 30
days. `nextNDays:7` resolves to today + 7 days. `thisMonth` and
`lastMonth` resolve to the **first day** of the respective month
per spec.

### 3. Tests — `tests/test_condition_expression.py` and `tests/test_relative_date.py`

Two new test files, following the existing `tests/test_*.py`
conventions (pytest, dedent fixtures, `Loader` style).

**Coverage areas required for `test_condition_expression.py`:**

- Shorthand parsing (flat list of leaves) — including single-clause,
  multi-clause, and empty-list-rejection cases
- Structured parsing — `all:` only, `any:` only, nested `all`-in-`any`,
  nested `any`-in-`all`, deeply nested cases
- All 11 operators — at least one parse + one evaluate test per
  operator
- Operator value-shape rules — `in`/`notIn` require list, `isNull`/
  `isNotNull` reject `value`, comparison operators accept
  numerics/dates/relative-date strings
- `validate_condition` field-reference checking — known field passes,
  unknown field fails with a clear message, related-entity field
  scope works
- `evaluate_condition` semantics — at least one positive and one
  negative case per operator; `contains` against a list field;
  null handling for `isNull`/`isNotNull`; relative-date values
  resolved at evaluation time
- `render_condition` round-trip — parse a condition then render it
  back to a dict/list and confirm it parses to an equal AST
- Error path coverage — every spec 11.5 rule produces a failing
  validate result with a clear message

**Coverage areas required for `test_relative_date.py`:**

- Each of the four bare tokens resolves to the expected date when
  given a fixed `today`
- `lastNDays:N` and `nextNDays:N` work for several N values
  including 0, 1, 30, 365
- `is_relative_date` correctly identifies all valid forms and
  rejects literal ISO dates and gibberish
- `resolve_relative_date` raises `ValueError` with a clear message
  on invalid input

## Files to Modify

### 4. `espo_impl/core/config_loader.py`

Add loader plumbing for the new keys. **Do not parse the
internals** — store raw values for later prompts to consume.

**Schema version detection.** Add at the top of `load_program`:

```python
schema_version = str(raw.get("version", "1.0"))
deprecation_warnings: list[str] = []
```

**Pass-through entity-level keys.** When parsing each
`entity_data` dict, capture the new keys verbatim and stash them on
the resulting `EntityDefinition` (you'll add the new fields to
`EntityDefinition` in step 5 below):

```python
settings_raw = entity_data.get("settings")  # dict | None
duplicate_checks_raw = entity_data.get("duplicateChecks")  # list | None
saved_views_raw = entity_data.get("savedViews")  # list | None
email_templates_raw = entity_data.get("emailTemplates")  # list | None
workflows_raw = entity_data.get("workflows")  # list | None
```

**Deprecation handling.** If any of `labelSingular`, `labelPlural`,
`stream`, or `disabled` appear at the top level of `entity_data`:

- Continue accepting them (write to existing `EntityDefinition`
  fields for backward compatibility).
- Emit a deprecation warning via `logger.warning(...)` that names
  the entity, the deprecated key, and the equivalent
  `settings.<key>` location.
- Append the same message to `deprecation_warnings` so it can be
  surfaced through the loader's return value.

**Pass-through field-level keys.** When parsing each field dict,
capture:

```python
required_when_raw = field_data.get("requiredWhen")  # list | dict | None
visible_when_raw = field_data.get("visibleWhen")  # list | dict | None
formula_raw = field_data.get("formula")  # dict | None
externally_populated = bool(field_data.get("externallyPopulated", False))
```

Stash these on the new `FieldDefinition` fields (step 5 below).

**Panel-level `dynamicLogicVisible:` deprecation.** When parsing
panels, if `dynamicLogicVisible` appears, log a deprecation warning
naming the entity, the panel label, and the equivalent
`visibleWhen:` form. Continue populating the existing
`PanelSpec.dynamicLogicVisible` for backward compatibility. Also
read `visibleWhen` if present and stash it on `PanelSpec` (step 5).

**Surface deprecation warnings.** Modify `load_program` to also
return the warnings (or attach them to `ProgramFile`). Pick the
cleanest approach for the existing call sites.

### 5. `espo_impl/core/models.py`

Extend the dataclasses to carry the new raw fields:

**`EntityDefinition`:** add five optional fields (all default to
`None`):

```python
settings_raw: dict | None = None
duplicate_checks_raw: list | None = None
saved_views_raw: list | None = None
email_templates_raw: list | None = None
workflows_raw: list | None = None
```

**`FieldDefinition`:** add four optional fields:

```python
required_when_raw: list | dict | None = None
visible_when_raw: list | dict | None = None
formula_raw: dict | None = None
externally_populated: bool = False
```

**`PanelSpec`:** add one optional field:

```python
visible_when_raw: list | dict | None = None
```

(The existing `dynamicLogicVisible: dict | None = None` stays;
deprecated but preserved.)

**`ProgramFile`:** if you choose to surface deprecation warnings
through the model, add:

```python
deprecation_warnings: list[str] = field(default_factory=list)
```

### 6. Tests — `tests/test_config_loader.py`

Add tests covering:

- Loading a v1.1 program file with `settings:`, `duplicateChecks:`,
  `savedViews:`, `emailTemplates:`, `workflows:` blocks present —
  all stash as raw values, no validation errors
- Loading a v1.1 file with `requiredWhen:`, `visibleWhen:`,
  `formula:`, `externallyPopulated: true` on fields — all stash
  as raw values
- Loading a v1.0-style file with top-level `labelSingular`,
  `labelPlural`, `stream`, `disabled` on a custom entity — load
  succeeds, deprecation warnings are emitted (one per deprecated
  key per entity)
- Loading a panel with `dynamicLogicVisible:` — load succeeds,
  deprecation warning emitted
- Loading a panel with `visibleWhen:` — load succeeds, value
  stashes on `PanelSpec.visible_when_raw`

## Acceptance Criteria

1. New files exist:
   - `espo_impl/core/condition_expression.py`
   - `espo_impl/core/relative_date.py`
   - `tests/test_condition_expression.py`
   - `tests/test_relative_date.py`
2. `EntityDefinition`, `FieldDefinition`, and `PanelSpec` carry the
   new optional fields described in step 5.
3. `ConfigLoader.load_program` accepts v1.1 YAML files containing
   any of the new entity-level or field-level keys without error,
   stashing raw values for later prompts to consume.
4. Loading a v1.0-style file with deprecated top-level entity
   properties or panel-level `dynamicLogicVisible:` succeeds, with
   deprecation warnings emitted per spec.
5. `condition_expression` module's parser, validator, evaluator,
   and renderer behave per spec Section 11.
6. `relative_date` module resolves all six relative-date forms per
   spec Section 11.4.
7. All existing tests continue to pass.
8. New tests cover the coverage areas listed for each test file.
9. `uv run ruff check espo_impl/ tests/` passes clean.
10. `uv run pytest tests/ -v` passes.
11. Commit and push to `main` with a clear message referencing this
    prompt and the spec.

## Out of Scope

- Per-block validation of `settings.*`, `duplicateChecks.*`,
  `savedViews.*`, `emailTemplates.*`, `workflows.*`, `requiredWhen`,
  `visibleWhen`, `formula`, `externallyPopulated` — those are
  Prompts B–H.
- Any deploy-manager CHECK→ACT logic — those are Prompts B–H.
- Mutual-exclusion validation between `required: true` and
  `requiredWhen:` / `visibleWhen:` — Prompt D.
- The `tools/migrate-yaml-v1.0-to-v1.1.py` migration script —
  out of series scope.
- Any UI changes — none planned in v1.1.

## Reporting Back

When finished, report:

- New file paths and line counts
- New tests added (counts and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompts B–H
