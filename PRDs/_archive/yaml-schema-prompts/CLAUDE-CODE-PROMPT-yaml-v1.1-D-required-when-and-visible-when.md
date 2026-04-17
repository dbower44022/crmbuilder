# CLAUDE-CODE-PROMPT — yaml-v1.1-D — Field-Level `requiredWhen:` and `visibleWhen:`; Panel-Level `visibleWhen:` Rename

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:25
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Sections 6.1.1
(`requiredWhen:`), 6.1.2 (`visibleWhen:` field-level), 7.3
(`visibleWhen:` panel-level); Section 10 "Field-level" and
"Layout-level" validation rules.
**Foundation:** Prompt A established `condition_expression.py`
(used to parse, validate, and evaluate both `requiredWhen:` and
`visibleWhen:` expressions) and stashed the raw values on
`FieldDefinition.required_when_raw`, `FieldDefinition.visible_when_raw`,
and `PanelSpec.visible_when_raw`. Prompt A also added the
panel-level `dynamicLogicVisible:` deprecation warning.

## Position in the Series

Implements gap-analysis Categories 4 (Conditional-Required Logic)
and 5 (Field-Level Dynamic Logic). These two are bundled because
they share the same condition-expression construct, the same
mutual-exclusion rules with `required: true`, and the same deploy-
manager translation path (both map to the target CRM's
dynamic-logic API).

## Scope

In scope:

1. Parse `required_when_raw` and `visible_when_raw` on each
   `FieldDefinition` via Prompt A's `parse_condition`. Store the
   parsed AST on new typed fields.
2. Parse `visible_when_raw` on each `PanelSpec` via
   `parse_condition`. Store the parsed AST on a new typed field.
3. Validation per spec Section 10 "Field-level":
   - `requiredWhen:` must be a valid condition expression.
   - A field must not set both `required: true` and
     `requiredWhen:`.
   - `visibleWhen:` must be a valid condition expression.
   - A field must not set both `required: true` and
     `visibleWhen:`.
   - Field references inside both expressions must exist on the
     entity (delegated to `validate_condition`).
4. Validation per spec Section 10 "Layout-level":
   - A panel may specify either `visibleWhen:` or the deprecated
     `dynamicLogicVisible:`, not both. Both present is an error.
   - `visibleWhen:` on a panel must be a valid condition
     expression with field references checked against the entity.
5. Translation of parsed `requiredWhen:` and `visibleWhen:`
   (field-level and panel-level) into the target CRM's
   dynamic-logic API during deploy. No new manager module is
   needed — these become additional payloads that
   `field_manager.py` (for field-level) and `layout_manager.py`
   (for panel-level) send alongside their existing work.
6. Drift detection: compare parsed condition against the CRM's
   current dynamic-logic state; report differences via the
   existing field/layout outcome machinery.
7. Tests covering parsing, mutual-exclusion validation, deploy
   translation, and drift detection.

Out of scope:

- Evaluating `requiredWhen:` / `visibleWhen:` client-side within
  the CRM Builder app — these are translated to target-CRM
  configuration and executed by the CRM at runtime.
- `dynamicLogicVisible:` auto-migration — the prompt preserves
  the Prompt A deprecation-warning behavior and adds the
  mutual-exclusion check. The `tools/migrate-yaml-v1.0-to-v1.1.py`
  script remains out of series scope.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- Mutual-exclusion rules are defined in spec Sections 6.1.1 and
  6.1.2.
- Panel-level `visibleWhen:` replaces `dynamicLogicVisible:` per
  spec Section 7.3; a panel may not set both.
- Condition expressions conform to spec Section 11; this prompt
  consumes them via `parse_condition` / `validate_condition` and
  does not redefine them.

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. Tests are
  pure-logic.
- **Validator integration.** Mutual-exclusion checks and
  condition-expression validation are added to `config_loader.py`'s
  `_validate_field` and `_validate_layout` paths.
- **Drift detection.** Existing `field_manager.py` and
  `layout_manager.py` CHECK→ACT loops are extended to include the
  new dynamic-logic payloads.
- **Field reference validation.** Condition-expression field
  references are checked by delegating to `validate_condition`
  with the entity's field-name set.
