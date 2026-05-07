# CLAUDE-CODE-PROMPT-v2-B-pacing

## Purpose

Land the resolution of planning dimension #5 (pacing, cadence, milestones) into the v2 governance artifacts. Append the second session record to the sessions log, append five new decision entries (one for the project-structure deferral and four for the operational rules established by dimension #5), update the status document to reflect the resolution, update the charter to reflect the change in remaining open planning items, save this prompt into the prompts directory, and commit the result with the `v2:` subject prefix. Do not push.

## Project context

CRMBuilder v2 is in pre-build planning. The bootstrap commit (v2-A) landed the four governance artifacts and added the v2 routing section to the top-level CLAUDE.md. Planning dimension #5 was the second session of the project; it resolved the question of what a working session looks like, the cadence model, the milestone list, and the definition of done and gating between phases. A side discussion about whether the next iteration of CRMBuilder should move to a separate Claude Project (clean memory) or a separate GitHub repository was deferred to the end of planning, after dimensions #6 through #8 are resolved.

This prompt records the conversation's outcomes as durable artifacts in the repo.

## Pre-flight

1. Confirm working directory is the crmbuilder repo clone.
2. Confirm `git status` is clean. If there are uncommitted changes, stop and report to Doug before proceeding.
3. Confirm git identity is set: `git config user.email` should be `doug@dougbower.com` and `git config user.name` should be `Doug Bower`. If not set or set to a different value, configure with these exact values.
4. Pull latest from origin: `git pull --rebase origin main`.
5. Confirm the four governance artifacts exist at their expected locations:
   - `PRDs/product/crmbuilder-v2/charter.md`
   - `PRDs/product/crmbuilder-v2/decisions.md`
   - `PRDs/product/crmbuilder-v2/sessions.md`
   - `PRDs/product/crmbuilder-v2/status.md`
   - `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md`

   If any are missing, stop and report.

## Tasks

In every task below, replace `HH:MM` with the current time in 24-hour format (e.g., `14:30`). Use today's date `05-07-26` for the `Last Updated` fields and any new dated entries.

### Task 1 — Append SES-002 to `sessions.md`

Two `str_replace` operations on `PRDs/product/crmbuilder-v2/sessions.md`. Both anchors must match exactly (verbatim, including whitespace). If either anchor fails to match, stop and report — do not attempt a fallback.

**Operation 1A — Update `Last Updated` at top of file.**

`old_str`:

```
# CRMBuilder v2 — Session Records

**Last Updated:** 05-06-26 19:28
**Status:** Active
```

`new_str`:

```
# CRMBuilder v2 — Session Records

**Last Updated:** 05-07-26 HH:MM
**Status:** Active
```

**Operation 1B — Append the SES-002 record at end of file.**

`old_str` (the existing final paragraph of the file):

```
**Next step:**

In a new conversation, continue with planning dimension #5 (pacing, cadence, milestones). Subsequent conversations cover #6, #7, #8. After all eight planning dimensions are resolved, Step 0 (schema design) begins.
```

`new_str` (the existing paragraph plus the new SES-002 record appended):

```
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
```

### Task 2 — Append DEC-012 through DEC-016 to `decisions.md`

Three `str_replace` operations on `PRDs/product/crmbuilder-v2/decisions.md`.

**Operation 2A — Update `Last Updated` and add change log row.**

`old_str`:

```
# CRMBuilder v2 — Decisions Log

**Last Updated:** 05-06-26 19:28
**Status:** Active

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial decisions log capturing architectural decisions DEC-001 through DEC-011 from the planning conversation. |
```

`new_str`:

```
# CRMBuilder v2 — Decisions Log

**Last Updated:** 05-07-26 HH:MM
**Status:** Active

## Change Log

| Version | Date | Description |
|---------|------|-------------|
| 0.1 | 05-06-26 | Initial decisions log capturing architectural decisions DEC-001 through DEC-011 from the planning conversation. |
| 0.2 | 05-07-26 | Added DEC-012 through DEC-016 from planning dimension #5 conversation (project-structure split deferred; session-to-conversation mapping; every conversation produces a session record; cadence is ad-hoc; definition of done and gating model). |
```

**Operation 2B — Extend the Index section.**

`old_str`:

