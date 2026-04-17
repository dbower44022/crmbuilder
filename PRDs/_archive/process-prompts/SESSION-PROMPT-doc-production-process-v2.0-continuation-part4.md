# SESSION-PROMPT — Document Production Process v2.0 — Continuation (Part 4)

**Goal:** Continue the v2.0 rewrite of `PRDs/process/CRM-Builder-Document-Production-Process.docx` from where Part 3's session left off. Steps 1, 2, and 3b are complete and committed to branch `wip/doc-prod-v2.0`. This session executes **Step 3c onward** (author and splice the four new/merged subsections, then Steps 4–10).

## Predecessor prompts (read in order)

1. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation.md` — design decisions D1–D9 (locked, do not reopen).
2. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part2.md` — original 10-step execution plan.
3. `PRDs/process/SESSION-PROMPT-doc-production-process-v2.0-continuation-part3.md` — corrected execution strategy for Step 2.
4. **This file** — picks up at Step 3c.

## State at the start of this session

- **Branch:** `wip/doc-prod-v2.0` (off `main`). The Part 3 session committed Steps 1+2+3b here. **Check out this branch first** — do not work on `main`.
- **Header:** still reads `v1.7` / `04-04-26 21:30`. Version bump and "Last Updated" timestamp are deferred until the end of the v2.0 rewrite.
- **Section 1 (Purpose):** mission-anchored paragraph already inserted (Step 1).
- **Section 2 (Process Overview):** rebuilt to 13-phase structure (Step 2). Phase table is correct, narrative paragraphs updated.
- **Section 3 (Phase Details) current heading structure:**
  - 3.1 Phase 1: Master PRD ✅
  - **[GAP — new 3.2, 3.3, 3.4, 3.5 to be authored in Step 3c]**
  - 3.6 Phase 6: Cross-Domain Service Definition (renumbered from old 3.4)
  - 3.7 Phase 7: Domain Reconciliation (renumbered from old 3.6)
  - 3.8 Phase 8: Stakeholder Review (renumbered from old 3.7; internal "Phase 6" cross-ref bumped to "Phase 7")
  - 3.9 Phase 9: YAML Generation (renumbered from old 3.8; internal "Phase 8" cross-ref bumped to "Phase 9")
  - 3.10 Phase 10: CRM Selection
  - 3.11 Phase 11: CRM Deployment
  - 3.12 Phase 12: CRM Configuration
  - 3.13 Phase 13: Verification
- **Final commit plan:** branch will be **squash-merged** into `main` at the very end as a single commit `Update Document Production Process to v2.0`. The WIP branch is then deleted. Do not regular-merge.

## Working style (unchanged)

- One issue at a time, pause for Doug's approval between steps.
- Design D1–D9 is locked. Do not reopen.
- Confirm CLAUDE.md to read at session start: **crmbuilder root**.
- Show Doug the exact CLAUDE.md replacement text before applying (per D9).

## Step 3c — author and splice new subsections 3.2, 3.3, 3.4, 3.5

The four new subsections must be inserted in the document **between the end of 3.1 (Master PRD) and the start of 3.6 (Cross-Domain Service Definition)**. After Step 3b's deletions, there is a clean gap there — no orphan paragraphs to clean up.

### New 3.2 Phase 2: Domain Discovery

Heading2: `3.2 Phase 2: Domain Discovery`

Body covers domain identification, candidate entity capture, and candidate persona capture in a single phase. Output is `PRDs/Domain-Discovery-Report.docx` containing three sections: Domain List, Candidate Entity Inventory, Candidate Persona Inventory.

Must embed (verbatim, bold inline rule labels via split runs with `<w:b/>` and `<w:bCs/>`):

> **Rule 2.1 — Domain Validation Test.** If this area of work stopped tomorrow, would the mission be in trouble? If yes → domain. If no → probably a process or a cross-domain service.

> **Rule 2.2 — Persona Backing Rule.** Every persona is either backed by an entity record in the system, or declared External (an outside role not tracked as data).

Must embed the **Persona Inventory schema table** (D5) as a real Word table — three columns (Field, Required, Notes), six rows: Persona Name (Yes / Human-readable), Persona ID (Yes / `PER-NNN`, assigned in Phase 3, implementation-wide scope), Backing (Yes / Entity reference like `Contact / contactType=mentor`, or `External`), Description (Yes / 1–3 sentences), Source (Yes / Stakeholder name, document, or interview), Notes (No / Disambiguation, aliases, merge history). Use the same table styling as the Section 2 phase table for consistency.

### New 3.3 Phase 3: Inventory Reconciliation

Heading2: `3.3 Phase 3: Inventory Reconciliation`

Body covers the reconciliation activity. Outputs are two durable root-level artifacts `PRDs/Entity-Inventory.docx` and `PRDs/Persona-Inventory.docx`, plus the finalized domain list folded back into the Master PRD in place.

Must embed verbatim (D6 single-session-by-default language):

> Inventory Reconciliation is normally a single client-facing session covering both inventories, because personas are defined in terms of entities. Split into two sessions only if (a) the candidate inventories together exceed roughly 40 items, or (b) stakeholder availability forces it.

### New 3.4 Phase 4: Domain Overview + Process Definition

Heading2: `3.4 Phase 4: Domain Overview + Process Definition`

Brief framing paragraph stating this is a single phase with two activities. Then two Heading3 subsections:

