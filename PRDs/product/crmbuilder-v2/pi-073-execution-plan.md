# PI-073 — Redesign Session and Conversation entities — Execution Plan

**Last Updated:** 05-27-26 (v0.3 — branch + DB-isolation revision)
**Author:** Claude Code
**Planning item:** PI-073 (Open) — Redesign Session and Conversation entities as a medium-agnostic communication container with topical sub-units. **Top-priority work — the current session/conversation process is broken and is preventing the capture of valuable data (non-Claude.ai mediums; scheduled-then-updated sessions; topical separation within a longer session).**
**Branch:** `pi-073-redesign` (created off `main` from commit `99be558`). All build work lands on the branch; `main` stays working for ongoing governance recording (SES-096 and beyond) until the branch is ready to merge.
**DB isolation:** Branch tools target `crmbuilder-v2/data/branch-pi-073/CRMBUILDER.db` and `crmbuilder-v2/data/branch-pi-073/CBM.db` (gitignored copies of the live engagement DBs). The live `crmbuilder-v2/data/engagements/*.db` files are not touched by branch work until Phase F is staged at merge time. Set `CRMBUILDER_V2_DB_PATH=crmbuilder-v2/data/branch-pi-073/CRMBUILDER.db` when running alembic / pytest / the API server on the branch.
**Status of this document:** v0.3 — extends v0.2's bootstrap-aware shape with a branch quarantine. Same Phase A–G sequence; same one-final-close-out semantics; branch isolates the build's breakage from `main`.
**Workstream:** WS-011 (V2 storage API refinements).

> **v0.2 → v0.3 change summary.** v0.2 assumed work would land directly on `main`, leaving `main` in a broken state between Phase A and Phase G. v0.3 puts the entire build on a dedicated `pi-073-redesign` branch with isolated DB copies, so `main` continues to work for ongoing governance recording. The merge happens once after Phase G stabilizes the new world end-to-end. Discovered prerequisites during v0.3 planning: the data lives in per-engagement DBs (`engagements/CRMBUILDER.db` + `engagements/CBM.db`) at divergent alembic heads — CRMBUILDER at `0019_v0_5_entity_kind_and_variants`, CBM at `0010_v0_4_create_crm_candidates_table` — so the PI-073 migration must be authored to apply cleanly on top of CRMBUILDER (the primary target) and the CBM lag is recorded as a separate forward-port issue (CBM will be brought up to v0.7 + v0.8 schema first, then PI-073 applies as a normal subsequent migration).
>
> **Realistic clock-time expectation.** Phases A through G total roughly 8–15 hours of focused Claude Code work spread across many turns. The branch absorbs that work without disrupting `main`; Doug pushes the branch to GitHub only when stable. The PR is the merge point.

---

## 1. Why this plan exists

PI-073 is an architectural redesign of the two most-used V2 governance entities (`session` and `conversation`). The PI body identifies four open design questions that must be resolved before any schema, API, MCP, UI, or migration work can start. The PI is not slice-shaped — it is a multi-conversation workstream. This document proposes the conversation sequence, the design questions each conversation owns, and the deliverable per conversation, so a future "open against PI-073" can route into the right starting conversation rather than re-deriving the structure each time.

The plan deliberately mirrors the proven pattern used for the v0.7 governance entity workstream (master plan → per-entity schema-design conversations → slice build prompts → close-out) and the more recent code-change-lifecycle / commit-entity work (planning conversation → schema spec → slice A migration + ORM → slice B access + REST → slice C UI).

---

## 2. Cross-PI sequencing — settled