```
- DEC-009: CBM as test case, not parallel commitment
- DEC-010: CBM migration order — MN, then MR, then CR, then FU
- DEC-011: Session orientation protocol — tiered

---
```

`new_str`:

```
- DEC-009: CBM as test case, not parallel commitment
- DEC-010: CBM migration order — MN, then MR, then CR, then FU
- DEC-011: Session orientation protocol — tiered
- DEC-012: Project-structure split (Claude Project, repository) deferred to end of planning
- DEC-013: Session-to-conversation mapping — one conversation, one session record, append-only
- DEC-014: Every v2 conversation produces a session record
- DEC-015: Cadence is ad-hoc, no fixed schedule
- DEC-016: Definition of done and gating model — Doug review at phase boundaries

---
```

**Operation 2C — Append the five full decision records at end of file.**

`old_str` (the closing paragraph of DEC-011, which is the last content in the file):

```
**Consequences:** CLAUDE.md update required to document the protocol. Sessions table schema must support "what was in flight at end of session" so the next session resumes cleanly. Bootstrap window before MCP exists requires fallback to reading the v2 directory listing and most recent session transcript.
```

`new_str` (the existing closing paragraph plus all five new decision records):

```
**Consequences:** CLAUDE.md update required to document the protocol. Sessions table schema must support "what was in flight at end of session" so the next session resumes cleanly. Bootstrap window before MCP exists requires fallback to reading the v2 directory listing and most recent session transcript.

---

### DEC-012: Project-structure split (Claude Project, repository) deferred to end of planning

**Date:** 05-07-26
**Status:** Active

**Context:** During the dimension #5 conversation, the question arose whether the next iteration of CRMBuilder should move to a separate Claude Project (giving v2 design conversations independent memory scope) or a separate GitHub repository (clean separation of legacy from next-generation code). The concern motivating the question is that accumulated v1 memory and conversation history could shape v2 design in ways that don't serve the new system, and that the boundary between archived v1 and current v2 may become hard to maintain over time.

**Decision:** Defer both decisions (Claude Project split, repository split) to the end of planning — after dimensions #6, #7, and #8 are resolved. Stay in the current Claude Project and the existing crmbuilder repository for the remaining planning conversations.

**Rationale:** Memory contamination risk is highest during design conversations, where v1 patterns can subtly leak into v2 schema decisions, not during planning conversations, which are cross-cutting and benefit from full v1 context. The remaining planning dimensions are also too early to make the rewrite-vs-modify call that drives the repository decision. Deferral preserves optionality without immediate cost.

**Alternatives considered:**
- Split now (new Claude Project, new repository or same). Rejected — premature; would force the rewrite-vs-modify framing decision before the planning phase is complete.
- Don't split at all. Rejected as a final answer, but accepted as the working state for the remainder of planning.

**Consequences:** At end of planning (when dimensions #6 through #8 are resolved), the Claude Project split decision and the repository decision both come due for resolution. The rewrite-vs-modify question — whether v2 modifies the existing application in place or rewrites it from scratch — becomes the prior question that shapes the repository answer. The current Claude Project and the existing crmbuilder repository continue to host all v2 work in the interim.

---

### DEC-013: Session-to-conversation mapping — one conversation, one session record, append-only

**Date:** 05-07-26
**Status:** Active

**Context:** The session log needs a clear rule for how Claude.ai conversations map to session records. Some topics fit in one conversation; others — schema design, CBM domain migration — almost certainly span multiple. Without a clear rule, the session log becomes ambiguous: is one log entry per topic (mutated across conversations) or one per conversation (multiple per topic)?

**Decision:** One Claude.ai conversation equals one session, which produces exactly one session record. A topic that spans multiple conversations produces a sequence of related session records, each capturing what its conversation accomplished. Session records are append-only — once written, they are not edited.

**Rationale:** Append-only records are stable, auditable, and chronological. Multi-conversation topics are reconstructed by reading the sequence of session records that touch the topic. The references table, when implemented as part of the storage layer, will eventually make this reconstruction a single query; until then, it is a manual scroll through the chronological sessions log. Doug's existing working preference — one major task per session, new conversations for each major task — aligns naturally with this rule.

**Alternatives considered:**
- One open session record per topic, mutated across conversations. Rejected — breaks the append-only property; conflates "session" (a discrete working block) with "topic" (a strand of work that may span many sessions).

**Consequences:** The session log naturally becomes a chronological project record. The "in-flight at session end" field of each session record is the load-bearing handoff mechanism for multi-conversation topics. The references table (when implemented) will provide a single query to retrieve all session records relevant to a given topic.

---

### DEC-014: Every v2 conversation produces a session record

**Date:** 05-07-26
**Status:** Active

**Context:** When a Claude.ai conversation engages v2 work, does it always produce a session record, or only when there is substantive output? The trade-off is between complete audit trail (always) and overhead minimization (only when needed).

**Decision:** Every conversation that engages v2 work produces a session record, even short or exploratory ones. The record can be brief when there is nothing substantive to capture ("explored topic X, no decisions reached, no commits beyond this entry"), but the record exists.

**Rationale:** The session log is itself one of the things that defines what the next iteration of CRMBuilder is — the project's own dogfooding of the database-as-source-of-truth principle. By that logic, an exploratory conversation that produces no record is, in v2 terms, a conversation that did not happen. Complete audit trail also helps reconstruct prior reasoning when topics recur.

**Alternatives considered:**
- Threshold-based (record only if a decision is made or an artifact lands). Rejected — discretion creates inconsistency; gaps in the log become ambiguous (no work, or unrecorded work?).
- Record only when there is a commit anyway. Rejected — same discretion problem in different framing.

**Consequences:** Some commits exist solely to land a session record when a conversation produced no other artifact. That is accepted overhead.

---

### DEC-015: Cadence is ad-hoc, no fixed schedule

**Date:** 05-07-26
**Status:** Active

**Context:** Planning dimension #5 includes a cadence sub-question — weekly, ad-hoc, or time-blocked against ongoing CBM work. The right answer depends on workload structure and the presence or absence of forcing functions.

**Decision:** Cadence is ad-hoc. Sessions happen when the work is ready. No fixed schedule, no time-box per session.

**Rationale:** This is a single-developer project with no external deadlines and no parallel commitments competing for time. CBM is downstream of v2 (per DEC-009), not parallel to it, so there is nothing to time-block against. A fixed cadence would create artificial pressure without serving any operational need. Ad-hoc matches Doug's existing working style.

**Alternatives considered:**
- Weekly. Rejected — no operational need for the rhythm; would create artificial pressure or dead sessions.
- Time-blocked against CBM. Rejected — CBM is the downstream test case, not a parallel commitment.

**Consequences:** Long gaps between sessions are expected and acceptable. The session record's "in-flight at session end" field becomes load-bearing for clean resumption. There is no built-in checkpoint mechanism — status reviews are themselves ad-hoc.

---

### DEC-016: Definition of done and gating model — Doug review at phase boundaries

**Date:** 05-07-26
**Status:** Active

**Context:** Each phase of the project (schema design, storage layer build, domain migrations, test infrastructure) needs a definition of "done" that determines when work moves to the next phase, and gates that determine whether to proceed forward, iterate within the current step, or stop and reassess. The question is whether to define done formally per phase or to trust judgment.

**Decision:** For any phase: done means the phase's nominal output exists in the repository, and Doug has reviewed it and judged it sufficient to move on. No formal per-phase checklist. Gates between phases are Doug's judgment, informed by whether the output works. If yes, proceed. If not, iterate within the current phase. If the phase cannot be made to work, stop and reassess.

**Rationale:** For a single-developer project where the architectural foundations are already settled, formal definition-of-done machinery adds overhead without proportional value. Judgment-based review is honest and matches the project's operational reality. The CBM-as-test-case principle (per DEC-009) provides empirical pressure on each phase's output independent of any formal checklist — schema designs are tested by attempting to absorb CBM content; storage layers are tested by serving real reads and writes; renderers are tested by producing review-quality artifacts.

**Alternatives considered:**
- Formal per-phase definition-of-done checklists. Rejected — over-scoping for single-developer ad-hoc work; produces ceremony without insight.

**Consequences:** Phase boundaries are softer than they would be under a formal model. Iteration within a phase is normal and expected. The status document tracks the active phase but does not enforce gates beyond Doug's judgment.
```