- **Heading3 "Domain Overview Activity"** — body merged from salvaged old 3.3 Domain Overview content + the orphan Sub-Domain Overviews content folded in as ordinary prose (per Doug's option (a) decision in Part 4 design — no separate sub-heading for Sub-Domain Overviews).
- **Heading3 "Process Definition Activity"** — body from salvaged old 3.5 Process Definition content.

The salvaged content is preserved verbatim in `step3b-salvage.json` in the previous session's local workspace, but that file does NOT survive a session reset. The salvaged paragraphs need to be re-extracted from the **previous commit on `main`** (the parent of this WIP branch) at `PRDs/process/CRM-Builder-Document-Production-Process.docx`. Do this with:

```
git show main:PRDs/process/CRM-Builder-Document-Production-Process.docx > /tmp/old.docx
python3 /mnt/skills/public/docx/scripts/office/unpack.py /tmp/old.docx /tmp/old-unpacked
```

Then walk paragraphs in `/tmp/old-unpacked/word/document.xml` and capture the bodies of:
- H2 `3.3 Phase 3: Domain Overview` through next H2
- H2 `Sub-Domain Overviews` through next H2
- H2 `3.5 Phase 5: Process Definition` through next H2

When merging old 3.3 + Sub-Domain Overviews + old 3.5 into new 3.4, audit each old paragraph for `Phase N` cross-references and remap per the D1 old→new table:
- Old Phase 2 (Entity Definition) → split: usually maps to new Phase 5 (Entity PRDs) or Phase 3 (Inventory Reconciliation) depending on context
- Old Phase 3 (Domain Overview) → new Phase 4
- Old Phase 4 (Cross-Domain Service Definition) → new Phase 6
- Old Phase 5 (Process Definition) → new Phase 4 (since Process Definition is now an activity within Phase 4)
- Old Phase 6 (Domain Reconciliation) → new Phase 7

Pause and surface any non-mechanical remappings to Doug before applying.

### New 3.5 Phase 5: Entity PRDs

Heading2: `3.5 Phase 5: Entity PRDs`

Body covers full Entity PRD production after process documents are drafted. Brief paragraphs on input (reconciled Entity Inventory + Phase 4 process documents), output (one Entity PRD per entity), conversation count (1 per entity), and the standard for PRD content (complete field lists, relationships, business rules).

Must embed verbatim:

> **Rule 5.1 — Entity Definition Timing.** Entities are identified and sketched during Phase 2 Domain Discovery to establish shared vocabulary, and reconciled in Phase 3. Full Entity PRDs — including complete field lists, relationships, and business rules — are produced only in Phase 5, after the Phase 4 process documents that use the entities have been drafted. Process documents may reference entity names and obvious fields from the reconciled Entity Inventory without waiting for the full PRD.

## Step 3c — deferred semantic cross-ref decisions in new 3.6

After splicing 3.2–3.5, two sentences in new 3.6 (Cross-Domain Service Definition) body still reference old "Phase 2 (Entity Definition)" and need semantic rewording. Surface both to Doug with proposed rewordings before editing:

1. *"Service entities are defined in Phase 2 (Entity Definition) alongside domain entities."*
   - **Proposed:** *"Service entities are sketched in Phase 2 (Domain Discovery), reconciled in Phase 3 (Inventory Reconciliation), and fully defined in Phase 5 (Entity PRDs) alongside domain entities."*

2. *"This applies both when services are identified after Phase 2 has been completed and when service process definition reveals entities not anticipated during the original Entity Discovery."*
   - **Proposed:** *"This applies both when services are identified after Phase 5 has been completed and when service process definition reveals entities not anticipated during the original Domain Discovery."* (Note: "Entity Discovery" → "Domain Discovery" because the old phase name no longer exists.)

## Steps 4–10 (still pending after 3c)

- **Step 4 — Cross-reference sweep (D8).** Scan Sections 4–9 for every `Phase N` mention, audit each hit, remap per D1 old→new.
- **Step 5 — Section 6 (Repository Structure) updates** for any path or file changes implied by the new artifacts (`Domain-Discovery-Report.docx`, `Entity-Inventory.docx`, `Persona-Inventory.docx` at `PRDs/` root).
- **Step 6 — Section 8 (Key Design Decisions) updates** to record the D1–D9 decisions or replace stale ones.
- **Step 7 — Section 9 (Document Hierarchy) updates** to reflect the new phase set.
- **Step 8 — Header bump** to v2.0 with "Last Updated" timestamp in `MM-DD-YY HH:MM` format. Confirm exact timestamp with Doug before stamping.
- **Step 9 — CLAUDE.md update** at the crmbuilder repo root per D9. Show Doug the exact replacement text before applying.
- **Step 10 — Final review, squash-merge to `main`.** Squash-merge `wip/doc-prod-v2.0` into `main` as a single commit `Update Document Production Process to v2.0`. Delete the WIP branch locally and on origin. Verify `main` builds clean.

## Reminders for the next session

- The WIP branch is the source of truth — never work on `main` directly during this rewrite.
- Salvage content for Step 3c must be re-extracted from `main:PRDs/process/CRM-Builder-Document-Production-Process.docx` (instructions above).
- Use the "rebuild whole subsection from freshly authored XML" discipline from Part 3, not chained `str.replace()` on cell or run text.
- Header style for Heading2: `spacing after="160" before="280"`, color `1F3864`, size 24, Arial. Heading3: `after="120" before="240"`, size 22.
- Bold inline rule labels: split runs with `<w:b/>` and `<w:bCs/>` in `<w:rPr>`.
- Pack with `pack.py --original <original.docx>` so styles are preserved.

## Out of scope (unchanged)

Client-facing kickoff script; interview guides, templates, Automation L2 PRD; CBM repo changes.
