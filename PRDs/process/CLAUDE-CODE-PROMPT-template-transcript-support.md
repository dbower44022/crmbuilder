# CLAUDE-CODE-PROMPT: Template Transcript Support

**Date:** 04-11-26
**Repo:** `dbower44022/crmbuilder`
**Files touched:**
- `PRDs/process/templates/generate-process-doc-template.js`
- `PRDs/process/templates/generate-entity-prd-template.js`

## Background

On 04-11-26 the four interview guides in `PRDs/process/interviews/`
were updated to require an Interview Transcript section in every
produced document:

- `interview-master-prd.md` v1.3 — Section 6 Interview Transcript
- `guide-entity-definition.md` v1.3 — Section 6 (Entity Inventory)
  and Section 10 (Entity PRD) Interview Transcript
- `interview-process-definition.md` v2.4 — Section 11 Interview
  Transcript (already specified since v2.3)
- `guide-domain-reconciliation.md` v1.2 — Section 7 Interview
  Transcript scoped to the reconciliation conversation only

The Master PRD, Entity Inventory, and Domain PRD are hand-authored
in Claude.ai sessions and have no generator templates. The two
files this prompt modifies are the only generator templates that
exist.

When this audit was performed, two gaps were found:

1. **`generate-process-doc-template.js`** is severely out of date.
   It only emits Sections 1–6 of the process document, but the
   v2.4 guide specifies 11 sections. Patching only Section 11
   would leave a four-section gap and produce a document that
   silently omits Process Completion, Open Issues, and Updates to
   Prior Documents. The right fix is a full catch-up to v2.4.

2. **`generate-entity-prd-template.js`** emits Sections 1–9 and is
   missing only Section 10 Interview Transcript.

## Tasks

### Task 1 — Read the guides first

Before touching either template file, read both interview guides
in full:

- `PRDs/process/interviews/interview-process-definition.md` (v2.4)
- `PRDs/process/interviews/guide-entity-definition.md` (v1.3)

Derive the authoritative section list for each produced document
from these guides, **not** from this prompt. If anything in this
prompt contradicts the guides, the guides win — flag the conflict
in your final summary rather than silently choosing one.

### Task 2 — Bring `generate-process-doc-template.js` up to v2.4

The template currently emits Sections 1–6 with hardcoded MN-INTAKE
sample content. Replace it with a stub template that:

1. **Emits all 11 sections** of the v2.4 process document, in
   the order and with the exact section names specified in
   `interview-process-definition.md` v2.4.
2. **Replaces the hardcoded MN-INTAKE sample content with empty
   section stubs.** Each section should contain a single
   placeholder paragraph (e.g., `p("[Content for this section
   goes here.]")`) and any required structural elements
   (sub-headings, empty tables) as documented in the guide.
3. **Preserves the existing helper functions** (`heading`, `p`,
   `fieldTable`, etc.) and the existing document setup
   (numbering, styles, page setup, header/footer). Do not
   refactor these.
4. **Adds a leading comment block** at the top of the file
   explaining that this is a template meant to be copied per
   process, the source-of-truth guide is
   `interview-process-definition.md` v2.4, and the section list
   should be kept in sync with that guide on future updates.
5. **Section 11 (Interview Transcript)** stub should include a
   sub-heading for one example topic group with placeholder Q/A
   pair and a placeholder Decision callout, so users see the
   intended format. Use the format spec in Section 11 of the
   v2.4 guide.

The empty-stub approach is deliberate. The previous hardcoded
MN-INTAKE content has likely drifted from the current
MN-INTAKE.docx in the CBM repo and is no longer authoritative;
do not attempt to update it. If you find it valuable as a
reference, save it to a sibling file
`generate-process-doc-template-EXAMPLE-mn-intake.js` rather than
deleting it outright — but this is optional, the priority is
getting the stub template right.

### Task 3 — Add Section 10 Interview Transcript to `generate-entity-prd-template.js`

The template currently emits Sections 1–9 (ending at Decisions
Made). Add **Section 10: Interview Transcript** as a new section
immediately after Section 9, following the format spec in the
"Interview Transcript Format" subsection of `guide-entity-definition.md` v1.3.

Requirements:
1. Use the same `heading("10. Interview Transcript", HeadingLevel.HEADING_1)`
   pattern as the existing sections.
2. Emit a placeholder topic-group subheading
   (HeadingLevel.HEADING_2), followed by a placeholder Q/A pair
   and a placeholder Decision callout, so users see the intended
   format.
3. Make **no other changes** to Sections 1–9. This is a purely
   additive change.
4. Update the section-list comment block at the top of the file
   (lines ~20–30, where Sections 1–9 are listed) to include
   Section 10.

### Task 4 — Verification

After making the changes:

1. Run `node generate-process-doc-template.js` and
   `node generate-entity-prd-template.js` to confirm both
   produce valid `.docx` output without errors. Open the
   produced files (or use a docx unpacker) to verify the
   section structure matches the guides.
2. Run `uv run ruff check` and `uv run pytest tests/ -v` to
   confirm no regressions in the wider repo. (These templates
   are not Python and are not covered by ruff/pytest, but the
   sanity check is still worth doing.)

### Task 5 — Commit and PR

Stage the two modified template files (and the optional
`-EXAMPLE-mn-intake.js` file if you chose to preserve the
hardcoded sample). Commit on a feature branch with this message:

```
Bring document-generation templates in sync with v2.4/v1.3 guides

- generate-process-doc-template.js: full catch-up to
  interview-process-definition.md v2.4 (11 sections), replacing
  hardcoded MN-INTAKE sample with empty section stubs. Adds
  Sections 7-11 including Interview Transcript with format
  example.
- generate-entity-prd-template.js: add Section 10 Interview
  Transcript per guide-entity-definition.md v1.3. Purely
  additive; Sections 1-9 unchanged.

Brings both templates into parity with the interview guides
updated on 04-11-26.
```

Open a PR against `main` and report the PR URL in your final
summary.

## Out of scope

- Do not modify any `.docx` files in the CBM repo. Existing
  hand-authored documents (Master PRD, Entity Inventory,
  Domain PRDs, Entity PRDs, process docs) are not being
  retroactively updated.
- Do not modify any interview guide files. They were committed
  in `f0804a9` on 04-11-26 and are the source of truth for this
  prompt.
- Do not modify any code under `espo_impl/`, `tools/`, or
  `tests/`. This prompt is scoped strictly to the two template
  files in `PRDs/process/templates/`.
- Do not add Section 11 / Section 10 transcript support to any
  hand-authored document templates — there are no other
  generator templates in the repo.

## Final summary requirements

In your final report, include:

1. The PR URL.
2. The exact section list emitted by the updated process
   template, with the section name and heading level for each.
3. The exact section list emitted by the updated entity
   template, with the section name and heading level for each.
4. Any conflicts you found between this prompt and the guides,
   and which you chose.
5. Confirmation that both templates produce valid `.docx`
   output and that `ruff` and `pytest` still pass on the wider
   repo.
