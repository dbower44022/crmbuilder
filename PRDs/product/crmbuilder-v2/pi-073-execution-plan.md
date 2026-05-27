# PI-073 — Redesign Session and Conversation entities — Execution Plan

**Last Updated:** 05-27-26
**Author:** Claude Code (draft for review)
**Planning item:** PI-073 (Open) — Redesign Session and Conversation entities as a medium-agnostic communication container with topical sub-units
**Status of this document:** v0.1 DISCUSSION DRAFT — proposed plan; awaiting Doug's review before any conversation is opened against it.
**Workstream:** to be assigned (recommended: a new workstream rather than slotting under WS-011 V2 storage API refinements; the redesign touches schema, API, MCP, UI, data, and docs and is large enough to merit its own).

---

## 1. Why this plan exists

PI-073 is an architectural redesign of the two most-used V2 governance entities (`session` and `conversation`). The PI body identifies four open design questions that must be resolved before any schema, API, MCP, UI, or migration work can start. The PI is not slice-shaped — it is a multi-conversation workstream. This document proposes the conversation sequence, the design questions each conversation owns, and the deliverable per conversation, so a future "open against PI-073" can route into the right starting conversation rather than re-deriving the structure each time.

The plan deliberately mirrors the proven pattern used for the v0.7 governance entity workstream (master plan → per-entity schema-design conversations → slice build prompts → close-out) and the more recent code-change-lifecycle / commit-entity work (planning conversation → schema spec → slice A migration + ORM → slice B access + REST → slice C UI).

---

## 2. Cross-PI sequencing — read this first

PI-085, PI-086, PI-087, PI-088 are all Open and (per SES-093) blocked on each other in that order. PI-087 in particular is the Session/Conversation governance **Process PRD** — i.e., a Process PRD whose subject matter is the lifecycle of the very entities PI-073 redesigns. The plan must take a position on which goes first.

**Recommended sequencing.** PI-073 first. Rationale:

- PI-087 must describe entity names, lifecycle states, and reference edges. If PI-087 is authored against the current model and PI-073 then lands, every step, every entity reference, and most of the acceptance criteria in the Process PRD need to be re-spelled. The churn is roughly all of PI-087.
- PI-085 (Domain Overview) and PI-086 (Personas) can both proceed against the redesigned model without rewrite — they reference Session and Conversation by name only.
- PI-073 itself is unblocked by anything in PI-085–PI-088.
- The four open design questions in PI-073 (especially Q2 — handling planned-but-not-started conversations at session close) materially shape how PI-087's process steps read; settling them first makes PI-087 authorable in one pass.

**Alternative.** Run PI-073 and PI-085–PI-088 fully in parallel only if PI-087 explicitly defers all naming/structure to a later revision. Not recommended — splits the documentation across two states and undermines the dogfood intent of DEC-295.

**Disposition needed.** Doug to confirm "PI-073 first" before any conversation against PI-073 opens. If confirmed, record as a DEC at the start of Conversation 1 (below).

---

## 3. Conversation sequence

