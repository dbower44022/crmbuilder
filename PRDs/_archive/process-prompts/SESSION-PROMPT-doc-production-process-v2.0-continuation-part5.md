# SESSION-PROMPT — Document Production Process v2.0 — Continuation (Part 5)

**Goal:** Continue the v2.0 rewrite of `PRDs/process/CRM-Builder-Document-Production-Process.docx` from where Part 4's session left off. Steps 1, 2, 3b, 3c (4 new subsections + 3.6 rewordings), and Step 4 (cross-reference sweep) are complete and committed to branch `wip/doc-prod-v2.0`. This session executes **Steps 5 through 10**.

## Predecessor prompts (read in order)

1. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation.md` — design decisions D1–D9 (locked).
2. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part2.md` — original 10-step execution plan.
3. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part3.md` — corrected strategy for Step 2.
4. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part4.md` — Step 3c plan.
5. **This file** — picks up at Step 5.

## State at the start of this session

* **Branch:** `wip/doc-prod-v2.0`, tip `a050f94` (off `main`). **Check out this branch first.**
* **Important context from Part 4 session:** The WIP branch commits were pushed directly to `main` during Part 3, so `main` and `wip/doc-prod-v2.0` diverge only in the Step 3c + Step 4 commits now. The "squash-merge into a single clean commit" plan from the original Part 4 prompt **is no longer achievable** and has been abandoned. Step 10 in this prompt uses **fast-forward merge** instead (see below).
* **Header:** still reads `v1.7` / `04-04-26 21:30`. Version bump and "Last Updated" timestamp are deferred until Step 8.

## Commits made in Parts 3 and 4 (for context)

| Commit | Contents |
|---|---|
| `9b51ae4` | Step 1: Section 1 Purpose mission-anchored paragraph |
| `c12ccd5` | Steps 1+2+3b: Section 2 Phase Overview rebuilt to 13 phases, old 3.2–3.6 headings cleared |
| `3d2aecc` | Step 3c.1: New 3.2 Phase 2 Domain Discovery (incl. Persona Inventory schema table, Rules 2.1 & 2.2) |
| `b6110f3` | Step 3c.2: New 3.3 Phase 3 Inventory Reconciliation |
| `367ef23` | Step 3c.3: New 3.4 Phase 4 Domain Overview + Process Definition (merged from old 3.3 + Sub-Domain Overviews + old 3.5; Required Sections table preserved verbatim; Context Passing H3s renamed; 3 cross-ref rewordings applied) |
| `3f9c534` | Step 3c.4: New 3.5 Phase 5 Entity PRDs (incl. Rule 5.1) |
| `8767515` | Step 3c.5: 3.6 cross-ref rewordings (service entity lifecycle + Phase 5/Domain Discovery refs) |
| `2f83504` | Step 4 partial: Section 10.2 "Entity Definition" references reworded |
| `a050f94` | Step 4: Section 7.2 Context Requirements table fully rewritten (16 rows, aligned with 13-phase v2.0 model) |

## Working style (unchanged)

