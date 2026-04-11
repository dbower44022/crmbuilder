# SESSION-PROMPT — Document Production Process v2.0 — Continuation (Part 2)

**Goal:** Complete the v2.0 rewrite of `PRDs/process/CRM-Builder-Document-Production-Process.docx` and the companion `CLAUDE.md` update. Step 1 of the original plan is already committed; this session picks up at Step 2.

**Predecessor prompt:** `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation.md` — read it in full. All design decisions D1–D9 in that prompt are **final and locked**. Do not reopen them.

## Before starting

1. Confirm CLAUDE.md to read: **crmbuilder root**.
2. `git pull` crmbuilder.
3. Unpack `PRDs/process/CRM-Builder-Document-Production-Process.docx` with `/mnt/skills/public/docx/scripts/office/unpack.py`.
4. The document is still internally labeled **v1.7** in the header table, but Section 1 Purpose already contains the mission-anchored paragraph inserted by Step 1 of the predecessor session. Do **not** re-insert it. Verify it is present by grepping for "mission-anchored" in `word/document.xml` before doing anything else. If absent, stop and escalate — the prior commit did not land as expected.

## Execution plan — resume at Step 2

Execute these steps in order, pausing for Doug's approval between each one per his working-style preference. Design is locked; pauses are for review of actual edits, not rediscussion.

**Step 2 — Section 2 Process Overview rewrite.** Replace the 12-row phase table and its surrounding narrative with the new 13-phase structure per D1. Phase 4 is one phase titled "Domain Overview + Process Definition" (not 4a/4b). Update the narrative sentences about which phases repeat per domain and per service to match the new numbering.

**Step 3 — Section 3 Phase Details rewrite.** This is the largest edit.
- 3.1 Master PRD: unchanged content, still numbered 3.1.
- 3.2 Domain Discovery (NEW): replaces old 3.2 Entity Definition content entirely. Output is a single `PRDs/Domain-Discovery-Report.docx` with three sections: Domain List, Candidate Entity Inventory, Candidate Persona Inventory. Includes **Rule 2.1 — Domain Validation Test** and **Rule 2.2 — Persona Backing Rule** verbatim from D3. Includes the Persona Inventory schema table from D5 (Persona Name, Persona ID `PER-NNN`, Backing, Description, Source, Notes).
- 3.3 Inventory Reconciliation (NEW): produces two durable root-level artifacts `PRDs/Entity-Inventory.docx` and `PRDs/Persona-Inventory.docx`; finalized domain list folds back into Master PRD in place. Body includes the D6 single-session-by-default language verbatim.
- 3.4 Domain Overview + Process Definition (merged): one phase with two activities described in its body. Content derived from merging old 3.3 Domain Overview and old 3.5 Process Definition. Single subsection number 3.4.
- 3.5 Entity PRDs (NEW, moved): produced post-process. Includes **Rule 5.1 — Entity Definition Timing** verbatim from D3.
- 3.6 Cross-Domain Service Definition: content from old 3.4, renumbered.
- 3.7 Domain Reconciliation: content from old 3.6, renumbered.
- 3.8 Stakeholder Review: content from old 3.7, renumbered.
- 3.9 YAML Generation: old 3.8.
- 3.10 CRM Selection: old 3.9.
- 3.11 CRM Deployment: old 3.10.
- 3.12 CRM Configuration: old 3.11.
- 3.13 Verification: old 3.12.

Rules are formatted as bold inline labels (`Rule N.N — Name.`) using split runs with `<w:b/>` and `<w:bCs/>`, followed by rule text in the same paragraph. No shaded callout boxes.

**Step 4 — Cross-reference sweep (D8).** Scan Sections 4–9 for every "Phase N" mention and remap using the D1 old→new table. Do not assume any cross-reference is still accurate. Grep for `Phase 1` through `Phase 12` in `word/document.xml` and audit each hit.

**Step 5 — Section 6 Repository Structure update (D4).** Show `PRDs/Domain-Discovery-Report.docx`, `PRDs/Entity-Inventory.docx`, and `PRDs/Persona-Inventory.docx` at the PRDs root alongside Master PRD.

**Step 6 — Section 10 rewrites (D7).** Preserve 10.1 and 10.3–10.6 content except for phase-number cross-refs updated in Step 4. Insert new **10.2 — New Entity Discovered During Process Definition** verbatim from D7. Insert new **10.7 — New Persona Discovered During Process Definition** verbatim from D7. Renumber old 10.7 → **10.8** and old 10.8 → **10.9**. Section 10 ends with 9 subsections.

**Step 7 — New Section 11 Revision History (D2).** Added at the end of the document after current Section 10. First entry is v2.0 with four summary bullets (mission-anchored framing explicit; entity rule restated — sketch early, define late; Personas introduced as first-class; early phases restructured) and a phase renumbering table showing old # → new # for all 12 old phases mapped to 13 new phases.

**Step 8 — Header version update (D2).** Version `2.0`, Status `Current`, Last Updated `MM-DD-YY HH:MM` (actual completion time), Replaces `v1.7`.

**Step 9 — CLAUDE.md update (D9).** Replace the entire "Document Production Process" section of crmbuilder root `CLAUDE.md`. Current content is stale — it still shows an 11-phase structure, not 12. Full replacement text per D9: new 13-phase code block matching D1 exactly; Key Principles bullet replacement about entity timing + new bullet about Personas first-class with reference to Rule 2.2; PRD Content Rules unchanged; At the Start of Every Requirements Session unchanged; pointer line updated to v2.0. **Show Doug the exact replacement text before applying.**

**Step 10 — Validate, commit, present.**
- Pack with `pack.py --original`, verify validations pass, and verify with pandoc that the key strings are present (Rule 2.1, Rule 2.2, Rule 5.1, new 10.2, new 10.7, Revision History).
- Commit to crmbuilder with message: `Update Document Production Process to v2.0`
- `present_files` on both the docx and `CLAUDE.md`.

## Output standards reminders

- Arial throughout, header background `#1F3864`, title/heading color `#1F3864`, alternating row shading `#F2F7FB`, borders `#AAAAAA`.
- No product names (EspoCRM, WordPress, etc.) anywhere in the document.
- "Last Updated" format `MM-DD-YY HH:MM`.
- Human-readable-first identifiers throughout.
- Smart quotes in XML stored as `&#x2019;`; em-dash as `&#x2014;`.
- Bold inline labels require split runs with `<w:b/>` and `<w:bCs/>`.
- Within `<w:tcPr>`: element order tcW → tcBorders → shd → tcMar → vAlign.

## Out of scope (unchanged)

Client-facing kickoff script; interview guides, templates, Automation L2 PRD; CBM repo changes.

## Working style

One step at a time, pause for approval between steps. Design locked — no reopening of D1–D9. Single commit at the end.