**PI-073 lands first.** Settled by Doug 2026-05-27 and recorded as part of DEC-314. The seven downstream PIs (PI-085, PI-086, PI-087, PI-088, PI-024, PI-025, PI-026) carry `blocked_by` reference edges to PI-073 (authored in SES-095's close-out) and unblock when PI-073 resolves at Phase G.

---

## 3. Phase sequence (v0.2)

Seven phases. **Conversation 1 (architectural design) landed as SES-095 / DEC-314 on 2026-05-27 — the design is settled.** Phases A–G are the build effort. Each is a git commit on `main`; **no close-out payload is applied between phases.** One end-of-effort close-out at Phase G captures all the commits in `commits[]`, records the audit session, and resolves PI-073.

### Why no per-phase close-outs (the bootstrap problem)

Phase A's Alembic migration renames the `conversations` table to `sessions` and creates a new `conversations` table. The instant that migration runs, `apply_close_out.py`, every REST router, the MCP server, the desktop UI, and the `db-export` emitters are all broken — they all read/write the old shape. There is no working application stack between phases A and G. So per-phase close-out apply is impossible.

The compensating discipline: every phase's git commit message attributes the work to the conversation in flight at the time, and Phase G's close-out lists all of those commit SHAs in its `commits[]` section so the governance audit trail is complete in a single transaction.

### Conversation 1 (already complete) — Architectural design and decision

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

**Actual outcome (2026-05-27).** Landed as SES-095 in commit `99be558` with DEC-314, `session-v2.md` v1.0, `conversation-v2.md` v1.0, and seven `blocked_by` reference edges parking PI-085–088 and PI-024–026 behind PI-073.

---

### (Skipped) Conversation 2 — Build planning

v0.1 of this plan called for a separate build-planning conversation to settle slice-by-slice questions. v0.2 removes it: the seven deferred questions from SES-095's close-out (commits-table FK; per-medium JSON strictness; indexed JSON paths; timezone handling; auto-flip planned→not_started; conversation_summary required on complete; dedicated workstream y/n) are settled inline by the phase-author as each phase lands. Settled-call summary lives in Phase G's close-out body.

---

### Phase A — Alembic migration

**Goal.** Take the V2 schema from the pre-PI-073 shape to the post-PI-073 shape in one Alembic revision. After this commit, the SQL schema is right; the Python code is still broken (Phase B fixes that).

**What lands.**
- New Alembic revision file under `crmbuilder-v2/alembic/versions/`. Likely `0014_redesign_session_conversation.py` (slot 0013 was the v0.7 governance entity migration; verify head).
- Schema changes:
  - Rename existing `conversations` → `sessions` (the legacy `sessions` table that held the after-the-fact records is dropped; its data is recovered into the new `conversations` table by Phase F).
  - Wait — actually the cleaner order: drop the legacy `sessions` (after backing up to a temp table), rename `conversations` → `sessions`, create a fresh `conversations` table.
  - Add medium-agnostic columns to `sessions`: `session_medium`, `session_medium_metadata` (JSON), `session_participants` (JSON), `session_scheduled_for`, `session_started_at`, `session_ended_at`. Plus lifecycle columns matching the spec.
  - New `conversations` table per `conversation-v2.md` §3.
  - Extend `refs.relationship_kind` CHECK constraint to admit the new kinds (`session_belongs_to_workstream`, `session_opens_against_work_ticket`, `session_follows_from`, `conversation_belongs_to_session`, `conversation_follows_from`, `conversation_relates_to`).
  - Soft-rename `commit_conversation_id` FK on `commits` → `commit_session_id` (settle the deferred Q from SES-095 inline: rename rather than convert-to-edge; preserves query performance; commits attribute to session-grain).
- vocab.py partial updates (just the constants the migration's CHECK constraint references — full vocab finalize in Phase B).
- Tests covering the migration's roundtrip on a copy of v2.db.

**Commit message convention.** `v2: PI-073 Phase A — Alembic migration redesigning session and conversation tables`.

---

### Phase B — Access layer rewrite

**Goal.** Make the Python code match the new schema. After this commit, the ORM works against the new tables; the REST API does not.

**What lands.**
- New `session.py` and `conversation.py` ORM models in `crmbuilder-v2/src/crmbuilder_v2/access/models.py` (replacing the old ones).
- Rewritten repositories: `sessions.py`, `conversations.py`. Existing CRUD + next-identifier + supersedes patterns preserved.
- `_governance.py`: add new edge-rule helpers (`reject_missing_session_belongs_to_workstream`, `reject_missing_conversation_belongs_to_session`, `enforce_complete_requires_conversation`).
- `vocab.py`: finalize REFERENCE_RELATIONSHIPS, ENTITY_TYPES, `_kinds_for_pair`.
- Tests: full coverage of access-layer create/update/delete, edge-rule enforcement, lifecycle transition rules.

**Commit message convention.** `v2: PI-073 Phase B — Access layer rewrite for redesigned session/conversation`.

---

### Phase C — REST endpoints + apply_close_out.py update

**Goal.** Make the API surface match the new shape. After this commit, the REST API works against the new tables AND `apply_close_out.py` is updated to use the new request shapes (load-bearing for Phase G's close-out apply).

**What lands.**
- Rewritten routers: `crmbuilder-v2/src/crmbuilder_v2/api/routers/sessions.py` and `conversations.py`.
- Updated Pydantic schemas in `schemas.py`.
- **`scripts/apply_close_out.py` update** — the apply script's `_SECTIONS` table refers to fields like `conversation_identifier`, `conversation_title` that move/rename under the new shape. Re-derive shapes and label-extractors. **This is critical for Phase G.**
- API tests covering envelope shape, identifier-collision behavior, lifecycle transitions, derived endpoints, JSON medium-metadata roundtrip.

**Commit message convention.** `v2: PI-073 Phase C — REST endpoints + apply_close_out update for new session/conversation`.

---

### Phase D — MCP tools update

**Goal.** Make the MCP tool surface match. After this commit, Claude Desktop / sandbox MCP clients can call the new API correctly.

**What lands.**
- Updated tool definitions in `crmbuilder-v2/src/crmbuilder_v2/mcp_server/tools/` for `get_session`, `list_sessions`, `get_conversation`, `list_conversations`, and any lifecycle helpers.
- Tool descriptions updated to reflect new semantics.

**Commit message convention.** `v2: PI-073 Phase D — MCP tool surface update`.

---

### Phase E — Desktop UI

**Goal.** Make the desktop application match. After this commit, the Sessions sidebar entry opens the new Session panel; the Conversation entries nest within Session views.

**What lands.**
- New Session panel under the Governance sidebar group (replacing the legacy Conversation panel; the v0.7 panel pattern from `workstream_panel.py` is the template).
- New Conversation sub-panel that nests within a Session view (the Session's `GET /sessions/{id}/conversations` derived endpoint feeds it).
- EntityCrudDialog usage rewritten to accept the medium enum and the medium_metadata JSON editor.
- Sidebar entry updates.

**Commit message convention.** `v2: PI-073 Phase E — Desktop UI for redesigned session/conversation`.

---

### Phase F — Data migration of existing records

**Goal.** Convert the 94 existing CONV-NNN rows and 64 existing SES-NNN rows into the new shape. After this commit, all historical governance data is queryable under the new schema.

**What lands.**
- Standalone migration script at `crmbuilder-v2/scripts/migrate_pi_073_data.py`. Idempotent. Produces a `pi-073-migration-report.md` enumerating every old → new row mapping.
- Migration rules per `session-v2.md` §6 and `conversation-v2.md` §6:
  - Old `conversations.CONV-NNN` rows become new `sessions` records keyed by `CONV-NNN` (identifier-prefix retained for historical readability).
  - Old `sessions.SES-NNN` rows become new `conversations` records keyed by `SES-NNN` (same accepted asymmetry).
  - Edges retarget: `decided_in → session` becomes `decided_in → conversation` (because the original session row that hosted the decision now lives as a conversation); `conversation_belongs_to_workstream` becomes `session_belongs_to_workstream`; `conversation_records_session` is replaced by inbound `conversation_belongs_to_session` edges.
  - `commit_conversation_id` FK already renamed to `commit_session_id` in Phase A; migrate values: each old `commit_conversation_id` → `commit_session_id` where the old conversation became the new session (1:1 mapping preserved).
- Migration runs in a single SQLAlchemy transaction with a SAVEPOINT per record-group; rolls back cleanly on validation failure.
- Spot-check: enumerate 5–10 random pre-migration records, capture their content, run the migration, verify post-migration content matches.

**Commit message convention.** `v2: PI-073 Phase F — Data migration of 94 conversations + 64 sessions to new shape`.

---

### Phase G — Final close-out, documentation propagation, PI-073 resolution

**Goal.** Close the loop. Author one close-out that records the entire workstream's commits, applies via the (now-working) `apply_close_out.py`, propagates documentation through CLAUDE.md and downstream PRDs, and resolves PI-073.

**What lands.**
- Documentation updates:
  - CLAUDE.md: "v2 session lifecycle — opening a session" + "closing a session" sections rewritten for the new model; "v0.7 governance entity release" paragraph notes the post-launch redesign; the DEC-013 callout is removed (DEC-013 is now Superseded by DEC-314).
  - `governance-recording-rules.md` updated.
  - `pi-073-execution-plan.md` itself marked Complete and pointed at the audit report.
  - `pi-073-migration-audit.md` written from Phase F's migration report + a final integrity sweep.
- Close-out payload at `close-out-payloads/ses_NNN.json` listing every Phase A–F commit in `commits[]` plus the Phase-G audit session itself.
- `addresses_planning_items: [PI-073]` is NOT used here; this close-out's `resolves_planning_items: [PI-073]` flips PI-073 to Resolved.
- The Phase-G close-out also addresses the seven blocked_by'd PIs — they unblock automatically when their target PI-073 resolves (the `blocked_by` edges stay in the DB as historical references; they no longer represent active blockage).
- Apply via `apply_close_out.py` (now updated to new shape per Phase C). The apply commits one final SHA capturing the regenerated `db-export` snapshots + `dep_NNN.log`.

**Commit message convention.** `v2: PI-073 close-out applied — Phase G audit + documentation propagation + PI-073 resolved`.

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

### Pre-work — backup, baseline, and branch isolation (DONE 2026-05-27)

1. ✅ Backed up `crmbuilder-v2/data/engagements/CRMBUILDER.db` and `CBM.db` to `~/v2-backups/*.pre-pi-073.20260527-100817`.
2. ✅ Created `pi-073-redesign` branch from `main` at commit `99be558`.
3. ✅ Made gitignored DB copies at `crmbuilder-v2/data/branch-pi-073/CRMBUILDER.db` and `CBM.db` — branch tools target these.
4. ✅ Confirmed API healthy and DEC-013 status=Superseded.
5. CBM forward-port: deferred to a sub-step before Phase A's Alembic chain can apply to CBM (CBM lags by 9 revisions). Tracked in §5 risk 6.

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

5. **Backfill timing for PI-024, PI-025, PI-026.** Those PIs (per v0.7 close) defer backfill of prior workstreams, conversations, and historical applies. If they land before PI-073, the backfill happens in the old shape and then needs to migrate. If after, no migration needed but the backfill is delayed further. Recommendation: defer PI-024/025/026 explicitly until after PI-073's Phase G. Already realized via the `blocked_by` reference edges authored in SES-095.

6. **CBM.db lags 9 alembic revisions.** Discovered 2026-05-27 during v0.3 plan revision: `engagements/CBM.db` is at `0010_v0_4_create_crm_candidates_table` while `engagements/CRMBUILDER.db` is at `0019_v0_5_entity_kind_and_variants`. The PI-073 migration is authored against the post-0019 schema. Before merging the `pi-073-redesign` branch to `main`, CBM.db must be forward-ported through revisions 0011–0019 (most of which add tables CBM doesn't currently use; should be no-op safe but verify). This is an additional step inserted between Phase F (data migration of CRMBUILDER's records) and Phase G (final close-out + merge).

7. **Active SES-096 on `main`.** A new session (SES-096 — "Governance recording rules v0.1 authoring") landed in CRMBUILDER.db after this branch was cut. Because the branch's DB copy was made at branch-cut time, the branch's DB is one record behind. When Phase F's data migration eventually runs against the *live* CRMBUILDER.db (at merge time), it picks up SES-096 + any newer records automatically; the migration script must be authored to handle whatever record count exists at run time, not the snapshot-time count.

---

## 6. Summary of v0.2 path

| Step | What | Status | Commit |
|---|---|---|---|
| 0 | Architectural design + DEC-314 + two schema specs (Conversation 1 / SES-095) | **Done** | `99be558` |
| 1 | Pre-work — backup v2.db, baseline test pass | pending | — |
| 2 | Phase A — Alembic migration | pending | — |
| 3 | Phase B — Access layer rewrite | pending | — |
| 4 | Phase C — REST endpoints + apply_close_out.py update | pending | — |
| 5 | Phase D — MCP tool surface | pending | — |
| 6 | Phase E — Desktop UI | pending | — |
| 7 | Phase F — Data migration of existing records | pending | — |
| 8 | Phase G — Final close-out + documentation + **resolves PI-073** | pending | — |

Wall-clock: one focused Claude Code session at Doug's terminal. Each phase commits separately so Doug has checkpoints to review. The repo's `main` branch will be in an inconsistent build state between phases A and G — no part of the V2 app should be expected to work until Phase G lands.

---

## 7. What this v0.2 plan does NOT do

- Does not pre-claim identifiers. Phase G captures heads at apply-time per DEC-300.
- Does not commit to "ship in one Claude Code session" — the work may span multiple Claude Code turns, with intermediate checkpoint commits. Doug can interrupt at any commit boundary.
- Does not change the architectural design — DEC-314 + `session-v2.md` + `conversation-v2.md` are settled inputs to the build.
- Does not specify the exact line-count or structure of any phase's code — those are settled by the phase-author as the work lands.
