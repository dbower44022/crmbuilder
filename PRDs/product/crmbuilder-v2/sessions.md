# CRMBuilder v2 — Session Records

**Last Updated:** 05-07-26 00:37
**Status:** Active

**Revision Control:** This document is an append-only log. Each new SES-NNN entry constitutes a revision; the "Last Updated" field above reflects the most recent addition.

---

## SES-001: Initial Planning — Project Identity, Architecture, and Initial Artifacts

**Date:** 05-06-26
**Status:** Complete
**Conversation reference:** Claude.ai session (transcript preserved separately if needed)

**Topics covered:** v2 project identity, methodology rearchitecture rationale, storage architecture (SQLite + REST API + MCP server), universal references pattern, topics table, session orientation protocol, charter structure, decisions log structure, CBM as test case

**Summary:**

Started as a request to create a functional testing routine for CRM Builder YAML processing. Through iterative reframing during the conversation, the scope evolved into a substantially larger architectural redesign — a structured database as source of truth for all CRM implementation artifacts (methodology and project management both), with Word documents, deployment YAML, and test cases as renders.

Key reframes during the conversation, in order:

- Testing system → behavior-driven testing → cross-cutting persona/process testing → end-to-end PRD-to-deployed-CRM verification with feedback loop to Claude Code
- Word documents as source → structured database as source
- Project artifacts as markdown documents → project artifacts as database records (dogfooding)
- YAML files in git → SQLite + REST API + MCP server (real database)
- MCP-direct → layered (REST API as durable interface, MCP as Claude.ai bridge)
- Topics as one of many junction tables → universal references pattern with controlled relationship vocabulary

Working through the eight planning dimensions:

- Resolved #1 (project identity) including all sub-questions A–F
- Resolved #2.1 (session orientation protocol)
- Substantially resolved #2.3, #2.4, #3 by virtue of the database architecture
- Collapsed #4 (CBM coexistence) — CBM is the test case, not parallel commitment
- Did not address #5–#8 (deferred to future conversations)

**Decisions made:** DEC-001 through DEC-011 (see `decisions.md`)

**Artifacts produced:**

- `charter.md` (draft v0.1)
- `decisions.md` (draft v0.1, capturing DEC-001 through DEC-011)
- `sessions.md` (this record)
- `status.md` (draft v0.1)

**In-flight at session end:**

- All four governance artifacts drafted and committed via the v2-A bootstrap prompt
- v2 home directory `PRDs/product/crmbuilder-v2/` created
- CLAUDE.md updated with v2 routing section
- Planning dimensions #5–#8 unresolved
- Step 0 (schema design) not started

**Next step:**

In a new conversation, continue with planning dimension #5 (pacing, cadence, milestones). Subsequent conversations cover #6, #7, #8. After all eight planning dimensions are resolved, Step 0 (schema design) begins.

---

## SES-002: Planning Dimension #5 — Pacing, Cadence, and Milestones

**Date:** 05-07-26
**Status:** Complete
**Conversation reference:** Claude.ai session (transcript preserved separately if needed)

**Topics covered:** working session anatomy, session-to-conversation mapping, artifact-per-session rule, cadence model, definition of done, gating between phases, project-structure split (Claude Project and repository) — deferred

**Summary:**

Worked through the four sub-questions of planning dimension #5. A side discussion about whether the next iteration of CRMBuilder should move to a separate Claude Project (giving v2 design conversations a clean memory slate) or a separate GitHub repository was deferred to the end of planning, after dimensions #6 through #8 are resolved. The remaining sub-questions resolved cleanly:

- Anatomy of a working session: orient using the tiered orientation protocol established in the bootstrap, discuss in plain text one issue at a time, close with a Claude Code prompt that lands a commit. One Claude.ai conversation equals one session, which produces exactly one session record. Multi-conversation topics are reconstructed by reading the chronological sequence of session records that touch the topic. Every conversation that engages v2 produces a session record, even brief or exploratory ones.
- Cadence: ad-hoc. No fixed schedule. Sessions happen when the work is ready. Long gaps between sessions are expected; the "in-flight at session end" capture in each session record is the load-bearing mechanism for clean resumption.
- Milestones: the phase list already enumerated in the status document — schema design (Step 0), storage layer build (Step 1), MN domain migration as the proving ground (Step 2), then MR / CR / FU migrations in priority order, with test infrastructure layered in alongside.
- Definition of done and gating: Doug reviews each phase's output. Proceed if it works, iterate within the current step if it doesn't, stop and reassess if the approach can't be made to work. No formal checklist per phase; judgment based on whether the output works.

A communication rule was also added to Claude's stored memory during this session: Claude must never reference identifiers, codes, or shorthand tags without explaining what they mean in plain English. This is a working-style rule rather than a v2 architectural decision and is captured in stored memory rather than the v2 decisions log.

**Decisions made:** DEC-012 through DEC-016 (see `decisions.md`)

**Artifacts produced:**

- This session record (SES-002)
- DEC-012 through DEC-016 in `decisions.md`
- `status.md` updated to reflect dimension #5 resolution
- `charter.md` updated (v0.1 → v0.2) — Current State and Open Planning Items sections trimmed to reflect dimension #5 resolution
- `prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md` saved as the executing prompt

**In-flight at session end:**

- Planning dimensions #6 (division of labor), #7 (risk register), #8 (exit criteria) remain unresolved
- Project-structure decision (Claude Project split, repository split) deferred to end of planning per DEC-012
- Step 0 (schema design) not yet started

**Next step:**

In a new conversation, take up planning dimension #6 (division of labor) — boundaries between Claude.ai work, Claude Code work, and Doug-only work, and the handoff protocol between modes.