### Task 3 — Update `status.md`

Four `str_replace` operations on `PRDs/product/crmbuilder-v2/status.md`.

**Operation 3A — Update `Last Updated`.**

`old_str`:

```
# CRMBuilder v2 — Status

**Last Updated:** 05-06-26 19:28
**Status:** Active
```

`new_str`:

```
# CRMBuilder v2 — Status

**Last Updated:** 05-07-26 HH:MM
**Status:** Active
```

**Operation 3B — Update the Current Phase sub-step description.**

`old_str`:

```
**Sub-step:** Initial planning conversation complete and bootstrap committed. Planning dimensions 1, 2.1, 2.3, 2.4, 3, and 4 resolved (some explicitly, some by virtue of the database architecture). Dimensions 5–8 remain. Step 0 (schema design) has not yet started.
```

`new_str`:

```
**Sub-step:** Planning dimensions 1 through 5 resolved. Dimensions 6, 7, and 8 remain. Step 0 (schema design) has not yet started.
```

**Operation 3C — Update the v1/v2/Transition inventory and the Active Work / Pending — Immediate sections.**

`old_str`:

```
### What's in v2

- `charter.md` v0.1 — scope, name, architectural foundations, current state, open planning items
- `decisions.md` v0.1 — DEC-001 through DEC-011, architectural decisions from initial planning
- `sessions.md` v0.1 — SES-001, the initial planning conversation record
- `status.md` v0.1 — this document
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — the prompt that produced this initial state
```

