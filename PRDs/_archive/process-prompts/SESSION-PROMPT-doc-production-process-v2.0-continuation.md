# SESSION-PROMPT — Document Production Process v2.0 — Continuation

**Goal:** Execute the approved v2.0 rewrite of
`PRDs/process/CRM-Builder-Document-Production-Process.docx` and the
companion update to `CLAUDE.md`. All design decisions below were
finalized in the 04-11-26 design session and are **not** open for
rediscussion — go straight to execution.

## Before starting

1. Confirm CLAUDE.md to read: **crmbuilder root**.
2. `git pull` crmbuilder.
3. Unpack current docx with `/mnt/skills/public/docx/scripts/office/unpack.py`.
4. The current document is internally labeled **v1.7** (Last Updated
   `04-04-26 21:30`), not v1.6. New label is **v2.0**, Replaces **v1.7**.

## Approved decisions (all final, do not reopen)

### D1 — Phase structure (13 phases)

| # | Phase | Source |
|---|---|---|
| 1 | Master PRD | unchanged |
| 2 | Domain Discovery | NEW — replaces old Phase 2 front half |
| 3 | Inventory Reconciliation | NEW |
| 4 | Domain Overview + Process Definition | merged old 3.3 + 3.5; single phase, two activities |
| 5 | Entity PRDs | moved from old 3.2 back half to post-process |
| 6 | Cross-Domain Service Definition | was Phase 4 |
| 7 | Domain Reconciliation | was Phase 6 |
| 8 | Stakeholder Review | was Phase 7 |
| 9 | YAML Generation | was Phase 8 |
| 10 | CRM Selection | was Phase 9 |
| 11 | CRM Deployment | was Phase 10 |
| 12 | CRM Configuration | was Phase 11 |
| 13 | Verification | was Phase 12 |

Phase 4 is ONE phase with two activities described within it, not 4a/4b.

### D2 — Version, revision note

- Header: Version **2.0**, Status Current, Last Updated `MM-DD-YY HH:MM`
  (actual completion timestamp), Replaces **v1.7**.
- Revision history: new **Section 11 "Revision History"** at the end of
  the document (after current Section 10). First entry is v2.0 with:
  - Four summary bullets: mission-anchored framing explicit; entity rule
    restated (sketch early, define late); Personas introduced as
    first-class; early phases restructured (Domain Discovery +
    Inventory Reconciliation + merged Domain Overview/Process Definition).
  - Phase renumbering table: old # → new #, all 12 old phases → 13 new.

### D3 — Domain definition and numbered rules

- **Section 1 Purpose** gets a new paragraph after the existing opening,
  exactly (verbatim):

  > The methodology is mission-anchored, not technology-anchored.
  > Requirements belong to the business, are captured in business terms,
  > and are expressed independently of any specific CRM product. A
  > domain is one of the big questions the mission forces the
  > organization to answer — not a department, not a screen, not a
  > feature of a product. The full definition and the validation test
  > appear in Phase 2 as Rule 2.1.

- **Phase 2 Domain Discovery** contains:
  - **Rule 2.1 — Domain Validation Test.** "If this area of work stopped
    tomorrow, would the mission be in trouble? If yes → domain. If no →
    probably a process or a cross-domain service."
  - **Rule 2.2 — Persona Backing Rule.** Every persona is either backed
    by an entity record in the system, or declared External (an outside
    role not tracked as data).

- **Phase 5 Entity PRDs** contains:
  - **Rule 5.1 — Entity Definition Timing** (verbatim):

    > Entities are identified and sketched during Phase 2 Domain
    > Discovery to establish shared vocabulary, and reconciled in
    > Phase 3. Full Entity PRDs — including complete field lists,
    > relationships, and business rules — are produced only in Phase 5,
    > after the Phase 4 process documents that use the entities have
    > been drafted. Process documents may reference entity names and
    > obvious fields from the reconciled Entity Inventory without
    > waiting for the full PRD.

Rules are formatted as bold inline labels (`**Rule N.N — Name.**`)
followed by the rule text, matching existing doc tone. No shaded
callout boxes.

### D4 — Phase 2 / Phase 3 artifacts

- Phase 2 output: **single** `PRDs/Domain-Discovery-Report.docx` with
  three sections: Domain List, Candidate Entity Inventory, Candidate
  Persona Inventory.
- Phase 3 outputs: **two** separate durable docs —
  `PRDs/Entity-Inventory.docx` and `PRDs/Persona-Inventory.docx`.
  Finalized domain list folds back into the Master PRD (updates the
  existing domains section in place).
