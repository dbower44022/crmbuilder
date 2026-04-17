# CLAUDE-CODE-PROMPT — yaml-v1.1-B — Entity `settings:` and `duplicateChecks:` Blocks

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:15
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Sections 5.4
(`settings:`) and 5.5 (`duplicateChecks:`); Section 10
"Settings-level" and "Duplicate-detection-level" validation rules.
**Foundation:** `CLAUDE-CODE-PROMPT-yaml-v1.1-A-condition-expressions-and-loader.md`
established the loader plumbing that stashes `settings_raw` and
`duplicate_checks_raw` on `EntityDefinition`, and added the
`ProgramFile.deprecation_warnings` channel. This prompt parses
those raw values and adds CHECK→ACT plumbing.

## Position in the Series

Implements gap-analysis Categories 1 (Stream and Audit Logging)
and 2 (Duplicate Detection Rules). Bundled because both are
small, both add a new entity-level rule block, and both need
parallel CHECK→ACT plumbing in the deploy manager.

## Scope

In scope:

1. Parse `settings_raw` into a typed `Settings` model on each
   entity. Reject unknown keys per spec Section 10.
2. Parse `duplicate_checks_raw` into a typed `list[DuplicateCheck]`
   on each entity, with full validation per spec Section 10.
3. Promote v1.0 deprecation handling from "warn only" (Prompt A) to
   "warn and merge into `Settings`": when a deprecated top-level
   key is present and the equivalent `settings.<key>` is absent,
   the top-level value populates the corresponding `Settings`
   field. When both are present, `settings.<key>` wins and an
   additional warning notes the conflict.
4. New manager modules:
   - `espo_impl/core/entity_settings_manager.py` — CHECK→ACT for
     `settings:` against the EspoCRM entity-metadata API.
   - `espo_impl/core/duplicate_check_manager.py` — CHECK→ACT for
     `duplicateChecks:` against the EspoCRM duplicate-rule
     mechanism.
5. Wire both managers into the existing run/verify orchestration
   alongside fields/layouts/relationships.
6. Drift detection for both blocks, parallel to the existing
   field/layout/relationship drift paths.
7. Tests covering parsing, validation, CHECK→ACT logic, and drift
   detection.

Out of scope:

- `alertTemplate:` / `alertTo:` cross-block resolution against
  `emailTemplates:` — Prompt E adds the registry; this prompt
  validates only the shape of `alertTemplate:` (string) and
  `alertTo:` (string matching one of the three allowed forms).
  A follow-up validator pass in Prompt E performs the cross-block
  reference check.
- Roles handling in `alertTo: role:<role-id>` — Category 6, v1.2.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- Allowed `settings:` keys, their types, and required-ness are
  defined in spec Section 5.4.
- `duplicateChecks:` rule shape, `normalize:` vocabulary, and
  `onMatch:` vocabulary are defined in spec Section 5.5.
- All validation rules referenced here are spelled out in spec
  Section 10 ("Settings-level" and "Duplicate-detection-level").

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. Tests are
  pure-logic.
- **Validator integration.** Settings-key whitelist and
  duplicate-check rule validation are added to
  `config_loader.py`'s `validate_program` path, so failures are
  reported alongside existing field/layout/relationship errors.
- **Drift detection.** Both managers implement CHECK→ACT against
  the EspoCRM API, parallel to `field_manager.py` /
  `layout_manager.py` / `relationship_manager.py`. Each must
  surface created / updated / skipped / verified outcomes through
  the existing reporter machinery.
- **Field reference validation.** Every field name in a
  `duplicateChecks:` rule's `fields:` list and every key in
  `normalize:` must reference a real field on the entity. Bad
  references fail validation at load time.
- **Backward compatibility.** v1.0 YAML files continue to load
  with deprecation warnings. The deprecation merge described in
  scope #3 is non-breaking — the Settings dataclass picks up the
  same values whether they came from top-level or `settings:`.

## Files to Create