`new_str`:

```
### What's in v2

- `charter.md` v0.2 — scope, name, architectural foundations, current state, open planning items (Open Planning Items trimmed at v0.2 to reflect dimension #5 resolution)
- `decisions.md` — DEC-001 through DEC-016, architectural and operational decisions
- `sessions.md` — SES-001 (initial planning) and SES-002 (planning dimension #5)
- `status.md` — this document
- `prompts/CLAUDE-CODE-PROMPT-v2-A-bootstrap.md` — bootstrap prompt
- `prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md` — planning dimension #5 prompt
```

**Operation 3D — Update Active Work, Pending — Planning, and reduce Pending — Immediate to remain accurate.**

`old_str`:

```
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
```

`new_str`:

```
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
```

### Task 4 — Update `charter.md`

Four `str_replace` operations on `PRDs/product/crmbuilder-v2/charter.md`. The dimension #5 resolution does not change scope language; charter updates are limited to bumping the version to v0.2, adding a change log row, and trimming the Current State and Open Planning Items sections to reflect dimension #5's resolution.

**Operation 4A — Bump version and update `Last Updated`.**

`old_str`:

```
# CRMBuilder v2 Charter

**Version:** 0.1 (draft)
**Last Updated:** 05-06-26 19:28
**Status:** In planning — pre-build
```

`new_str`:

```
# CRMBuilder v2 Charter

**Version:** 0.2 (draft)
**Last Updated:** 05-07-26 HH:MM
**Status:** In planning — pre-build
```

**Operation 4B — Add change log row.**

`old_str`:

```
| 0.1 | 05-06-26 | Initial draft from planning conversation. Captures scope, name, architectural foundations, session orientation protocol, and remaining planning dimensions. |
```

`new_str`:

```
| 0.1 | 05-06-26 | Initial draft from planning conversation. Captures scope, name, architectural foundations, session orientation protocol, and remaining planning dimensions. |
| 0.2 | 05-07-26 | Resolved planning dimension #5 (pacing, cadence, milestones); operational resolution recorded in decisions and sessions logs. Trimmed Current State and Open Planning Items sections to reflect resolution. No scope change. |
```

**Operation 4C — Update the Current State section.**

`old_str`:

```
Planning dimensions remaining:

- #5 (pacing, cadence, milestones)
- #6 (division of labor)
- #7 (risk register)
- #8 (exit criteria)

**Active work:** Drafting this charter and the companion decisions document as the first durable artifacts of the project. Architectural decisions are being numbered retroactively as DEC-001 through DEC-N.

**Not yet started:** Step 0 (schema design), implementation of any v2 code, creation of the v2 home directory in the repo, CLAUDE.md update, MCP server build.
```

`new_str`:

