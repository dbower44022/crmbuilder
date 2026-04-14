# SESSION-PROMPT — yaml-v1.1 series — Draft Prompts B–H

**Repo:** `crmbuilder` (and read context from
`ClevelandBusinessMentoring`)
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-14-26 20:30
**Created in:** the prior session that produced the gap analysis,
the schema doc v1.1, and Prompt A.

## Purpose

Draft the remaining seven Claude Code prompts in the `yaml-v1.1`
series — Prompts B through H — for execution in Claude Code. Prompt
A (condition expressions and loader plumbing) was drafted and
committed in the prior session; this session covers the rest.

## Pre-flight — read these before doing any drafting

In this order:

1. **`crmbuilder/CLAUDE.md`** — current state of the deployment-app
   codebase. Confirm what's listed there matches what you find in
   the repo.
2. **`crmbuilder/PRDs/product/app-yaml-schema.md` v1.1** — the
   spec being implemented. Section 11 is the cross-cutting
   condition-expression construct; Sections 5.4–5.8 are
   entity-level blocks; Sections 6.1.1–6.1.4 are field-level
   properties; Section 7.3 is the panel-level rename of
   `dynamicLogicVisible:` to `visibleWhen:`.
3. **`crmbuilder/PRDs/product/yaml-schema-gap-analysis-MR-pilot.md`** —
   the design rationale and decision log. The Summary section at
   the end maps capabilities to gap-analysis categories.
4. **`crmbuilder/PRDs/product/yaml-schema-prompts/CLAUDE-CODE-PROMPT-yaml-v1.1-A-condition-expressions-and-loader.md`** —
   the prompt that established the foundation. Note its style; B–H
   should reference patterns this prompt established rather than
   restating them.
5. **The actual condition-expression module Prompt A produced** —
   most likely `crmbuilder/espo_impl/core/condition_expression.py`
   and `relative_date.py`, plus their tests. Read these before
   drafting any prompt that uses them. The module's actual public
   API may differ from the suggestions in Prompt A — drafts must
   match reality, not the suggestions.
6. **`crmbuilder/espo_impl/core/config_loader.py`** — confirm what
   loader plumbing for the new keys actually looks like after
   Prompt A landed. Prompts B–H assume the raw values are stashed
   on `EntityDefinition` and `FieldDefinition`.
7. **`crmbuilder/espo_impl/core/models.py`** — confirm the
   dataclass shapes after Prompt A's additions.

If the actual code shipped in Prompt A's commit deviates
substantially from what Prompt A spec'd, **stop and ask Doug**
before drafting B–H. Don't paper over discrepancies.

## Series shape (already approved in prior session)

| Prompt | Categories | Scope |
|---|---|---|
| A | (Section 11) | **Done** — shared condition-expression parser/validator/evaluator + loader plumbing |
| B | 1, 2 | Entity `settings:` block (with v1.0 deprecation), `duplicateChecks:` block |
| C | 3 | `savedViews:` block + CHECK→ACT |
| D | 4, 5 | Field-level `requiredWhen:` and `visibleWhen:`; panel-level `visibleWhen:` rename |
| E | 7 | `emailTemplates:` block + body-file resolution + merge-field validation |
| F | 8 | `formula:` block (aggregate / arithmetic / concat) — biggest single prompt |
| G | 9 | `workflows:` block, triggers, actions |
| H | 10 | `externallyPopulated:` flag + Verification Spec generator update |

Category 6 (Field-Level Access Control + Roles) is **deferred to
v1.2** by design and is not part of this series.

## Drafting style (already agreed in prior session)

- **Mixed depth, leaning short.** Prompt A was full step-by-step
  prescriptive because it set the patterns. B–H are spec-and-scope:
  state the capability, reference `app-yaml-schema.md` v1.1 for the
  authoritative spec, point at the modules from Prompt A for
  patterns, name the files to touch, list acceptance criteria. Do
  not restate the spec inside the prompt.
- **Coverage areas, not test counts.** Each prompt lists what
  *must* be covered by tests without naming a specific number.
- **No code samples in B–H prompts unless necessary to disambiguate**
  — the spec doc has the YAML examples already.

## Drafting working method

For each of Prompts B–H, follow the same loop used in the prior
session:

