# CLAUDE-CODE-PROMPT — yaml-v1.1-G — Entity `workflows:` Block

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:40
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Section 5.8
(`workflows:`); Section 10 "Workflow-level" validation rules;
Section 11 "Shared Condition Expressions" (used by `where:`).
**Foundation:** Prompt A established `condition_expression.py`
(used by workflow `where:` clauses). Prompt E established the
email-template registry on each entity (used by `sendEmail`
actions). Prompt F established the arithmetic parser (reused by
`setField.value:` arithmetic expressions).

## Position in the Series

Implements gap-analysis Category 9 (Workflows). This prompt has
the most cross-prompt dependencies in the series — it consumes
Prompt A (condition expressions), Prompt E (email template
resolution), and Prompt F (arithmetic expression parsing).

## Scope

In scope:

1. Parse `workflows_raw` into a typed `list[Workflow]` on each
   entity.
2. Trigger parsing: five trigger events per spec Section 5.8 —
   `onCreate`, `onUpdate`, `onFieldChange`, `onFieldTransition`,
   `onDelete`. Each trigger's required clauses are validated per
   the spec's trigger-events table.
3. Action parsing: four action types per spec Section 5.8 —
   `setField`, `clearField`, `sendEmail`,
   `sendInternalNotification`. Each action's required clauses
   are validated per the spec's actions table.
4. `where:` clause parsing via Prompt A's `parse_condition`;
   field-reference validation via `validate_condition`.
