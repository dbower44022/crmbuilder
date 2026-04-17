# CLAUDE-CODE-PROMPT — yaml-v1.1-H — `externallyPopulated:` Flag and Verification Spec Generator Skeleton

**Repo:** `crmbuilder`
**Series:** `yaml-v1.1` (eight-prompt sequence implementing
`PRDs/product/app-yaml-schema.md` v1.1)
**Last Updated:** 04-15-26 04:45
**Spec:** `PRDs/product/app-yaml-schema.md` v1.1 — Section 6.1.4
(`externallyPopulated:`).
**Foundation:** Prompt A stashed `externally_populated` as a bool
on `FieldDefinition`. No further parsing or validation is needed
for the flag itself.

## Position in the Series

Implements gap-analysis Category 10 (Integrations — the
`externallyPopulated:` flag only). This is the final prompt in
the series and the smallest in terms of new schema logic. Its
primary deliverable is the **Verification Spec generator
skeleton** — the first builder for a Phase 13 output document
that does not yet exist in the codebase.

## Context — Verification Spec Generator

The existing `tools/docgen/` generates Implementation Docs (the
CRM Reference document) from YAML program files. There is no
Phase 13 Verification Spec generator yet. This prompt creates the
skeleton: a new entry point and a first builder that produces an
"External Integration Dependencies" section by scanning all
entities for `externallyPopulated: true` fields. The full
Verification Spec generator is future work beyond this series;
this prompt establishes the pattern and the first section.

## Scope

In scope:

1. The `externallyPopulated` flag on `FieldDefinition` is already
   loaded by Prompt A (a boolean, defaults to `false`). No
   additional parsing or validation needed — the prior session's
   explicit decision dropped the trivial validation rule.
2. Deploy-time behavior: the flag is purely informational and
   produces no changes to the target CRM's field configuration.
   Confirm that `field_manager.py` does not attempt to send
   `externallyPopulated` as a field property to the CRM API.
3. **Verification Spec generator skeleton:**
   - New entry point: `tools/generate_verification_spec.py`
     (parallel to the existing `tools/generate_docs.py`). Takes
     the same `--programs` argument pointing to a directory of
     YAML program files.
   - New builder:
     `tools/docgen/builders/verification_spec_builder.py` —
     scans all loaded entities for fields where
     `externally_populated is True`. Groups them by entity.
     For each field, outputs: field name, field label, field
     type, and the field's `description:` (which per spec
     Section 6.1.4 should note which external system populates
     it).
   - Output: a Markdown document (using the existing
     `md_renderer`) with a title, generation timestamp, and the
     "External Integration Dependencies" section. The document
     structure should be extensible — future prompts will add
     additional sections (field-by-field verification checklists,
     workflow verification, etc.).
   - If no `externallyPopulated: true` fields exist in any
     entity, the section should say so explicitly rather than
     being silently absent.
4. Tests covering: the builder correctly identifies and groups
   externally-populated fields; the builder handles zero
   externally-populated fields; the entry point produces a
   Markdown file; end-to-end from YAML fixtures through the
   generator to output content verification.

Out of scope:

- Full Verification Spec content beyond the "External Integration
  Dependencies" section — that is future work.
- DOCX rendering of the Verification Spec — Markdown is
  sufficient for the skeleton. DOCX rendering can be added when
  the full spec generator is built.
- Import-data expectations (the spec notes that
  `externallyPopulated` fields are skipped in seed-data import
  expectations) — this is import_manager territory and is not
  changed by this prompt.
- Any UI changes — none planned in v1.1.

## Spec Authority

This prompt implements `app-yaml-schema.md` v1.1. Where this
prompt and the spec disagree, the spec wins. In particular:

- The flag's effects are defined in spec Section 6.1.4: skipped
  in seed-data import expectations, grouped in Verification Spec
  output, purely informational at deploy time.
- The field's `description:` is the source for which external
  system populates it — per spec Section 6.1.4.

## Cross-Cutting Concerns

- **Pure-logic discipline.** The builder is pure logic with no
  GUI dependencies. The entry point script follows the same
  pattern as `generate_docs.py`.
- **Backward compatibility.** v1.0 YAML files have no
  `externallyPopulated:` fields; the generator produces an empty
  section rather than failing.

## Files to Create

1. `tools/generate_verification_spec.py` — entry point for
   Verification Spec generation.
2. `tools/docgen/builders/verification_spec_builder.py` —
   "External Integration Dependencies" section builder.
3. `tests/test_verification_spec.py` — builder logic, entry
   point integration, edge cases.

## Files to Modify

1. `espo_impl/core/field_manager.py` — confirm (and add a guard
   if needed) that `externally_populated` is not sent to the CRM
   API as a field property. If the existing code already skips
   unknown properties, document that in a code comment.

## Test Coverage Areas

For `tests/test_verification_spec.py`:

- Builder identifies `externallyPopulated: true` fields from a
  multi-entity YAML fixture.
- Builder groups fields by entity, listing field name, label,
  type, and description for each.
- Builder produces a meaningful "no externally-populated fields"
  message when none exist.
- Builder handles mixed entities: some with externally-populated
  fields, some without.
- Entry point produces a Markdown file at the expected output
  path.
- End-to-end: YAML fixture with known externally-populated fields
  → generated Markdown contains the expected entity names, field
  names, and descriptions.

No specific test counts are required; the coverage areas above
are the bar.

## Acceptance Criteria

1. New files exist at the paths listed under "Files to Create".
2. `field_manager.py` confirmed not to send
   `externallyPopulated` to the CRM API (with a code comment
   noting the intentional omission if one is not already present).
3. `tools/generate_verification_spec.py` runs successfully
   against a directory of YAML program files and produces a
   Markdown document.
4. The generated document contains an "External Integration
   Dependencies" section that lists all `externallyPopulated:
   true` fields grouped by entity, with field name, label, type,
   and description.
5. The document structure is extensible (additional sections can
   be added by future prompts without restructuring the entry
   point or builder pattern).
6. All existing tests continue to pass.
7. New tests cover the coverage areas above.
8. `uv run ruff check espo_impl/ tools/ tests/` passes clean.
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
- Summary of the full yaml-v1.1 series: all eight prompts (A–H)
  now committed, listing what each delivered