```
Planning dimensions remaining:

- #6 (division of labor)
- #7 (risk register)
- #8 (exit criteria)

Project-structure split decision (Claude Project, repository) — deferred to end of planning per DEC-012.

**Active work:** None currently active. Next conversation takes up planning dimension #6.

**Not yet started:** Step 0 (schema design), implementation of any v2 code, MCP server build.
```

**Operation 4D — Trim the Open Planning Items section to remove dimension #5.**

`old_str`:

```
## Open Planning Items

The following planning dimensions remain to be resolved before Step 0 (schema design) begins:

**#5 — Pacing, cadence, and milestones.** What does a working session on this project look like? Cadence weekly, ad-hoc, or time-blocked against ongoing CBM work? What does "done" mean for each phase and sub-step? What are the gates that determine whether to proceed forward, iterate within the current step, or stop and reassess?

**#6 — Division of labor.** Where are the boundaries between Claude.ai work (design, drafting, schema iteration), Claude Code work (implementation, file edits, repo changes), and Doug-only work (methodology decisions, stakeholder coordination, final approval, validation review)? What's the handoff protocol between modes?
```

`new_str`:

```
## Open Planning Items

The following planning dimensions remain to be resolved before Step 0 (schema design) begins:

**#6 — Division of labor.** Where are the boundaries between Claude.ai work (design, drafting, schema iteration), Claude Code work (implementation, file edits, repo changes), and Doug-only work (methodology decisions, stakeholder coordination, final approval, validation review)? What's the handoff protocol between modes?
```

### Task 5 — Save this prompt to `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md`

Use `create_file` to write the complete contents of this prompt to `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md`. The contents to write are everything from the H1 line `# CLAUDE-CODE-PROMPT-v2-B-pacing` through the end of this document, verbatim. Do not modify, abbreviate, or commentate the contents — they should match this prompt exactly so future sessions have an authoritative record of what produced this commit.

### Task 6 — Commit

```bash
git add PRDs/product/crmbuilder-v2/
git commit -m "v2: planning dim #5 — pacing, cadence, milestones (SES-002, DEC-012 through DEC-016)"
```

Do **not** push automatically. Doug will review and push manually after inspection.

## Validation

After completion, confirm:

- `PRDs/product/crmbuilder-v2/sessions.md` contains an `## SES-002:` heading and the new session record is the last content in the file.
- `PRDs/product/crmbuilder-v2/decisions.md` contains five new index entries (DEC-012 through DEC-016) and five new full decision records (DEC-012 through DEC-016) appended after DEC-011, plus a new change log row for v0.2.
- `PRDs/product/crmbuilder-v2/status.md` no longer lists dimension #5 in Pending — Planning, and the Sub-step text reflects dimensions 1 through 5 resolved.
- `PRDs/product/crmbuilder-v2/charter.md` shows `**Version:** 0.2 (draft)`, has a v0.2 change log row, has dimension #5 removed from the Current State remaining list and from the Open Planning Items section, and includes the project-structure deferral note in Current State.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-B-pacing.md` exists and matches this prompt.
- All four governance artifacts and this prompt have `Last Updated` (or per-document equivalent) values of `05-07-26 HH:MM` where `HH:MM` is the actual commit time.
- The commit message starts with `v2:` and is the most recent commit.
- `git status` is clean (no untracked files or unstaged changes).
- `git log -1 --stat` shows exactly the expected files modified (sessions.md, decisions.md, status.md, charter.md) plus one new file (the prompt copy).

## Reporting

Report back to Doug with:

- The full text of the commit message.
- Output of `git log -1 --stat`.
- Any anomalies encountered, including any `str_replace` anchor mismatches that forced a stop.

## Notes

- This is the second commit of the v2 series. All future v2 commits use the `v2:` subject prefix.
- The `HH:MM` placeholder in each `Last Updated` field must be replaced with the actual commit time at the moment of execution.
- The five new decision records (DEC-012 through DEC-016) are operational decisions about how the project runs, not architectural decisions about what the project is. They are recorded in the same decisions log because the log is the project's single decision record, not split between architectural and operational.
- The communication rule about never referencing identifiers without explanation is captured in Claude's stored memory rather than in the v2 decisions log because it is a working-style rule that applies across all of Doug's work, not specifically a v2 architectural or operational decision.