* One issue at a time, pause for Doug's approval between steps.
* Design D1–D9 is locked. Do not reopen.
* Confirm CLAUDE.md to read at session start: **crmbuilder root**.
* Show Doug the exact CLAUDE.md replacement text before applying (per D9 and per Doug's user preferences).
* Do **NOT** use `ask_user_input` popup widgets. Plain-text discussion only. (Doug's user preferences.)
* Discuss one topic at a time; wait for explicit approval before moving to the next.
* After completing any step, explicitly state the next required step and ask for confirmation before proceeding.

## Step 5 — Section 6 (Repository Structure) updates

The v2.0 model introduced three new root-level artifacts that Section 6 must reflect:

* `PRDs/Domain-Discovery-Report.docx` — working artifact from Phase 2 (not durable but should be referenced).
* `PRDs/Entity-Inventory.docx` — durable inventory from Phase 3.
* `PRDs/Persona-Inventory.docx` — durable inventory from Phase 3.

**Recommended approach:**
1. Read-only dump of Section 6's current structure (paragraphs, lists, any file-tree representation).
2. Identify what file references currently exist and what's missing under v2.0.
3. Surface proposed additions/edits to Doug for approval.
4. Apply edits and commit as `WIP: Document Production Process v2.0 — Step 5 (Section 6 Repository Structure)`.

**Known context from Part 4 scan:** Section 6 had zero "Phase N" or old-phase-name references — its content was already in terms of file paths, not phase numbers. The Part 4 scan did flag two paragraphs (tokens 249–250 at scan time) that mention Domain Overview and Sub-Domain Overview — these appear fine as prose but should be reviewed in context.

## Step 6 — Section 8 (Key Design Decisions) updates

Section 8 is a table of Decision / Rationale pairs. Part 4 verified one existing row is correct ("Phase 7" and "Phase 8" references — both accurate in v2.0). This step should record any new design decisions from D1–D9 that aren't already captured, or replace stale rows.

**D1–D9 design decisions to consider for inclusion** (from the original Part 4 continuation prompt — confirm with Doug which, if any, should be recorded in Section 8):
* D1: Old-to-new phase remapping table (likely not appropriate for Section 8; more of an internal-transition artifact)
* D2–D9: Whatever specific decisions these captured (need to re-read the Part 1 continuation prompt for exact content)

**Recommended approach:** Read-only dump of current Section 8 rows, identify which are stale / which v2.0 decisions are unrepresented, propose additions to Doug, apply and commit as `WIP: Document Production Process v2.0 — Step 6 (Section 8 Key Design Decisions)`.

## Step 7 — Section 9 (Document Hierarchy) rewrite

**Part 4 explicitly deferred this step.** Section 9 currently lists levels 1, 2, 4a, 4b, 7, 9 using the *old* numbering and does not mention the Persona Inventory or Domain Discovery Report at all. This is a structural rewrite, not a sweep.

**Key considerations:**
* v2.0 has 13 phases but the Document Hierarchy's "levels" don't need to map 1:1 to phases — levels represent document abstraction, not phases. Need to decide the new level-numbering scheme with Doug.
* Must add: Domain Discovery Report, Persona Inventory.
* Must update: Level 7 (YAML) → now Phase 9 output; Level 9 (Configured CRM) → now Phase 12 output. Level numbers themselves may need renumbering.
* Candidate new hierarchy (needs Doug's approval):
  1. Master PRD
  2. Domain Discovery Report (working artifact)
  3. Entity Inventory
  4. Persona Inventory
  5. Domain Overview (4a) / Sub-Domain Overview (4b)
  6. Process documents / Entity PRDs / Service PRDs
  7. Domain PRDs
  8. YAML Program Files
  9. CRM Evaluation Report
  10. Configured CRM Instance

**Recommended approach:** Draft the new hierarchy for Doug's review first, iterate on structure, then rewrite the Section 9 content. Commit as `WIP: Document Production Process v2.0 — Step 7 (Section 9 Document Hierarchy rewrite)`.

## Step 8 — Header bump to v2.0

* Update header version from `v1.7` to `v2.0`.
* Update "Last Updated" timestamp in `MM-DD-YY HH:MM` format (per Doug's user preferences).
* Confirm exact timestamp with Doug before stamping.
* Commit as `Update Document Production Process to v2.0`.

## Step 9 — CLAUDE.md update

Per D9 (locked in Part 1), the crmbuilder repo root `CLAUDE.md` needs updates reflecting the v2.0 process doc. Show Doug the exact replacement text before applying. Likely touches:

* Any numbered list referencing the 12-phase model → update to 13-phase.
* Any phase-name references (Entity Discovery, Entity Definition) → remap.
* References to document-production-process version number.

**Recommended approach:** Dump current CLAUDE.md, diff against v2.0 content, propose targeted edits to Doug, apply. Commit separately as `Update CLAUDE.md for Document Production Process v2.0`.

## Step 10 — Final review + fast-forward `main`

**Changed from original plan.** Squash-merge is no longer viable (history on `main` already contains WIP commits). Use **fast-forward merge** instead:

1. Final eyes-on review of the full docx on `wip/doc-prod-v2.0` by Doug before merge.
2. `git checkout main && git merge --ff-only wip/doc-prod-v2.0` — fast-forward `main` to the WIP tip. This should succeed cleanly because `main` and the WIP branch share history up through `c12ccd5` and the WIP branch has only added commits on top.
3. `git push origin main`.
4. Delete WIP branch locally and on origin: `git branch -d wip/doc-prod-v2.0 && git push origin --delete wip/doc-prod-v2.0`.
5. Verify `main` tip is the v2.0 header-bump commit.

## Reminders for the next session

* The WIP branch is the source of truth until Step 10.
* Use `pack.py --original <original.docx>` so styles are preserved on every repack.
* Table rebuilds: use the Part 4 pattern — find a representative row, use it as a template, rebuild all rows from scratch rather than attempting surgical cell-by-cell edits.
* Cross-reference scans must walk both `<w:p>` and `<w:tbl>` siblings in document order, not just `<w:p>`.
* Header style constants (for any new H2/H3 authoring): Heading2 `spacing after="160" before="280"`, color `1F3864`, size 24, Arial. Heading3 `after="120" before="240"`, size 22. Body text 11pt Arial. Table borders `#AAAAAA`, header fill `#1F3864` with white bold text, alt row shading `#F2F7FB`.
* Bold inline labels: split runs with `<w:b/>` and `<w:bCs/>` in `<w:rPr>`.
* Every document change gets committed to `wip/doc-prod-v2.0` with a `WIP: Document Production Process v2.0 — Step N (...)` message, except Steps 8, 9, and 10 which use their own finalized messages.

## Out of scope (unchanged)

Client-facing kickoff script; interview guides; templates; Automation L2 PRD; CBM repo changes.