5. Full validation per spec Section 10 "Workflow-level":
   - Unique `id` within entity.
   - `name`, `trigger`, and `actions` required; `actions`
     non-empty.
   - `trigger.event` must be one of the five supported events.
   - `onFieldChange` and `onFieldTransition` require a valid
     `field:` on the entity; `onFieldTransition` additionally
     requires `from:` and/or `to:`.
   - `where:` must be a valid condition expression.
   - Action `type:` must be one of the four supported types.
   - `setField` and `clearField` require `field:` referencing a
     real field on the entity.
   - `setField.value:` must be a literal, the token `now`, or a
     valid arithmetic expression (reuse Prompt F's parser).
   - `sendEmail.template:` must reference an `id` in the
     entity's `emailTemplates:` block (Prompt E).
   - `sendEmail.to:` must be a field name on the entity or a
     literal email address.
   - `sendInternalNotification.to:` must be a literal email
     address or a string of the form `role:<role-id>` or
     `user:<user-id>`.
6. New manager module `espo_impl/core/workflow_manager.py` —
   CHECK→ACT against the EspoCRM workflow API.
7. Wire the manager into the run/verify orchestration. Workflows
   should be deployed **after** email templates (because
   `sendEmail` references must resolve) and after fields (because
   trigger `field:` and action `field:` must exist). Recommended
   position: last in the entity-level pass, after fields/layouts/
   relationships.
8. Drift detection: workflow absent on CRM → create; workflow
   present but differing → update; workflow on CRM not in YAML →
   drift report (do not silently delete).
9. Tests covering trigger parsing, action parsing, `where:`
   integration, cross-block template resolution, `setField.value:`
   arithmetic reuse, manager CHECK→ACT, and drift detection.

Out of scope:

- `onFirstTransition` trigger event — deferred to v1.2 per spec
  Section 5.8 because correct implementation requires audit-
  history awareness across multiple target CRMs.
- `createRelatedRecord` action — deferred to v1.2 per spec
  Section 5.8.
- Roles handling in `sendInternalNotification.to: role:<role-id>`
  — Category 6, v1.2. This prompt validates the string shape
  only; full role resolution arrives in v1.2.
- Workflow execution priority — v1.1 uses YAML declaration order
  per spec; no explicit `priority:` field.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- Trigger events and their required clauses are in spec
  Section 5.8 "Trigger events (v1.1)" table.
- Action types and their required clauses are in spec
  Section 5.8 "Actions (v1.1)" table.
- `setField.value:` accepts a literal, `now`, or an arithmetic
  expression per spec Section 5.8.
- `sendEmail.template:` cross-references spec Section 5.7.
- All validation rules are in spec Section 10 "Workflow-level".

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. Tests are
  pure-logic.
- **Validator integration.** Workflow validation is added to
  `config_loader.py`'s `validate_program` path. Cross-block
  `sendEmail.template:` resolution runs as a second-pass
  validator after both `emailTemplates:` and `workflows:` are
  parsed.
- **Drift detection.** `workflow_manager.py` implements CHECK→ACT
  against the EspoCRM API, parallel to the managers from
  Prompts B, C, and E.
- **Field reference validation.** Trigger `field:`, action
  `field:`, `where:` clause field references, and
  `setField.value:` arithmetic field references are all checked
  against the entity's field names.
- **Backward compatibility.** v1.0 YAML files have no
  `workflows:` block; their behavior is unchanged.

## Cross-Prompt Dependencies (explicit)

- **Prompt A** — `parse_condition` / `validate_condition` for
  `where:` clauses. Public API confirmed: `parse_condition(raw)`,
  `validate_condition(parsed, entity_field_names)`.
- **Prompt E** — `emailTemplates:` registry. The cross-block
  check confirms `sendEmail.template:` values resolve against
  the entity's `email_templates` list by `id`.
- **Prompt F** — arithmetic parser for `setField.value:`
  expressions. If Prompt F's parser exposes a public function
  like `parse_arithmetic(expression_str)` returning an AST, this
  prompt reuses it directly. If not, confirm the actual API at
  execution time and adapt.

## Files to Create

1. `espo_impl/core/workflow_manager.py` — Workflow CHECK→ACT.
2. `tests/test_workflows.py` — trigger parsing, action parsing,
   where-clause integration, cross-block template resolution,
   setField arithmetic reuse, manager CHECK→ACT.

## Files to Modify

1. `espo_impl/core/models.py` — add `Workflow`, `WorkflowTrigger`,
   and `WorkflowAction` dataclasses (or a similar decomposition).
   Add a typed field on `EntityDefinition`:
   - `workflows: list[Workflow] = field(default_factory=list)`

   The existing `workflows_raw` field stays populated.

2. `espo_impl/core/config_loader.py` — parse `workflows_raw`
   into the typed list during `load_program`. Add
   `_validate_workflows` helper per spec Section 10. Add the
   cross-block `sendEmail.template:` resolution check (iterate
   each entity's `workflows` and confirm `sendEmail` actions'
   `template:` values match `id`s in the same entity's
   `email_templates`).

3. The run/verify orchestration entry point — add the workflow
   manager call after fields/layouts/relationships, as the last
   entity-level step.

4. `espo_impl/core/reporter.py` and `RunSummary` in `models.py`
   — extend to surface workflow outcomes (created / updated /
   skipped / drift).

## Test Coverage Areas

For `tests/test_workflows.py`:

**Trigger parsing:**
- Each of the five trigger events parses correctly.
- `onFieldChange` requires `field:` (valid and invalid cases).
- `onFieldChange` with optional `to:` (single value and list).
- `onFieldTransition` requires `field:` plus `from:` and/or
  `to:` (present/absent combinations).
- `onFieldTransition` with `from:` and `to:` as single values
  and as lists.
- Invalid `trigger.event` produces an error.
- `trigger.field:` referencing a non-existent field produces an
  error.

**Action parsing:**
- `setField` with literal value, `now` token, and arithmetic
  expression.
- `setField.value:` arithmetic expression reuses Prompt F's
  parser; field references validated.
- `clearField` with valid and invalid `field:`.
- `sendEmail` with valid `template:` and `to:` (field name and
  literal email).
- `sendEmail.template:` not matching any email template ID →
  validation error.
- `sendInternalNotification.to:` with literal email,
  `role:<role-id>`, `user:<user-id>` — all three shapes accepted.
- Invalid action `type:` produces an error.
- Missing required clauses per action type produce errors.

**`where:` clause:**
- Shorthand and structured forms parsed via `parse_condition`.
- Field references validated against entity fields.
- Invalid condition shape surfaces a clear error tied to the
  workflow's `id`.

**General validation:**
- Duplicate `id` within entity.
- Missing `name`, `trigger`, or `actions`.
- Empty `actions` list.

**Manager CHECK→ACT:**
- Workflow absent on CRM → create.
- Workflow present and matching → skip.
- Workflow present but differing → update.
- Workflow on CRM not in YAML → drift report.
- Idempotency on second run.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `EntityDefinition` carries a typed
   `workflows: list[Workflow]` field in addition to the existing
   raw field.
3. `ConfigLoader.load_program` parses `workflows:` (including
   `where:` via `parse_condition` and `setField.value:` via
   Prompt F's arithmetic parser) and populates the typed field;
   `validate_program` enforces every Section 10 "Workflow-level"
   rule.
4. The cross-block `sendEmail.template:` resolution check is
   implemented and tested.
5. Run/verify orchestration applies workflow changes as the last
   entity-level step, with results surfaced through the reporter
   and counted in `RunSummary`.
6. All existing tests continue to pass.
7. New tests cover the coverage areas above.
8. `uv run ruff check espo_impl/ tests/` passes clean.
9. `uv run pytest tests/ -v` passes.
10. Commit and push to `main` with a clear message referencing
    this prompt and the spec.

## Reporting Back

When finished, report:

- New file paths and line counts
- New tests added (counts and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompt H
