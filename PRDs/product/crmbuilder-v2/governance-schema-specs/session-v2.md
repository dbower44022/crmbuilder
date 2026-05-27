# Governance Entity Schema Spec — `session` (v2 redesign)

**Last Updated:** 05-27-26
**Status:** Draft v1.0 — produced by PI-073 architectural-design conversation (SES-095)
**Position in workstream:** First of two specs in the PI-073 redesign workstream (`session-v2` then `conversation-v2`), authored together so each can reference the other as a settled referent.
**Predecessor:** original `conversation.md` spec (the entity being redesigned out of existence in its original shape; per DEC-314 the table itself is renamed/repurposed)
**Successor:** the build-planning conversation (Conversation 2 of the PI-073 sequence per `pi-073-execution-plan.md`) which slices these two specs into Alembic + access + API + MCP + UI + data-migration build prompts.
**Authority:** This spec inherits the v0.7 governance-entity cross-spec precedents established by `workstream.md` and `conversation.md` (references-edge over FK; per-status lifecycle timestamps; terminal-states-are-terminal — but see §3.4 for the narrowed posture this spec establishes for `session`).

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-27-26 | Doug Bower / Claude Code | Initial draft. Produced by the PI-073 architectural-design conversation (SES-095). Establishes `session` as the medium-agnostic communication container — one Claude.ai chat / email / phone call / Zoom meeting / in-person meeting / Slack thread = one session. This supersedes the original session entity (after-the-fact append-only record per DEC-013) and the original conversation entity (per DEC-119, lifecycle wrapper). The new `session` carries the lifecycle that the original conversation carried, plus medium-specific metadata. Resolves PI-073 Q1 (yes to optional `session_follows_from`, plus optional `session_thread_id`), Q3 (JSON column for medium-specific metadata + small universal column set), and Q4 (existing-record migration via 1:1 row mapping — see §6). Records the explicit supersession of DEC-013 per Doug's redirect of 2026-05-27. |

---

## Change Log

**Version 1.0 (05-27-26):** Initial creation. Defines `session` as the V2 governance entity type that represents one discrete unit of communication in any medium. Establishes a universal column set (`session_medium`, `session_started_at`, `session_ended_at`, `session_participants`) plus a JSON `session_medium_metadata` column for medium-specific fields, plus the lifecycle states `planned → in_flight → complete` with optional `cancelled` / `superseded` / `not_started` terminals, plus optional `session_follows_from` reference-edge for medium-driven session-level sequencing (email threads, Zoom recurring meetings). Carries the kickoff prompt linkage and workstream membership inbound from the old conversation entity. Sessions are now **schedulable** and **stateful** — DEC-013's append-only rule is superseded by DEC-314 in its entirety, and the session entity no longer carries the after-the-fact constraint. Companion spec `conversation-v2.md` defines the topical sub-unit that lives within a session.

---

## 1. Purpose and Position

This document specifies the redesigned `session` entity for V2's storage layer. It is the **first of two** specs produced by the PI-073 architectural-design conversation — designed before `conversation-v2.md` because every conversation belongs to a session, and designing in that order lets the conversation spec treat session as a settled referent (parallel to how `workstream.md` was authored before `conversation.md` in the v0.7 release).

The redesign is governed by `pi-073-execution-plan.md`. The two specs feed a third build-planning conversation (Conversation 2 in the plan), which integrates them into a slice sequence (Alembic → access → API → MCP → UI → data migration), each slice landing as its own Claude Code session.

`session`'s primary scope in this release is to host the **unit of communication** concept in a medium-agnostic way. The pre-redesign V2 entity called `conversation` (per DEC-119) had a Claude.ai-chat-specific lifecycle wrapper, and the pre-redesign V2 entity called `session` (per DEC-013) was an append-only after-the-fact record of one Claude.ai chat. Both were structurally a single concept split across two tables for historical reasons (DEC-119 amended DEC-013 rather than superseding it; PI-073 now removes the split entirely). The new `session` has the lifecycle that the old `conversation` carried, plus medium-specific metadata that lets it represent more than just Claude.ai chats.

This spec **inherits three cross-spec precedents** from the v0.7 governance-entity workstream:

