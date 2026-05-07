# CRMBuilder v2 — Status

**Last Updated:** 05-07-26 00:37
**Status:** Active

**Revision Control:** This document is a living status snapshot updated as project state changes. The "Last Updated" field above reflects the most recent revision; prior states are recoverable through git history.

---

## Current Phase

**Phase:** Planning (pre-build)

**Sub-step:** Planning dimensions 1 through 5 resolved. Dimensions 6, 7, and 8 remain. Step 0 (schema design) has not yet started.

---

## v1 / v2 / Transition Inventory

### What's in v2

- `charter.md` v0.2 — scope, name, architectural foundations, current state, open planning items (Open Planning Items trimmed at v0.2 to reflect dimension #5 resolution)
- `decisions.md` — DEC-001 through DEC-016, architectural and operational decisions
- `sessions.md` — SES-001 (initial planning) and SES-002 (planning dimension #5)
- `status.md` — this document
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — bootstrap prompt
- `prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md` — planning dimension #5 prompt

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

None currently active. The next active work is planning dimension #6 (division of labor) in a new conversation.

---

## Pending — Immediate

None. Planning dimension #5 is complete after this prompt executes.

## Pending — Planning

- Planning dimension #6 — division of labor
- Planning dimension #7 — risk register
- Planning dimension #8 — exit criteria
- Project-structure split decision (Claude Project, repository) — deferred to end of planning per DEC-012

## Pending — Build (gated by planning completion)

- Step 0 — schema design (project management schema first, methodology schema second; references vocabulary; validation rules)
- Step 1 — storage layer build (SQLite, Python access layer, REST API, MCP server, JSON export hook)
- Step 2 — MN domain migration as proving ground
- Step 3 — test infrastructure first deliverable (CRUD layer)
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