1. State which gap-analysis category/categories the prompt covers.
2. Identify the spec sections it implements.
3. Identify the modules to create or modify.
4. Identify the tests to add (coverage areas).
5. Note any cross-prompt dependencies (e.g., Prompt G's `sendEmail`
   action depends on Prompt E's `emailTemplates:` registration; the
   `where:` clauses on workflows depend on Prompt A's parser).
6. Show the proposed prompt to Doug.
7. Get approval (Doug's standard one-issue-at-a-time discipline).
8. Apply: write the file at
   `PRDs/product/yaml-schema-prompts/CLAUDE-CODE-PROMPT-yaml-v1.1-{letter}-{descriptor}.md`.
9. Move to the next prompt.

After all seven drafts, commit the batch (or commit per-prompt as
you go — Doug's call at the start of the session).

## Cross-cutting concerns to repeat in every prompt

These appear consistently across B–H — each prompt should restate
them concisely rather than assume they're inherited:

- **Spec authority:** the prompt implements `app-yaml-schema.md`
  v1.1; if the prompt and spec disagree, the spec wins.
- **Pure-logic discipline:** new logic lives in `espo_impl/core/`
  with no GUI dependencies; tests are pure-logic.
- **Validator integration:** every new property gets schema
  validation in `config_loader.py` per the matching block in spec
  Section 10.
- **Drift detection:** every new entity-level rule block (B, C, E,
  G) needs a CHECK→ACT path parallel to existing fields/layouts/
  relationships. Reference the `field_manager.py` /
  `layout_manager.py` / `relationship_manager.py` pattern.
- **Field reference validation:** every new construct that names a
  field must have its references checked against the entity at load
  time.
- **Backward compatibility:** never break existing v1.0 YAML files;
  deprecation warnings only.
- **Out of scope:** Category 6 (Roles, field-level permissions),
  `onFirstTransition` workflow trigger, `createRelatedRecord`
  workflow action, formula functions like `min`/`max`/`abs`/
  `round`/`coalesce`, `format:` clauses on concat parts, and the
  `tools/migrate-yaml-v1.0-to-v1.1.py` migration script. All
  deferred to v1.2 or beyond.

## Per-prompt drafting hints

These are starting points, not constraints — adjust based on what
the Prompt A code actually shipped.

### Prompt B — `settings` and `duplicateChecks`

Two entity-level blocks bundled because both are small and both
need parallel CHECK→ACT plumbing. Modules: likely a new
`entity_settings_manager.py` and `duplicate_check_manager.py` in
`espo_impl/core/`. Models: parse `settings_raw` into a `Settings`
dataclass and `duplicate_checks_raw` into a `list[DuplicateCheck]`.
Validator: settings keys whitelist, duplicate-check rules `id`
uniqueness, `onMatch` value check, `normalize` value check,
`alertTemplate` resolution (deferred to E — note this in the
prompt). v1.0 deprecation warnings for top-level
`labelSingular`/`labelPlural`/`stream`/`disabled` should already
be emitting from Prompt A's loader; B's job is to make
`settings.*` the canonical write path on the EspoCRM API side.

### Prompt C — `savedViews`

Entity-level block. New `saved_view_manager.py`. Models: parse
`saved_views_raw` into `list[SavedView]`. Validator: per spec
Section 10 saved-view-level rules — including `filter:` validation
via Prompt A's condition-expression module. CHECK→ACT against
EspoCRM's list-view configuration. `orderBy:` shape supports both
single dict and list of dicts.

### Prompt D — `requiredWhen` and `visibleWhen`

Field-level and panel-level. Two related conditional-rule
constructs. No new manager module — these become field properties
that the existing field_manager / layout_manager translate into
EspoCRM's dynamic-logic API. Validator: mutual-exclusion rules
(`required: true` cannot coexist with `requiredWhen:` or
`visibleWhen:`); panel-level `dynamicLogicVisible:` and
`visibleWhen:` cannot both be set; deprecation warning when
`dynamicLogicVisible:` is used. The condition expressions go
through Prompt A's parser/validator/evaluator.

### Prompt E — `emailTemplates`

Entity-level block. New `email_template_manager.py`. Models: parse
`email_templates_raw` into `list[EmailTemplate]`. Body-file
resolution: read `bodyFile:` paths relative to the program YAML;
hash for drift detection. Merge-field validation: every entry in
`mergeFields:` must be a real field on the named `entity`; every
`{{placeholder}}` in subject and body must be in `mergeFields:`;
no unused merge fields. CHECK→ACT against EspoCRM's email template
API. **Important:** Prompt B's duplicate-check `alertTemplate:`
references resolve here — defer the cross-block resolution check
to load order (templates loaded before duplicate checks evaluate
their references), or implement a two-pass validator. Note the
choice in the prompt.

### Prompt F — `formula` (the biggest)

Field-level. Three formula types: `aggregate`, `arithmetic`,
`concat`. New module `formula_parser.py` (or split into
`formula_aggregate.py`, `formula_arithmetic.py`, `formula_concat.py`
if cleaner). The arithmetic mini-parser is the only nontrivial
parser in the series — recommend a small recursive-descent
implementation rather than pulling in a dependency. Field-reference
validation across all three types. `formula:` requires
`readOnly: true` — validator enforces. CHECK→ACT against EspoCRM's
formula API (every CRM expresses calculated fields differently;
the deploy manager translates the structured YAML into the
target's syntax). Multi-hop `join:` traversals validate
hop-by-hop. Reference Prompt A's relative-date module for
`where:` clauses inside aggregates.

### Prompt G — `workflows`

Entity-level block. New `workflow_manager.py`. Models: parse
`workflows_raw` into `list[Workflow]`. Trigger vocabulary:
`onCreate`, `onUpdate`, `onFieldChange`, `onFieldTransition`,
`onDelete` (note: `onFirstTransition` deferred to v1.2). Action
vocabulary: `setField`, `clearField`, `sendEmail`,
`sendInternalNotification` (note: `createRelatedRecord` deferred).
Cross-block validations: `sendEmail.template:` resolves against
the entity's `emailTemplates:` block (Prompt E). `setField.value:`
accepts literal, `now`, or arithmetic expression — reuse Prompt
F's arithmetic parser. `where:` and trigger conditions reuse
Prompt A's parser. CHECK→ACT against EspoCRM's workflow API.

### Prompt H — `externallyPopulated` flag

The smallest prompt. Field-level boolean. No new manager module.
Loader already stashes it from Prompt A. Validator: nothing to
add — the flag has no constraints (per the prior session's
explicit decision to drop the trivial validation rule). The real
work in Prompt H is on the **Verification Spec generator**: when
generating a Verification Spec (Phase 13 output), group all
`externallyPopulated: true` fields under an "External Integration
Dependencies" section, listing them by entity with their
descriptions. Find and modify the existing Verification Spec
generator (look in `tools/docgen/` or wherever the Phase 13
output is built).

## Acceptance criteria for this drafting session

1. Seven new files exist under
   `PRDs/product/yaml-schema-prompts/`, named per the convention
   `CLAUDE-CODE-PROMPT-yaml-v1.1-{letter}-{descriptor}.md` with
   `{letter}` in `{B, C, D, E, F, G, H}`.
2. Each prompt references the spec doc and Prompt A explicitly.
3. Each prompt names the files to create or modify, the modules
   involved, the test coverage areas, and acceptance criteria.
4. Each prompt restates the cross-cutting concerns concisely.
5. Each prompt's "out of scope" section names the v1.2 deferrals
   relevant to that prompt.
6. All seven prompts committed and pushed to `main`.

## What to confirm with Doug at session start

- Has Prompt A been executed yet? (If not, this session shouldn't
  proceed — see pre-flight item 5.)
- Commit-per-prompt or batch commit at the end?
- Any series-level changes since the prior session (e.g., did the
  Prompt A run surface anything that changes the series shape)?

## What NOT to do

- Don't restate the spec inside any prompt — reference it.
- Don't include code samples in B–H unless absolutely necessary.
  The spec already has the YAML examples.
- Don't include test counts. Coverage areas only.
- Don't try to draft Prompt I or beyond. The series is exactly
  eight prompts (A through H); v1.2 work is a separate series.
- Don't modify `app-yaml-schema.md` v1.1, the gap analysis, or
  Prompt A. Those are settled deliverables. If any genuinely needs
  a fix discovered during drafting, stop and ask Doug.
- Don't begin executing any of the prompts in this session. This
  session drafts only.
