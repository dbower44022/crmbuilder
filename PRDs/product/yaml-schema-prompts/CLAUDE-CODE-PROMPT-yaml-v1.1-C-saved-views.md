# CLAUDE-CODE-PROMPT — yaml-v1.1-C — Entity `savedViews:` Block

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:20
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Section 5.6
(`savedViews:`); Section 10 "Saved-view-level" validation rules;
Section 11 "Shared Condition Expressions" (used by `filter:`).
**Foundation:** Prompt A established `condition_expression.py` —
the parser/validator/evaluator/renderer used by `filter:`. Prompt
A's loader plumbing stashed `saved_views_raw` on
`EntityDefinition`. Prompt B established the typed-block-on-
EntityDefinition pattern that this prompt follows.

## Position in the Series

Implements gap-analysis Category 3 (Saved Views and List Filters).
This prompt has the cleanest single-block scope in the series
because `savedViews:` is a self-contained list of rules with no
cross-block references.

## Scope

In scope:

1. Parse `saved_views_raw` into a typed `list[SavedView]` on each
   entity. Each saved view's `filter:` is parsed via Prompt A's
   `parse_condition`.
2. Full validation per spec Section 10 "Saved-view-level":
   unique `id` within entity, required `name`, `columns:` field
   references (when present), valid condition expression in
   `filter:` (delegating field-reference checks to
   `validate_condition` from Prompt A), `orderBy:` shape and
   field-reference checks.
3. New manager module `espo_impl/core/saved_view_manager.py` —
   CHECK→ACT against the EspoCRM list-view configuration API.
4. Wire the manager into the run/verify orchestration alongside
   the managers added in Prompt B.
5. Drift detection: a saved view present on the CRM that is not
   in YAML should be reported, not silently deleted.
6. Tests covering parsing, validation, manager CHECK→ACT, and
   drift detection.

Out of scope:

- Per-user saved views — v1.1 saved views are entity-scoped and
  shared across users. Per-user view authoring stays a CRM-side
  concern.
- Default-view selection (which saved view loads first) — not in
  the v1.1 spec.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- `SavedView` properties are defined in spec Section 5.6's table.
- `filter:` shorthand and structured forms are defined in spec
  Section 11; this prompt does not redefine them, it consumes
  them via `parse_condition`.
- `orderBy:` may be a single object or a list of objects, per
  spec Section 5.6 "orderBy clauses".
- All validation rules referenced here are spelled out in spec
  Section 10 "Saved-view-level".

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. Tests are
  pure-logic.
- **Validator integration.** Saved-view validation is added to
  `config_loader.py`'s `validate_program` path, so failures are
  reported alongside existing errors. Field-reference checks for
  `filter:` clauses delegate to `validate_condition` from
  Prompt A.
- **Drift detection.** `saved_view_manager.py` implements
  CHECK→ACT against the EspoCRM API, parallel to Prompt B's
  managers. Saved views present on the CRM but not in YAML are
  flagged in the report (do not silently delete).
- **Field reference validation.** Every field name in
  `columns:`, every `field:` in `filter:` leaf clauses, and
  every `field:` in `orderBy:` must reference a real field on
  the entity. The `filter:` checks come from Prompt A's
  `validate_condition`; `columns:` and `orderBy:` checks are
  this prompt's responsibility.
- **Backward compatibility.** v1.0 YAML files have no
  `savedViews:` block; their behavior is unchanged.

## Files to Create

1. `espo_impl/core/saved_view_manager.py` — SavedView CHECK→ACT.
2. `tests/test_saved_views.py` — parsing, validation, manager.

## Files to Modify

1. `espo_impl/core/models.py` — add `SavedView` dataclass and
   `OrderByClause` (or similar) dataclass. Add a typed field on
   `EntityDefinition`:
   - `saved_views: list[SavedView] = field(default_factory=list)`

   The existing `saved_views_raw` field stays populated for
   backward compatibility.

2. `espo_impl/core/config_loader.py` — parse `saved_views_raw`
   into the typed list during `load_program`. Filter expressions
   are parsed via `parse_condition` at load time so that load-time
   shape errors surface as load errors. Add a
   `_validate_saved_views` helper invoked from `_validate_entity`
   per spec Section 10.

3. The run/verify orchestration entry point — add the saved-view
   manager call after duplicate checks and before fields, in
   the same pass established in Prompt B. (Order rationale:
   saved views are display-layer artifacts that depend only on
   the entity existing; they can land before or after fields, but
   placing them earlier surfaces shape problems sooner.)

4. `espo_impl/core/reporter.py` and `RunSummary` in `models.py` —
   extend to surface saved-view outcomes (created / updated /
   skipped / drift).

## Test Coverage Areas

For `tests/test_saved_views.py`:

- Parsing: shorthand-form `filter:` parses via Prompt A; structured-
  form `filter:` parses via Prompt A; `orderBy:` as a single
  object and as a list both parse correctly; `direction:` defaults
  to `asc` when omitted.
- Validation per spec Section 10: duplicate `id` within entity;
  unknown field in `columns:`; unknown field in `filter:` leaf
  clauses (via `validate_condition`); unknown field in
  `orderBy:`; invalid `direction:` value; missing required
  `name`.
- Validation: an invalid `filter:` shape (e.g., empty `all:`,
  unknown operator) surfaces a clear error tied to the saved
  view's `id`.
- Manager CHECK→ACT: saved view absent on CRM → create; saved
  view present and matching → skip; saved view present and
  differing → update; saved view on CRM not in YAML → drift
  report (do not silently delete).
- Idempotency on second run.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `EntityDefinition` carries a typed
   `saved_views: list[SavedView]` field in addition to the
   existing raw field.
3. `ConfigLoader.load_program` parses `savedViews:` (including
   `filter:` via `parse_condition`) and populates the typed
   field; `validate_program` enforces every Section 10
   "Saved-view-level" rule.
4. Run/verify orchestration applies saved-view changes alongside
   the existing work, with results surfaced through the reporter
   and counted in `RunSummary`.
5. All existing tests continue to pass.
6. New tests cover the coverage areas above.
7. `uv run ruff check espo_impl/ tests/` passes clean.
8. `uv run pytest tests/ -v` passes.
9. Commit and push to `main` with a clear message referencing
   this prompt and the spec.

## Reporting Back

When finished, report:

- New file paths and line counts
- New tests added (counts and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompts D–H