- Both phase 3 outputs live at the PRDs root alongside Master PRD.
- Section 6 Repository Structure must be updated to show these three
  new artifacts at the PRDs root.

### D5 — Persona Inventory schema

Each persona entry has these fields (both candidate and reconciled):

| Field | Required | Notes |
|---|---|---|
| Persona Name | Yes | Human-readable |
| Persona ID | Yes | `PER-NNN`, assigned in Phase 3, implementation-wide scope |
| Backing | Yes | Entity reference (e.g. `Contact / contactType=mentor`) or `External` |
| Description | Yes | 1–3 sentences |
| Source | Yes | Stakeholder name, document, or interview |
| Notes | No | Disambiguation / aliases / merge history |

### D6 — Phase 3 session count

One session by default. Phase body states: "Inventory Reconciliation is
normally a single client-facing session covering both inventories,
because personas are defined in terms of entities. Split into two
sessions only if (a) the candidate inventories together exceed roughly
40 items, or (b) stakeholder availability forces it."

### D7 — Section 10 rewrites (preserve 10.1, 10.3–10.6 as-is except cross-refs)

**New 10.2 — New Entity Discovered During Process Definition** (verbatim):

> Under v2.0, entities are sketched in Phase 2 and reconciled in Phase 3
> before process work begins. If a process conversation (Phase 4)
> surfaces an entity not present in the reconciled Entity Inventory,
> stop the process conversation. The implementer adds the entity to the
> Entity Inventory as a late addition (flagged with source = Phase 4
> discovery and the process code that surfaced it), notes whether any
> existing persona's Backing field should change, and then resumes the
> process conversation. The inventory is updated in place; the change
> is summarized in the Entity Inventory's change log but does not
> require a new reconciliation session unless the addition invalidates
> a previously reconciled decision.

**New 10.7 — New Persona Discovered During Process Definition**
(verbatim):

> Same protocol as 10.2, applied to the Persona Inventory. Because
> Rule 2.2 requires every persona to be backed by an entity or declared
> External, the implementer must also confirm the Backing field at the
> time the persona is added. If the new persona's backing is an entity
> that is itself new, handle 10.2 first, then 10.7.

- Old 10.7 "New Cross-Domain Service Discovered" → renumber to **10.8**.
- Old 10.8 "Principle" → renumber to **10.9**.
- Section 10 now has 9 subsections.

### D8 — Cross-reference sweep

All cross-references to phase numbers throughout Sections 4–9 must be
updated to new numbers. Specifically scan for "Phase N" mentions and
remap using D1's old → new table. Do not assume any cross-reference is
still accurate.

### D9 — CLAUDE.md update (same commit)

Replace the "Document Production Process" section of crmbuilder root
`CLAUDE.md` with:

1. **Process Summary:** new 13-phase code block matching D1 exactly.
2. **Key Principles:** replace old bullet "Entities are defined before
   processes..." with: "Entities are sketched early in Phase 2 Domain
   Discovery, reconciled in Phase 3, and fully defined only in Phase 5
   after the processes that use them are drafted (see Rule 5.1)." Add
   new bullet: "Personas are first-class alongside entities; every
   persona is backed by an entity record or declared External (see
   Rule 2.2)."
3. **PRD Content Rules:** unchanged.
4. **At the Start of Every Requirements Session:** unchanged.
5. Pointer line updated to reference v2.0.

Show Doug the exact replacement text before applying.

## Deliverables

1. Updated `PRDs/process/CRM-Builder-Document-Production-Process.docx`
   at v2.0.
2. Updated `CLAUDE.md` Document Production Process section.
3. Single commit to crmbuilder: `Update Document Production Process to v2.0`.
4. Present both files.

## Output standards reminders

- Arial throughout, header background `#1F3864`, title/heading color
  `#1F3864`, alternating row shading `#F2F7FB`, borders `#AAAAAA`.
- No product names (EspoCRM, WordPress, etc.).
- "Last Updated" format `MM-DD-YY HH:MM`.
- Human-readable-first identifiers throughout.
- Use `pack.py --original` flag when repacking.
- Smart quotes in XML: use `&#x2019;` entity form for Python string
  matching.
- Bold inline labels require split runs with `<w:b/>` and `<w:bCs/>`.

## Out of scope

- Client-facing kickoff script (separate follow-up doc).
- Interview guides, templates, Automation L2 PRD.
- CBM repo changes.

## Working style

One issue at a time during execution, but design is locked — do not
reopen D1–D9. Commit at the end after Doug's final review.
