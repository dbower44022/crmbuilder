# CLAUDE-CODE-PROMPT — yaml-v1.1-E — Entity `emailTemplates:` Block

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:30
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Section 5.7
(`emailTemplates:`); Section 10 "Email-template-level" validation
rules.
**Foundation:** Prompt A stashed `email_templates_raw` on
`EntityDefinition`. Prompt B's `duplicateChecks:` may reference
templates via `alertTemplate:` — B deferred the cross-block
resolution to this prompt.

## Position in the Series

Implements gap-analysis Category 7 (Email Templates). This prompt
is a prerequisite for Prompt G (Workflows), whose `sendEmail`
action references templates declared here.

## Scope

In scope:

1. Parse `email_templates_raw` into a typed
   `list[EmailTemplate]` on each entity.
2. Full validation per spec Section 10 "Email-template-level":
   - Unique `id` within entity.
   - `name`, `entity`, `subject`, `bodyFile`, and `mergeFields`
     are required.
   - `entity:` must match the parent entity block's key.
   - `bodyFile:` path must resolve to an existing HTML file
     relative to the program YAML's `source_path`.
   - Every entry in `mergeFields:` must be a real field on
     `entity`.
   - Every `{{placeholder}}` in `subject:` and the body file
     must be listed in `mergeFields:`.
   - Every entry in `mergeFields:` must be used at least once
     in `subject:` or the body file (no unused merge fields).
3. Body-file resolution: read `bodyFile:` content at load time
   (or validation time — whichever is cleaner), resolve the path
   relative to `ProgramFile.source_path`, and hash the content
   for drift detection.
4. Cross-block `alertTemplate:` resolution: now that the email
   template registry exists on each entity, add a validation
   pass that checks every `duplicateChecks[].alertTemplate`
   value against the entity's `emailTemplates[]` IDs. This is
   the deferred work from Prompt B.
5. New manager module `espo_impl/core/email_template_manager.py`
   — CHECK→ACT against the EspoCRM email-template API. Uploads
   template metadata (name, subject, entity) plus body content
   read from the HTML file.
6. Wire the manager into the run/verify orchestration. Email
   templates must be deployed **before** duplicate checks
   (because `alertTemplate:` references must resolve on the CRM
   at deploy time) and **before** workflows (Prompt G). Adjust
   the orchestration order established in Prompt B accordingly:
   `EntitySettings` → `EmailTemplates` → `DuplicateChecks` →
   `SavedViews` → fields/layouts/relationships.
7. Drift detection: template absent on CRM → create; template
   present but body content hash differs → update; template on
   CRM not in YAML → drift report (do not silently delete).
8. Tests covering parsing, validation (including merge-field
   completeness), body-file resolution, cross-block alertTemplate
   check, manager CHECK→ACT, and drift detection.

Out of scope:

- `audience:` field enforcement — per spec Section 5.7, this is
  a free-form documentation string in v1.1. Full role-based
  audience handling arrives in v1.2 with Category 6.
- Template body *authoring* — the YAML registers templates; the
  HTML content is authored by humans outside the tool.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- `EmailTemplate` properties are defined in spec Section 5.7's
  table.
- Body-file format and merge-field placeholder syntax
  (`{{fieldName}}`) are defined in spec Section 5.7 "Body file
  format" and "Merge-field validation".
- Per-domain file location conventions are defined in spec
  Section 5.7 "Per-domain file location".
- All validation rules referenced here are spelled out in spec
  Section 10 "Email-template-level".

## Cross-Cutting Concerns

- **Pure-logic discipline.** All new logic lives in
  `espo_impl/core/` with no GUI dependencies. Tests are
  pure-logic.
- **Validator integration.** Email-template validation is added
  to `config_loader.py`'s `validate_program` path. The cross-
  block `alertTemplate:` check is a second-pass validator that
  runs after both `emailTemplates:` and `duplicateChecks:` are
  parsed.