- **References-edge over foreign-key for parent-child governance relationships.** Every session→other-entity relationship lives in `refs`, never as a foreign-key column.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles.** Session carries one timestamp column per non-starter status, server-set on transition.
- **The supersession-requires-edge rule.** A session in `superseded` status must have an outgoing `supersedes` reference edge to its successor.

This spec **establishes one new cross-spec precedent** that the `conversation-v2.md` spec inherits:

- **Sessions are no longer append-only.** DEC-013's "session records are append-only — once written, they are not edited" rule is **superseded in its entirety** by DEC-314. The new `session` admits updates throughout its non-terminal lifecycle (a planned-for-Friday session is scheduled with metadata at create time, then updated with actual start/end times and participant list when the meeting happens). The terminal-state-immutability principle still holds at the field-content level: once a session reaches `complete`, `cancelled`, `not_started`, or `superseded`, its non-timestamp fields are no longer user-editable, except for administrative-correction PATCH parallel to the commit entity's §3.4.3 posture. This narrowing applies to `session` only; `conversation-v2.md` retains the new lifecycle-state machine without inheriting the original append-only rule (which never applied to conversations under DEC-119 anyway).

---

## 2. Summary

A `session` record in V2 represents one discrete unit of communication in any medium. Real examples under the new model: SES-001 was a Claude.ai chat that produced the V2 framing decision (medium=chat); SES-094 was a Claude Code working session that produced DEC-313 (medium=chat); a hypothetical SES-N+1 might be an email to the implementation partner (medium=email, with subject, thread_id, and message_id in `session_medium_metadata`); SES-N+2 might be a weekly Zoom (medium=zoom, with meeting_id and recording_url). Each is structurally a unit of communication with a defined medium, participants, start, and end — and one or more topical conversations within.

