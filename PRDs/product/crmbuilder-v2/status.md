# CRMBuilder v2 — Status

**Last Updated:** 05-07-26 15:30
**Status:** Active

**Revision Control:** This document is a living status snapshot updated as project state changes. The "Last Updated" field above reflects the most recent revision; prior states are recoverable through git history.

---

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial status established alongside charter and decisions log via the v2-A bootstrap. |
| 0.2 | 05-07-26 | Updated for planning dimension #5 resolution (SES-002). |
| 0.3 | 05-07-26 | Storage system v0.1 build started. Planning dimensions #6/#7/#8 paused; build resumes them after v0.1 retires the markdown source-of-truth. |

---

## Current Phase

**Phase:** Build (storage system v0.1, in progress)

**Sub-step:** Implementing the four-layer storage stack per `storage-system-PRD-v0.1.md` and `storage-system-implementation-plan.md`. Acceptance criteria #1–#8 in the PRD define done.

**Note on planning dimensions #6 / #7 / #8:** Resolution of these three remaining planning dimensions is paused until v0.1 retires the markdown source-of-truth. Once the database is operational, those dimensions are re-engaged, and their resolution lands as database records (decision rows, planning-item rows) rather than markdown updates.

---

## v1 / v2 / Transition Inventory

### What's in v2

- `charter.md` v0.2 — scope, name, architectural foundations, current state, open planning items (Open Planning Items trimmed at v0.2 to reflect dimension #5 resolution). Slated for migration into the v0.1 database; markdown removed in the migration commit.
- `decisions.md` — DEC-001 through DEC-016, architectural and operational decisions. Slated for migration; markdown removed in the migration commit.
- `sessions.md` — SES-001 and SES-002. Slated for migration; markdown removed in the migration commit.
- `status.md` — this document. Slated for migration; markdown removed in the migration commit.
- `storage-system-PRD-v0.1.md` — storage system v0.1 requirements (stays in markdown; this is a PRD, not bootstrapped governance content).
- `storage-system-implementation-plan.md` — Claude Code's implementation plan companion to the PRD (stays in markdown).
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — bootstrap prompt
- `prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md` — planning dimension #5 prompt
- `prompts/CLAUDE-CODE-PROMPT-v2-B-storage-system.md` — storage system v0.1 build prompt (executing now)

### What's in v1 (unchanged)

The following remain in v1 form and are explicitly NOT part of v2 work:

- The crmbuilder PySide6 desktop application code (`espo_impl/`, `automation/`)
- The existing methodology guides (`PRDs/process/interviews/`, `PRDs/process/CRM-Builder-Document-Production-Process.docx`)
- The existing app-level product specs (`PRDs/product/CRMBuilder-PRD.md`, `PRDs/product/app-*.md`)
- The engine pluggability planning (`PRDs/product/crmbuilder-automation-PRD/engine-pluggability-planning.md`)
- The CBM client repo and all its content (`ClevelandBusinessMentoring/PRDs/`, `ClevelandBusinessMentoring/programs/`)

### What's in transition

None at this stage. v2 has not yet begun migrating any v1 artifacts.

---

## Active Work

Storage system v0.1 build (this conversation), per `storage-system-PRD-v0.1.md` and `storage-system-implementation-plan.md`.

---

## Pending — Immediate

- Acceptance criteria #1–#8 from `storage-system-PRD-v0.1.md` Section 8 (in-progress).

## Pending — Planning (paused until v0.1 lands)

- Planning dimension #6 — division of labor
- Planning dimension #7 — risk register
- Planning dimension #8 — exit criteria
- Project-structure split decision (Claude Project, repository) — deferred to end of planning per DEC-012

## Pending — Build (after v0.1)

- Step 0 follow-on — methodology entity schema (personas, entities, fields, processes, requirements, manual-config items, test specifications)
- Renderers — Word, YAML, test cases generated from the database (DEC-008)
- Application integration — CRMBuilder PySide6 reads/writes against the v2 database
- MN domain migration as proving ground (per DEC-010)
- Test infrastructure first deliverable (CRUD layer)
- Subsequent: MR, CR, FU migration; integration / process / UI test layers; methodology guide evolution; application UI changes

---

## Blockers

None at this stage. The architecture is defined sufficiently for the next planning conversation to proceed; no external dependencies block forward motion.

---

## Reading Order for New Sessions

Per DEC-011 (session orientation protocol):

**Tier 1:** `crmbuilder/CLAUDE.md`

**Tier 2 (when v2 work is engaged, before the MCP server exists):**

1. `status.md` — current state (this file)
2. `charter.md` — project scope and architectural foundations
3. `sessions.md` — most recent session(s), starting from the latest
4. `decisions.md` — referenced on demand when sessions reference DEC-NNN

**Tier 2 (once the MCP server exists):** Replace the file reads above with MCP queries (`get_status`, `get_charter`, `get_recent_sessions`, `get_decisions`).