- **Drift detection.** `email_template_manager.py` implements
  CHECK→ACT against the EspoCRM API. Body-file hashing enables
  content-drift detection without uploading the full body on
  every run.
- **Field reference validation.** Every entry in `mergeFields:`
  must be a real field on `entity`. Placeholder extraction from
  subject and body uses a regex for `{{...}}` patterns.
- **Backward compatibility.** v1.0 YAML files have no
  `emailTemplates:` block; their behavior is unchanged.

## Files to Create

1. `espo_impl/core/email_template_manager.py` — EmailTemplate
   CHECK→ACT.
2. `tests/test_email_templates.py` — parsing, validation, body-
   file resolution, cross-block alertTemplate check, manager.

## Files to Modify

1. `espo_impl/core/models.py` — add `EmailTemplate` dataclass.
   Add a typed field on `EntityDefinition`:
   - `email_templates: list[EmailTemplate] = field(default_factory=list)`

   The existing `email_templates_raw` field stays populated.

2. `espo_impl/core/config_loader.py` — parse
   `email_templates_raw` into the typed list during
   `load_program`. Add `_validate_email_templates` helper per
   spec Section 10. Add the cross-block `alertTemplate:`
   resolution check (iterate each entity's `duplicate_checks`
   and confirm any `alertTemplate` value matches an `id` in the
   same entity's `email_templates`).

3. The run/verify orchestration entry point — reorder to place
   email templates before duplicate checks and saved views, per
   scope #6 above.

4. `espo_impl/core/reporter.py` and `RunSummary` in `models.py`
   — extend to surface email-template outcomes (created /
   updated / skipped / drift).

## Test Coverage Areas

For `tests/test_email_templates.py`:

- Parsing: fully-populated template; template with optional
  `description` and `audience` fields; multiple templates per
  entity.
- Validation: duplicate `id` within entity; missing required
  fields (`name`, `entity`, `subject`, `bodyFile`, `mergeFields`);
  `entity:` mismatch with parent entity key; `bodyFile:` path
  that does not resolve to an existing file.
- Merge-field validation: merge field not a real field on entity;
  `{{placeholder}}` in subject not in `mergeFields:`; placeholder
  in body file not in `mergeFields:`; merge field listed but
  never used in subject or body.
- Cross-block alertTemplate: `alertTemplate:` on a duplicate-check
  rule that matches an email template ID → passes; value that
  does not match → validation error naming the duplicate-check
  rule and the missing template ID; `alertTemplate:` absent →
  no error.
- Body-file resolution: relative path resolves correctly from
  `ProgramFile.source_path`; body content is read and hashed.
- Manager CHECK→ACT: template absent on CRM → create (metadata +
  body uploaded); template present and matching (same hash) →
  skip; template present but body hash differs → update;
  template on CRM not in YAML → drift report.
- Idempotency on second run.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `EntityDefinition` carries a typed
   `email_templates: list[EmailTemplate]` field in addition to
   the existing raw field.
3. `ConfigLoader.load_program` parses `emailTemplates:` and
   populates the typed field; `validate_program` enforces every
   Section 10 "Email-template-level" rule including merge-field
   completeness.
4. The cross-block `alertTemplate:` resolution check (deferred
   from Prompt B) is implemented and tested.
5. Orchestration order places email templates before duplicate
   checks and saved views.
6. Run/verify orchestration applies email-template changes with
   results surfaced through the reporter and counted in
   `RunSummary`.
7. All existing tests continue to pass.
8. New tests cover the coverage areas above.
9. `uv run ruff check espo_impl/ tests/` passes clean.
10. `uv run pytest tests/ -v` passes.
11. Commit and push to `main` with a clear message referencing
    this prompt and the spec.

## Reporting Back

When finished, report:

- New file paths and line counts
- New tests added (counts and brief coverage summary)
- Total test count before → after, ruff status
- Commit hash and message
- Any deviations from this prompt's specification (and why)
- Any open questions or follow-ups for Prompts F–H, especially
  anything affecting the Prompt G sendEmail action's template
  resolution