The schema in this release is the thinnest shape that captures the unit-of-communication concept faithfully: a human-readable title, a one-paragraph description, a small set of universal columns (medium, started_at, ended_at, participants), a JSON column for medium-specific extras, a five-status lifecycle (`planned` → `in_flight` → one of `complete` / `cancelled` / `not_started` / `superseded`) with timestamps for each non-starter transition, mandatory membership in exactly one workstream via a references-edge to that workstream, and four kinds of additional references-edge linkage (kickoff prompt as work_ticket; predecessor session for medium-driven sequencing; supersession; generic cross-references). The schema deliberately omits estimated duration, recording-link enums, attendee-role taxonomies, and transcript storage — each grows additively if real-use signal supports it.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `session` |
| Display name (singular) | Session |
| Display name (plural) | Sessions |
| Identifier prefix | `SES` |
| Identifier format | `SES-NNN`, zero-padded to 3 digits (e.g., `SES-001`, `SES-095`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /sessions/next-identifier` |

**Identifier-prefix posture.** `SES` is the existing prefix for the pre-redesign session entity; it is retained under the new model. Per PI-073 §Q4 resolution, existing `SES-NNN` identifiers stay (the row becomes one topical conversation within its newly-paired session per the migration in §6) and existing `CONV-NNN` identifiers stay (the row becomes a session under the new model). The semantic shift is documented loudly in CLAUDE.md and `pi-073-migration-audit.md` (produced by Conversation N+1 of the plan).

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `session_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_identifier` | TEXT | yes | server-assigned | `^SES-\d{3}$`, unique | The session identifier. Server-assigned on POST omission; helper endpoint `GET /sessions/next-identifier` returns the next available value. |
| `session_title` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Human-readable session title. Examples: "Workstream entity schema design (Claude.ai sandbox)", "Weekly status sync — 05-26-26 (Zoom)", "Email to Frank re: deployment scope (email thread re-open)". |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing the session's scope and intent — what communication is happening, who is involved, what end-state defines its close. Plain text in this release. |
| `session_notes` | TEXT | no | — | — | Internal scratchpad for pre-session prep, mid-session context, or post-session observations that don't fit the per-conversation summaries. Not part of the session's user-facing record. Plain text. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_status` | TEXT | yes | `planned` | enum: `planned` \| `in_flight` \| `complete` \| `cancelled` \| `not_started` \| `superseded`; valid transitions per §3.4 | Lifecycle status. See §3.4 for the full state machine. |
| `session_medium` | TEXT | yes | — | enum: `chat` \| `email` \| `phone` \| `zoom` \| `in_person` \| `slack` \| `other` | The medium in which the session occurs. Drives the shape of `session_medium_metadata` and the rendering of the session view in the desktop UI. Required at create time so a scheduled-for-the-future session declares its medium up front. |

**Medium enum posture.** Six concrete mediums plus `other`. The list is deliberately small in this release. Adding a new medium is a vocab change (enum extension) plus an Alembic migration on the CHECK constraint; the JSON metadata column avoids any per-medium schema churn beyond the enum entry. Build-planning may add `letter` (postal mail) or `videoconference_non_zoom` if a concrete use surfaces; deferred to signal.

#### 3.2.4 Universal communication fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_scheduled_for` | DATETIME | no | null | ISO 8601 UTC | When the session is planned to start. Optional — set when the session is `planned`; nullable for ad-hoc sessions opened directly in `in_flight`. |
| `session_started_at` | DATETIME | no | null | ISO 8601 UTC; not user-editable; server-set on `planned → in_flight` transition | Actual start of the session. |
| `session_ended_at` | DATETIME | no | null | ISO 8601 UTC; not user-editable; server-set on the transition to any terminal state | Actual end of the session. Mutually exclusive with `not_started` (a session that never started has no ended_at). |
| `session_participants` | JSON | no | `[]` | JSON array of persona identifiers (or `["external:<free-text>"]` for personas not in the PER-NNN system) | Participants in the session. Order-significant if the medium implies it (email thread participants in receipt order); order-insignificant otherwise. |

#### 3.2.5 Medium-specific metadata

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_medium_metadata` | JSON | no | `{}` | JSON object; shape varies by `session_medium` per the table below | Medium-specific extras. SQLite stores the JSON; queryable via `json_extract`. UI renders per-medium fields based on the `session_medium` value. |

**Per-medium shape.** Each value is the recommended starting shape; build-planning may refine. None of these inner fields are CHECK-constrained at the column level (it's JSON); access-layer validation enforces the per-medium shape on POST and PATCH.

| `session_medium` | `session_medium_metadata` recommended keys |
|------------------|-------------------------------------------|
| `chat` | `{"chat_platform": "claude_ai_sandbox" \| "claude_code" \| "claude_desktop" \| "chatgpt" \| "other", "chat_url": "<optional>", "chat_organization": "<optional>"}` |
| `email` | `{"email_subject": "<string>", "email_thread_id": "<provider-specific thread id>", "email_message_id": "<RFC 5322 Message-ID>", "email_direction": "incoming" \| "outgoing" \| "internal"}` |
| `phone` | `{"phone_number": "<E.164>", "phone_direction": "incoming" \| "outgoing", "call_recording_url": "<optional>"}` |
| `zoom` | `{"zoom_meeting_id": "<string>", "zoom_recording_url": "<optional>", "zoom_recurrence_id": "<optional>"}` |
| `in_person` | `{"location": "<string>", "meeting_type": "<optional, e.g. 'workshop'>"}` |
| `slack` | `{"slack_workspace": "<string>", "slack_channel": "<string>", "slack_thread_ts": "<string>"}` |
| `other` | `{}` (open shape; document in `session_description`) |

**Query indexing.** Build-planning decides which inner JSON fields warrant indexed access. Strawman: index `session_medium_metadata->>'email_thread_id'` and `session_medium_metadata->>'zoom_recurrence_id'` because both drive natural session-grouping queries ("show me every session in this email thread").

#### 3.2.6 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `session_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Not user-editable. |
| `session_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Not user-editable. |
| `session_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Set on DELETE; cleared on POST `/restore`. |
| `session_in_flight_at` | DATETIME | no | null | ISO 8601 UTC; server-set on `planned → in_flight` transition | (Equal to `session_started_at`; kept separate for symmetry with the other per-status timestamps.) |
| `session_completed_at` | DATETIME | no | null | ISO 8601 UTC; server-set on the transition to `complete` | Mutually exclusive with `cancelled`, `not_started`, `superseded`. |
| `session_cancelled_at` | DATETIME | no | null | ISO 8601 UTC; server-set on the transition to `cancelled` | |
| `session_not_started_at` | DATETIME | no | null | ISO 8601 UTC; server-set on the transition to `not_started` | The "planned-but-the-event-never-happened" terminal — e.g., a Zoom no-show, a cancelled-day-of meeting. Mutually exclusive with the other terminals. |
| `session_superseded_at` | DATETIME | no | null | ISO 8601 UTC; server-set on the transition to `superseded` | |

**No `session_planned_at` column.** Equal to `session_created_at` by construction; redundant. Same posture as `conversation.md` for parallel reasons.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

**Workstream membership.** Every session belongs to exactly one workstream. References-edge per inherited precedent. The kind `session_belongs_to_workstream` is new in this release.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `session_belongs_to_workstream` | `session` | `workstream` | The session is a member of the named workstream. Cardinality: exactly one outgoing edge per session; missing or multiple returns HTTP 422. |

**Kickoff-prompt linkage.** A session that opens against a kickoff prompt has a work_ticket of kind `kickoff_prompt` consumed at session start. References-edge.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `session_opens_against_work_ticket` | `session` | `work_ticket` | The session opens against the named kickoff prompt. Cardinality: at most one outgoing edge per session; exactly one inbound edge per work_ticket. Required when `session_status ∈ {in_flight, complete}` and the session was opened against a formal kickoff (organic working sessions like SES-094 may have none). Optional throughout the lifecycle otherwise. |

**Predecessor-session sequencing (Q1 resolution — admitted, optional).** Some mediums have inherent session-level sequencing — email threads, recurring Zoom calls, follow-up phone calls. The `session_follows_from` kind makes that queryable without traversing per-conversation chains.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `session_follows_from` | `session` | `session` | This session continues from the target session at the medium-level (e.g., a reply email continues an earlier email; this week's Zoom follows last week's Zoom). Cardinality: many-to-many (a recurring meeting has one direct predecessor; an email reply may have multiple if the user is consolidating multiple threads). Optional throughout. No cycles enforced at the access layer. |

**Supersession.** A session in `superseded` status must have an outgoing `supersedes` edge to the successor session. Uses the existing generic `supersedes` kind (the `_kinds_for_pair` rule `if source_type == target_type` already admits `supersedes` for same-type pairs).

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `supersedes` (reused) | `session` | `session` | This session was redirected; the target carries the work forward. Required when `session_status == 'superseded'`. |

**Generic cross-references.** Sessions may use `is_about` and `references` for cross-record linkage. No new vocabulary required.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`session` is the target of inbound references from `conversation-v2` and from `commit`, `close_out_payload`, and `deposit_event`. Each source-side spec declares its outbound edge.

| relationship_kind | source | target | mechanism | semantics |
|-------------------|--------|--------|-----------|-----------|
| `conversation_belongs_to_session` (declared in `conversation-v2.md`) | `conversation` | `session` | references-table edge | Every conversation belongs to exactly one session. The successor to `conversation_records_session`. |
| `commit_in_session` (provisional; build-planning settles) | `commit` | `session` | references-table edge or migration of existing `commit_conversation_id` FK | Every commit attributed to a session. Build-planning decides whether the existing `commit_conversation_id` FK on the commits table migrates to a `commit_session_id` FK (preferred for query performance) or moves to a reference edge (preferred for consistency with the v0.7 cross-spec precedent). |
| `close_out_payload_produced_by_session` (declared in revised `close_out_payload.md`) | `close_out_payload` | `session` | references-table edge | Replaces `close_out_payload_produced_by_conversation`. Conversation 2 (build planning) renames the kind in vocab.py + migrates the existing edges. |
| `deposit_event_applies_close_out_payload` (unchanged) | `deposit_event` | `close_out_payload` | references-table edge | Untouched by PI-073 — deposit_event references close_out_payload, not session. |

#### 3.3.3 Hierarchy

Session uses the standard parent-child pattern via the inbound `conversation_belongs_to_session` edge from the new conversation entity (declared in `conversation-v2.md`). One session contains 1..N conversations. No session-to-session hierarchy (the `session_follows_from` kind is a DAG, not a tree).

#### 3.3.4 New reference vocabulary additions this spec requires

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `session_belongs_to_workstream` | Member-of relationship. |
| `REFERENCE_RELATIONSHIPS` | `session_opens_against_work_ticket` | Kickoff-prompt linkage. Successor to `conversation_opens_against_work_ticket`. |
| `REFERENCE_RELATIONSHIPS` | `session_follows_from` | Medium-driven session sequencing. New per Q1. |
| `_kinds_for_pair` | `(session, workstream) → session_belongs_to_workstream` | Source-target binding. |
| `_kinds_for_pair` | `(session, work_ticket) → session_opens_against_work_ticket` | Source-target binding. |
| `_kinds_for_pair` | `(session, session) → session_follows_from` (alongside existing `supersedes` admitted by the same-type rule) | Source-target binding. |
| Retire (declare deprecated; data-migrated by Slice F) | `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation` | The old conversation entity that referenced session no longer exists in its old shape. The new conversation entity has its own `conversation_belongs_to_session` and `conversation_follows_from` (per the companion spec). |

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status | Description | Valid predecessors | Valid successors |
|--------|-------------|--------------------|------------------|
| `planned` | Session scheduled but not yet started. Default starter. | (starter) | `in_flight`, `cancelled`, `superseded`, `not_started` |
| `in_flight` | Session is currently happening (medium-dependent: chat is open, call is connected, meeting is in progress, email is awaiting reply). | `planned` | `complete`, `cancelled`, `superseded`, `not_started` |
| `complete` | Session has ended with at least one closed conversation. Terminal. | `in_flight` | (terminal) |
| `cancelled` | Session was stopped without satisfying its scope and no successor carries the work. Terminal. | `planned`, `in_flight` | (terminal) |
| `not_started` | Session was scheduled but the event never happened (no-show, cancelled day-of, recipient didn't reply within the timeout). Terminal. | `planned` | (terminal) |
| `superseded` | Session was stopped without satisfying its scope, but a successor session (recorded via `supersedes` edge) carries the work forward. Terminal. | `planned`, `in_flight` | (terminal) |

**Lifecycle posture vs DEC-013.** DEC-013's append-only rule applied to a session that existed only as an after-the-fact record. Under the redesign, sessions are first-class lifecycle objects: a Zoom meeting is created in `planned` status when scheduled, transitions to `in_flight` when the meeting starts, and to `complete` when it ends. The lifecycle is workflow-shaped, identical posture to workstream and conversation per the v0.7 precedent.

#### 3.4.2 Transition semantics

Forward-only with four terminals. The two non-terminal states form a linear `planned → in_flight` sequence. Each terminal admits no outgoing transitions (parallel to workstream and original-conversation posture).

**Field-editability across the lifecycle.** Per the supersession-of-DEC-013, the new session entity is **editable** throughout non-terminal lifecycle. A planned session can have its `session_scheduled_for`, `session_participants`, `session_description`, and `session_medium_metadata` updated freely. A session in `in_flight` admits the same updates plus the start-time correction (`session_started_at` PATCH for administrative correction). Once a session reaches any terminal state, only administrative-correction PATCH is admitted (parallel to commit spec §3.4.3) and the close-out-completeness checker (§3.5) enforces the integrity invariants.

#### 3.4.3 Complete-requires-conversation edge

A session reaching `complete` must have at least one inbound `conversation_belongs_to_session` edge — i.e., at least one conversation occurred within it. Access-layer rule enforced at the `in_flight → complete` transition. Returns HTTP 422 with `session_complete_requires_conversation` when violated.

This rule has no parallel in the original session entity (which had no sub-units). It is the structural integrity invariant that distinguishes a `complete` session from a `not_started` session at the database level: a `not_started` session has zero conversations, a `complete` session has 1..N.

#### 3.4.4 Supersession-requires-edge

Inherited from the v0.7 precedent: a session at `session_status == 'superseded'` must have an outgoing `supersedes` reference edge to its successor session.

### 3.5 Validation

Per access layer (`crmbuilder-v2/src/crmbuilder_v2/access/repositories/sessions.py`):

1. `session_identifier` matches `^SES-\d{3}$` and is unique (or server-assigned on omission).
2. `session_title` non-empty after trimming; unique within the engagement (case-insensitive).
3. `session_description` non-empty after trimming.
4. `session_status` in the enum from §3.4.1.
5. `session_medium` in the enum from §3.2.3.
6. `session_medium_metadata` is JSON-decodable and its shape matches the recommended shape for the given `session_medium` (build-planning may relax to "schema warns but accepts" per UX call).
7. `session_participants` is a JSON array (possibly empty) of strings.
8. Lifecycle transitions are valid per §3.4.1's table.
9. `session_complete_requires_conversation` enforced at the `in_flight → complete` transition.
10. `supersession_requires_edge` enforced at the transition to `superseded`.
11. The `session_belongs_to_workstream` edge is present after create (post-insert validation per the v0.7 governance-entity pattern).

### 3.6 REST endpoints

Standard nine-endpoint set per V2 envelope (`{data, meta, errors}`):

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/sessions` | List sessions. Standard pagination. Filters: `session_status`, `session_medium`, `?workstream={WS-NNN}`. |
| GET | `/sessions/{identifier}` | Fetch one session. |
| GET | `/sessions/next-identifier` | Return next available `SES-NNN`. |
| POST | `/sessions` | Create a session. Accepts `identifier: null` for server-assignment. |
| PATCH | `/sessions/{identifier}` | Update mutable fields. Lifecycle transitions trigger access-layer rules. |
| PUT | `/sessions/{identifier}` | Replace mutable fields. |
| DELETE | `/sessions/{identifier}` | Soft-delete. |
| POST | `/sessions/{identifier}/restore` | Restore soft-deleted. |
| GET | `/sessions/{identifier}/conversations` | Derived: list every conversation belonging to this session. |

### 3.7 Acceptance criteria

1. POST with all required fields returns 201 and the created row.
2. POST with omitted identifier auto-assigns the next `SES-NNN`.
3. POST with malformed identifier returns 422.
4. POST with collision returns 409.
5. PATCH to `session_status = 'complete'` on a session with zero conversations returns 422 with `session_complete_requires_conversation`.
6. PATCH to `session_status = 'superseded'` without an outgoing `supersedes` edge returns 422.
7. PATCH on a terminal-status session that attempts to edit content (not administrative-correction) returns 422.
8. DELETE soft-deletes; GET excludes by default; `?include_deleted=true` includes.
9. `GET /sessions/{id}/conversations` returns the conversations in the session, ordered by `conversation_created_at` ascending.
10. Lifecycle transitions emit per-status timestamps consistently with §3.2.6.
11. `session_medium_metadata` round-trips through POST/GET unchanged (JSON-equal).
12. `session_follows_from` edges can form a chain (a → b → c) and resolve via `?follows_from={SES-NNN}`.

### 3.8 Build-planning open questions

These are intentionally deferred from this spec to Conversation 2 (build planning) per the execution plan.

1. **`commit_conversation_id` FK migration.** The existing `commit_conversation_id` FK on the commits table points at the old conversation entity. Under the redesign, every commit attributes to a session (one chat = one session = one or more conversations; a commit's authorship is at session-grain, not necessarily conversation-grain, because a single commit may cover discussion across multiple sub-conversations within a session). Build-planning decides: rename to `commit_session_id` (preferred for query performance) and migrate the FK target, OR convert to a reference edge (preferred for cross-spec precedent consistency). Strawman: rename + migrate, accept the cross-spec deviation, document in the commit-spec change log.
2. **Per-medium JSON validation strictness.** Hard-reject on shape mismatch, or warn-and-accept? Recommendation: warn-and-accept in this release; tighten after real-use signal.
3. **Indexed JSON paths.** Final list of `json_extract`-indexed paths on `session_medium_metadata`.
4. **`session_scheduled_for` timezone handling.** Stored as UTC; UI surfaces in operator's local timezone. Confirm at build-planning.

### 3.9 What this spec does NOT do

- Does not define the per-conversation lifecycle states inside a session — that's the companion spec `conversation-v2.md`.
- Does not specify Alembic migration step-by-step — Slice A of the build plan.
- Does not specify desktop UI layout — Slice E of the build plan.
- Does not migrate existing rows — Slice F of the build plan (the strawman migration rule lives in §6 below for cross-spec readability, but the executable script is Slice F's deliverable).

---

## 4. Cross-spec consistency check

Against `workstream.md`, `conversation.md` (original), `reference_book.md`, `work_ticket.md`, `close_out_payload.md`, `deposit_event.md`, `commit.md`:

- **References-edge precedent.** Honored — every cross-entity relationship is a reference edge, never an FK column on `sessions`.
- **Per-status timestamp precedent.** Honored — one column per non-starter status.
- **Terminal-states-are-terminal precedent.** Honored at the lifecycle-transition level; narrowed at the field-content level per the DEC-013 supersession (content remains editable for administrative correction in terminal states, parallel to commit spec §3.4.3).
- **Identifier-prefix posture.** `SES` is 3 letters — within the 2-to-5-letter guidance from the spec guide.
- **Field-prefix convention (DEC-046).** Honored — every field is `session_*`.

---

## 5. Companion spec dependency

`conversation-v2.md` (next spec, same workstream) declares the new `conversation_belongs_to_session` outbound edge and the new `conversation_follows_from` outbound edge. The vocab.py additions for those kinds belong to that spec; this spec only registers the inbound relationships from the session side for cross-reference.

---

## 6. Migration of existing records (strawman — Slice F authors the executable)

Per PI-073 Q4 resolution:

- **Existing `conversation` rows become new `session` rows.** `CONV-NNN` identifiers stay (now meaning session). Mapping:
  - `conversation_identifier` → `session_identifier` (the prefix mismatch is accepted; the row remains queryable under `CONV-NNN`).
  - `conversation_title` → `session_title`.
  - `conversation_purpose` + `conversation_description` → `session_description` (concatenated with a separator).
  - `conversation_notes` → `session_notes`.
  - `conversation_status` → `session_status` via the mapping `planned→planned`, `kickoff_drafted→planned`, `ready→planned`, `in_flight→in_flight`, `complete→complete`, `cancelled→cancelled`, `superseded→superseded`. (The intermediate `kickoff_drafted` and `ready` collapse into `planned` because the new model uses the kickoff-linkage edge to capture kickoff state, not a status.)
  - `conversation_created_at` → `session_created_at`. Same for `_updated_at`, `_deleted_at`, `_started_at`, `_completed_at`, `_cancelled_at`, `_superseded_at` mapping to their `session_*` counterparts.
  - `session_medium = 'chat'`, `session_medium_metadata = {"chat_platform": "claude_ai_sandbox"}` (default — operators can hand-edit historical records if a specific platform is known).
  - `session_participants = []` (empty; operators can backfill).
  - Existing `conversation_belongs_to_workstream` edges rename to `session_belongs_to_workstream`.
  - Existing `conversation_opens_against_work_ticket` edges rename to `session_opens_against_work_ticket`.
  - Existing `conversation_succeeds_conversation` edges rename to `session_follows_from`.
  - Existing `conversation_records_session` edges: each old-conversation/old-session pair gets unified into the new model — the old conversation row becomes the new session, the old session row becomes a single conversation belonging to it (see `conversation-v2.md` §6 for the conversation side).
- **Existing `session` rows become new `conversation` rows (per the companion spec).** `SES-NNN` identifiers stay (now meaning topical conversation within a session). The companion spec details that mapping.
- **Identifier-prefix asymmetry accepted.** Operators reading `SES-094` post-migration must remember it now identifies a topical conversation, not a session-level record. Conversation N+1 of the execution plan ships a CLAUDE.md update with the migration table; this is a one-time documentation cost rather than an identifier-rewriting cost.

---

## 7. Cross-references

- DEC-119 (original conversation-entity decision) — narrowed by DEC-314.
- DEC-013 (sessions are append-only) — **superseded in its entirety by DEC-314**.
- DEC-314 (the PI-073 redesign decision) — the authority for this spec.
- PI-073 — the planning item this spec resolves (partially; full resolution at Conversation N+1).
- `conversation-v2.md` — companion spec, defines the topical sub-unit.
- `pi-073-execution-plan.md` — the master plan.
- `governance-entity-schema-spec-guide.md` — the spec template.
- v0.7 governance-entity precedent specs: `workstream.md`, original `conversation.md`, `reference_book.md`, `work_ticket.md`, `close_out_payload.md`, `deposit_event.md`, `commit.md`.