- **Backward compatibility.** v1.0 YAML files continue to load.
  `dynamicLogicVisible:` continues to work with a deprecation
  warning (Prompt A) and now fails validation only if
  `visibleWhen:` is also present on the same panel.

## Implementation Note — `render_condition` Behavior

Prompt A's `render_condition` always emits structured form
(`{all: [...]}`) even for shorthand input. This is acceptable for
drift detection and CRM API translation — the target CRM receives
structured form regardless of YAML authoring style.

## Files to Create

1. `tests/test_required_when.py` — parsing, mutual-exclusion
   validation, deploy translation for `requiredWhen:`.
2. `tests/test_visible_when.py` — parsing, mutual-exclusion
   validation, deploy translation for field-level and panel-level
   `visibleWhen:`, including the `dynamicLogicVisible:` conflict
   check.

## Files to Modify

1. `espo_impl/core/models.py` — add typed fields:
   - `FieldDefinition.required_when: ConditionNode | None = None`
   - `FieldDefinition.visible_when: ConditionNode | None = None`
   - `PanelSpec.visible_when: ConditionNode | None = None`

   Import `ConditionNode` from `condition_expression`. The
   existing `*_raw` fields stay populated.

2. `espo_impl/core/config_loader.py` — parse the raw fields via
   `parse_condition` during `load_program` (entity field loop and
   panel loop). Add mutual-exclusion checks to `_validate_field`
   and condition-expression validation (via `validate_condition`)
   for field-level and panel-level constructs. Add the
   panel-level mutual-exclusion check (`visibleWhen:` vs.
   `dynamicLogicVisible:`) to `_validate_layout`.

3. `espo_impl/core/field_manager.py` — extend the CHECK→ACT loop
   to include `requiredWhen` and `visibleWhen` in the field's
   dynamic-logic payload sent to the CRM API. Use
   `render_condition` to produce the CRM-API-ready dict from the
   parsed AST.

4. `espo_impl/core/layout_manager.py` — extend the CHECK→ACT
   loop to include panel-level `visibleWhen` in the layout
   payload. Use `render_condition` for the same purpose.

## Test Coverage Areas

For `tests/test_required_when.py`:

- Parsing: shorthand-form `requiredWhen:` parses via Prompt A;
  structured-form parses; absent `requiredWhen:` leaves the
  typed field as `None`.
- Mutual exclusion: `required: true` with `requiredWhen:` present
  produces a validation error naming the entity and field.
- Validation: field references inside `requiredWhen:` checked
  against entity fields; unknown field produces an error.
- Deploy translation: parsed `requiredWhen:` is rendered via
  `render_condition` and included in the field's dynamic-logic
  API payload.

For `tests/test_visible_when.py`:

- Parsing (field-level): shorthand and structured forms; absent
  leaves `None`.
- Parsing (panel-level): shorthand and structured forms; absent
  leaves `None`.
- Mutual exclusion (field-level): `required: true` with
  `visibleWhen:` produces a validation error.
- Mutual exclusion (panel-level): `visibleWhen:` and
  `dynamicLogicVisible:` both present on the same panel produces
  a validation error. Only one present is fine (each with its own
  deprecation or acceptance path).
- Validation: field references checked; unknown field produces an
  error tied to the field or panel context.
- Deploy translation (field-level): rendered and included in
  field payload.
- Deploy translation (panel-level): rendered and included in
  layout payload.
- Drift detection: condition on CRM differs from YAML → flagged;
  condition matches → skipped.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New test files exist at the paths listed under "Files to
   Create".
2. `FieldDefinition` carries typed `required_when` and
   `visible_when` fields; `PanelSpec` carries typed
   `visible_when` field.
3. `ConfigLoader.load_program` parses both constructs via
   `parse_condition` and populates the typed fields.
4. `validate_program` enforces every relevant Section 10 rule:
   mutual exclusion, condition-expression validity, field
   references.
5. `field_manager.py` and `layout_manager.py` include the
   dynamic-logic payloads in their CHECK→ACT loops.
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
- Any open questions or follow-ups for Prompts E–H