Six conversations. Each has its own kickoff prompt (drafted as a side effect of the prior conversation's close-out, per the established pattern). Identifier slots are not pre-claimed — each conversation captures heads at open per DEC-300.

### Conversation 1 — Architectural design and decision

**Goal.** Resolve the four open design questions in PI-073's body, produce the architectural decision (single DEC), and produce the v0.1 schema spec for both redesigned entities.

**Inputs.**
- PI-073 body (the four open questions)
- DEC-119 (the original conversation-entity decision being amended)
- DEC-013 (sessions are append-only — needs explicit reconciliation)
- Current `session` and `conversation` schemas (`crmbuilder-v2/src/crmbuilder_v2/access/models.py` lines 175 and 1008–1075)
- v0.7 governance-entity precedents — the seven cross-spec precedents established by the workstream master plan, recorded in DEC-118 et al.

**Open design questions (PI-073 §OPEN DESIGN QUESTIONS, recapped here so the conversation does not have to re-derive them).**

1. **Session-level sequencing.** Should `session` carry predecessor/successor links (`session_follows_from`), or is session-level sequencing implicit through the conversation `follows_from` chains within them?
   - Recommendation in the conversation: yes for email threads and Zoom recurring meetings, where session-level sequence is a property of the medium. Make it optional, not required. Alternative: derive on demand from conversation chains.

2. **Planned-but-not-started conversations at session close.** Two candidates:
   - (a) Conversation record exists in `not_started` state; gets `rescheduled`, `deferred`, or `cancelled` at session close.
   - (b) The conversation never gets a record; the unstarted topic stays as a Planning Item that becomes a conversation when a future session picks it up.
   - Recommendation: (a) — symmetric with `planned → in_flight → complete` and avoids the type-shift between PI and conversation. Alternative: (b) if Doug prefers the PI as the canonical unstarted-work shape.

3. **Medium-specific metadata schema.** Universal fields (medium, started_at, completed_at, participants); medium-specific fields (subject + thread_id for email; URL for chat; dial-in for phone; location for in-person). Two candidate shapes:
   - Single table with all medium-specific columns nullable.
   - Single table with a `medium_metadata` JSON column.
   - Recommendation: JSON column. EspoCRM-style universal columns become a maintenance burden as new mediums appear; JSON is queryable in SQLite via `json_extract`; v2's envelope already round-trips JSON cleanly.

4. **Migration of existing records.** Current V2 has 94 sessions and 64 conversations (as of 2026-05-27).
   - Recommendation: current `conversation` records become `session` records in the new model (1:1 by identifier — `CONV-NNN` does not need to remap because it's a string identifier; only the table moves). Current `session` records become "session completion data" attached to the new session. Each migrated record becomes a single-conversation session by default (the old `topics_covered` text gets attached to one auto-created Conversation record per migrated Session). Operators who later want to topical-split a historical session can hand-split via the desktop UI.

**Deliverables.**
- One DEC settling all four questions and naming the redesigned model (single DEC, not four — this is one architectural decision).
- `governance-schema-specs/session-v2.md` — full v1.0 spec for the redesigned `session` entity (fields, validations, defaults, REST endpoints, UI, acceptance criteria) per the v0.7 governance-entity spec format.
- `governance-schema-specs/conversation-v2.md` — same for the redesigned `conversation`.
- Updated `vocab.py` provisional plan — which new relationship kinds need to land (`session_follows_from` if Q1 lands yes, `conversation_follows_from`, `conversation_relates_to`), which existing kinds need to retire (`close_out_payload_produced_by_conversation` may need to migrate).
- Close-out payload with the DEC, the two specs as `commits`, and `addresses_planning_items: [PI-073]` (not `resolves`; PI-073 resolves only at Conversation 6).

**Estimated effort.** One Claude.ai conversation, 2–4 hours.

---

### Conversation 2 — Build planning (slice the work)

**Goal.** Take the two specs from Conversation 1 and produce the slice plan — how many slices, what each slice ships, what order, and a build-prompt skeleton per slice. Mirror the `governance-schema-build-planning-kickoff.md` → `governance-schema-workstream-plan.md` pattern.

**Likely slice breakdown (proposed here as a strawman for Conversation 2 to confirm or revise).**

- **Slice A — Alembic migration.** Rename `conversations` table → `sessions_v2` (temp); add new columns (`medium`, `medium_metadata` JSON, `session_follows_from` if Q1=yes, etc.); create new `conversations_v2` table (the new topical sub-unit); data-preserving migration of existing rows; CHECK-constraint extensions on `refs` for new relationship kinds; vocab.py updates. Two-table rename + add-table pattern needs careful sequencing — `0013_redesign_session_conversation.py` or similar.
- **Slice B — Access layer.** New `session.py` and `conversation.py` ORM models replacing the existing pair; update `_helpers.py` if the new conversation lifecycle states need helper coverage; CRUD methods; access-layer validations (member-of-session enforcement, lifecycle transition guards).
- **Slice C — REST endpoints.** Standard nine-endpoint set per V2 envelope convention for both entities. Plus derived endpoints — `GET /sessions/{id}/conversations`, `GET /conversations/{id}/follows-from`, etc.
- **Slice D — MCP tool surface.** `get_session`, `get_conversation`, `list_sessions`, `list_conversations`, and the lifecycle helpers (`open_session`, `close_session`, `open_conversation`, `complete_conversation`) — replace the corresponding tools at `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools/`.
- **Slice E — Desktop UI.** Session panel (new), Conversation sub-panel (nested within session view), and update of the existing sidebar entries. Likely the largest slice — uses the four v0.7 governance panels as the visual template.
- **Slice F — Data migration of existing records.** Standalone slice (not folded into Slice A) so it can be run, audited, and rolled back independently. Migrates the 94 sessions + 64 conversations into the new shape per the rule from Conversation 1 Q4. Produces a `migration-report.md` enumerating every old row → new row mapping.

**Deliverables.**
- `pi-073-workstream-plan.md` (recommended filename) — the master plan with the slice breakdown, ordering, dependencies, success criteria per slice.
- Six (or however many slices land) draft kickoff-prompt outlines — one per slice — committed as stubs.
- Close-out payload; still `addresses_planning_items: [PI-073]`.

**Estimated effort.** One Claude.ai conversation, 2–3 hours.

---

### Conversations 3–N — Slice builds

One Claude Code conversation per slice. Each follows the established pattern:

1. Open against the slice's kickoff prompt (per "v2 session lifecycle — opening a session" in CLAUDE.md).
2. Implement against the spec (which is fixed; no design questions to re-litigate).
3. Author and apply the close-out payload locally.
4. Doug pushes the resulting commit + db-export changes.

Slice A and Slice F are the highest-risk slices. Slice A because it edits the schema two entities depend on for every governance operation; Slice F because it touches every existing row. Both warrant a verify pass against the local db before push, and a known-good restore point (`v2.db` is gitignored but the db-export JSON snapshots are the durable rollback target).

Per-slice `addresses_planning_items: [PI-073]`. None of these resolve PI-073.

---

### Conversation N+1 — Migration audit and documentation propagation

**Goal.** After all slices land, audit that the redesign is complete end-to-end and propagate it through documentation.

**Scope.**
- Audit pass: for each of the 94 existing sessions + 64 existing conversations, verify the migrated row reflects the original content faithfully. Spot-check 5–10 migrated records by hand.
- Update CLAUDE.md:
  - The "v2 session lifecycle — opening a session" and "v2 session lifecycle — closing a session" sections need rewording for the new model.
  - The "v0.7 governance entity release" paragraph needs a note that `session` and `conversation` were redesigned post-v0.7.
  - The DEC-013 callout (sessions are append-only) needs reconciliation with the new lifecycle states on `conversation`.
- Update PRDs that reference the old model — search `PRDs/product/crmbuilder-v2/` and `specifications/` for "conversation" used in the old `CONV-NNN-is-a-chat` sense and reword.
- Update working conventions in `governance-recording-rules.md` (v0.1 DISCUSSION DRAFT per recent commit `5a2b6a4`).
- Update the kickoff for PI-087 (Session/Conversation Process PRD) to reflect the redesigned model — this is the load-bearing cross-PI handoff.

**Deliverables.**
- Audit report committed as `pi-073-migration-audit.md`.
- CLAUDE.md and PRD updates committed.
- Close-out payload that **resolves** PI-073 (the only conversation in the sequence whose close-out carries `resolves_planning_items: [PI-073]`).

**Estimated effort.** One Claude Code conversation, 2–3 hours.

---

## 4. Coordination with PI-085–PI-088 once PI-073 lands

Once PI-073 is resolved:
- PI-085 (Domain Overview) and PI-086 (Personas) proceed unchanged.
- PI-087 (Session/Conversation Process PRD) inherits the redesigned model — its kickoff was updated in Conversation N+1.
- PI-088 (Meta Process PRD Definition Process) is unaffected.

If Doug chooses the alternative sequencing (run PI-085–PI-088 first), PI-087's kickoff explicitly states it is being authored against the pre-PI-073 model and will be revised after PI-073 lands. That revision becomes part of PI-073's documentation propagation in Conversation N+1.

---

## 5. Risks and open questions for this plan itself

1. **Append-only collision.** DEC-013 said sessions are append-only — the redesigned `conversation` (sub-unit) has lifecycle states. Conversation 1 must explicitly state whether the new `conversation` entity is append-only or stateful. If stateful, DEC-013's "append-only governance rule" is narrowed to apply only to `session` (now the medium-agnostic container) and the sub-unit `conversation` becomes the stateful work-unit record. This is a clean reframe but must be spelled out.

2. **Reference vocab churn.** The redesign touches at least three reference kinds (`close_out_payload_produced_by_conversation`, `commit_conversation_id` soft FK, `conversation_*_at` timestamps). Slice A's migration must address the data implications, not only the schema implications.

3. **MCP tool name churn.** Renaming `get_conversation` to keep its name but mean a different thing risks confusing any external client (Claude Desktop, the chat-UI-on-API per DEC-245). Two options: (a) keep names, accept semantic shift; (b) rename and stub old names with deprecation. Conversation 1 settles.

4. **CONV-NNN identifier reuse.** Existing `CONV-001..CONV-064` are conversation records in the old sense. Under the new model they become `session` records. Two options: (a) keep the identifier as-is (now means a session); (b) issue new `SES-NNN` identifiers and retire the old ones. Operationally (a) is simpler; semantically (b) is cleaner. Conversation 1 settles.

5. **Backfill timing for PI-024, PI-025, PI-026.** Those PIs (per v0.7 close) defer backfill of prior workstreams, conversations, and historical applies. If they land before PI-073, the backfill happens in the old shape and then needs to migrate. If after, no migration needed but the backfill is delayed further. Recommendation: defer PI-024/025/026 explicitly until after PI-073's Conversation N+1. Surface this as a DEC at Conversation 1.

---

## 6. Summary of recommended path

| Step | What | Where | Who |
|---|---|---|---|
| 0 | Confirm "PI-073 first" sequencing vs PI-085–PI-088 | (this document) | Doug |
| 1 | Conversation 1 — architectural design + DEC + two schema specs | Claude.ai sandbox | Sandbox + Doug |
| 2 | Conversation 2 — slice plan + per-slice kickoff stubs | Claude.ai sandbox | Sandbox + Doug |
| 3 | Slice A — Alembic migration + vocab + CHECK constraints | Claude Code local | Claude Code + Doug |
| 4 | Slice B — Access layer (ORM, CRUD, validations) | Claude Code local | Claude Code + Doug |
| 5 | Slice C — REST endpoints (envelope-preserving) | Claude Code local | Claude Code + Doug |
| 6 | Slice D — MCP tool surface | Claude Code local | Claude Code + Doug |
| 7 | Slice E — Desktop UI (Session panel + Conversation sub-panel) | Claude Code local | Claude Code + Doug |
| 8 | Slice F — Data migration of existing records | Claude Code local | Claude Code + Doug |
| 9 | Conversation N+1 — audit + documentation propagation + **resolves PI-073** | Claude Code local | Claude Code + Doug |

Total estimated conversations: 8 (1 design + 1 plan + 6 build/audit). Wall-clock: a week of part-time work or two days focused.

---

## 7. What this plan does NOT do

- It does not pre-claim DEC, PI, SES, CONV, or REF identifiers. Each conversation captures heads at open per DEC-300.
- It does not author the kickoff prompts for Conversation 1 or 2 — those are tiny enough (~half a page each) that they can be drafted at the point Doug authorizes the workstream open, rather than committed speculatively now.
- It does not author the DEC for "PI-073 first" sequencing — that's a Conversation 1 artifact, conditional on Doug confirming the recommendation in §2.
- It does not change anything in V2. Producing this plan is a pure documentation act; no records were created, no edges added, no rows changed.
