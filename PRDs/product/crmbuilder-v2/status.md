# CRMBuilder v2 — Status

**Last Updated:** 05-06-26 19:28
**Status:** Active

**Revision Control:** This document is a living status snapshot updated as project state changes. The "Last Updated" field above reflects the most recent revision; prior states are recoverable through git history.

---

## Current Phase

**Phase:** Planning (pre-build)

**Sub-step:** Initial planning conversation complete and bootstrap committed. Planning dimensions 1, 2.1, 2.3, 2.4, 3, and 4 resolved (some explicitly, some by virtue of the database architecture). Dimensions 5–8 remain. Step 0 (schema design) has not yet started.

---

## v1 / v2 / Transition Inventory

### What's in v2

- `charter.md` v0.1 — scope, name, architectural foundations, current state, open planning items
- `decisions.md` v0.1 — DEC-001 through DEC-011, architectural decisions from initial planning
- `sessions.md` v0.1 — SES-001, the initial planning conversation record
- `status.md` v0.1 — this document
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — the prompt that produced this initial state

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

None currently active. The bootstrap commit lands the planning work as durable artifacts; the next active work begins in the next conversation when planning dimension #5 (pacing) is taken up.

---

## Pending — Immediate

None. The bootstrap is complete after this prompt executes.

## Pending — Planning

- Planning dimension #5 — pacing, cadence, milestones
- Planning dimension #6 — division of labor
- Planning dimension #7 — risk register
- Planning dimension #8 — exit criteria

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