1. `espo_impl/core/entity_settings_manager.py` — Settings CHECK→ACT.
2. `espo_impl/core/duplicate_check_manager.py` — DuplicateCheck
   CHECK→ACT.
3. `tests/test_entity_settings.py` — parsing, validation, manager.
4. `tests/test_duplicate_checks.py` — parsing, validation, manager.

## Files to Modify

1. `espo_impl/core/models.py` — add `Settings` dataclass and
   `DuplicateCheck` dataclass (with nested `DuplicateCheckNormalize`
   if helpful). Add typed fields on `EntityDefinition`:
   - `settings: Settings | None = None`
   - `duplicate_checks: list[DuplicateCheck] = field(default_factory=list)`

   Keep the `*_raw` fields for backward compatibility with anything
   downstream that still consumes them; they remain populated.

2. `espo_impl/core/config_loader.py` — parse `settings_raw` and
   `duplicate_checks_raw` into the new typed fields during
   `load_program`. Extend `_validate_entity` (or add
   `_validate_settings` / `_validate_duplicate_checks` helpers) per
   spec Section 10. Implement the deprecation-merge described in
   scope #3.

3. The run/verify orchestration entry point (likely a method on
   `deploy_manager.py` or wherever fields/layouts/relationships
   are dispatched today — confirm at the start of execution) —
   wire in the two new managers in the same pass, in this order:
   `EntitySettings` → `DuplicateChecks` → existing
   field/layout/relationship work. Settings should be applied
   before duplicate checks because duplicate checks depend on
   stream-vs-no-stream behavior in some CRMs.

4. `espo_impl/core/reporter.py` — extend the report shape (and
   the corresponding `RunSummary` counters in `models.py`) to
   surface settings and duplicate-check outcomes.

## Test Coverage Areas

For `tests/test_entity_settings.py`:

- Parsing: empty `settings:`, fully-populated `settings:`,
  `settings:` absent → `entity.settings is None`.
- Validation: unknown key produces an error naming the key and the
  entity; `labelSingular` / `labelPlural` required only for
  `action: create` / `action: delete_and_create`; type checks for
  `stream` (bool) and `disabled` (bool).
- Deprecation merge: top-level `stream: true` with no `settings:`
  block populates `entity.settings.stream`; `settings.stream:
  false` with top-level `stream: true` resolves to `false` and
  emits a conflict warning.
- Manager CHECK→ACT: settings already match → no-op; settings
  differ → update issued and verified; native vs. custom entity
  handling differs as the spec describes; idempotency on second
  run.

For `tests/test_duplicate_checks.py`:

- Parsing: shorthand and structured rules; rules with and without
  `normalize:`, `alertTemplate:`, `alertTo:`; multiple rules per
  entity.
- Validation per spec Section 10: duplicate `id` within entity;
  unknown field in `fields:`; unknown field in `normalize:` keys;
  invalid `normalize:` value; invalid `onMatch:` value;
  `onMatch: block` without `message:`; `alertTo:` not matching
  one of the three allowed shapes.
- Manager CHECK→ACT: rule absent on CRM → create; rule present
  and matching → skip; rule present but differing → update; rule
  on CRM not in YAML → drift report (do not silently delete).
- Idempotency on second run.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `EntityDefinition` carries typed `settings: Settings | None`
   and `duplicate_checks: list[DuplicateCheck]` fields in
   addition to the existing raw fields.
3. `ConfigLoader.load_program` parses both blocks and populates
   the typed fields; `validate_program` enforces every Section 10
   rule listed under "Settings-level" and
   "Duplicate-detection-level" except the cross-block
   `alertTemplate:` reference (deferred to Prompt E).
4. The deprecation-merge behavior (scope #3) lands.
5. Run/verify orchestration applies settings and duplicate-check
   changes alongside the existing field/layout/relationship work,
   with results surfaced through the reporter and counted in
   `RunSummary`.
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
- Any open questions or follow-ups for Prompts C–H, especially
  any cross-block reference work that should land in a later
  prompt
