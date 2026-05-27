# Governance Entity Schema Spec — `conversation` (v2 redesign)

**Last Updated:** 05-27-26
**Status:** Draft v1.0 — produced by PI-073 architectural-design conversation (SES-095)
**Position in workstream:** Second of two specs in the PI-073 redesign workstream (`session-v2` then `conversation-v2`).
**Predecessor (sequencing):** `session-v2.md` (companion spec, this workstream)
**Predecessor (historical):** original `conversation.md` (the entity being redesigned — the original conversation was a chat-lifecycle wrapper per DEC-119; the new conversation is a topical sub-unit within a session per DEC-314)
**Successor:** the build-planning conversation (Conversation 2 of the PI-073 sequence per `pi-073-execution-plan.md`)
**Authority:** This spec inherits the v0.7 governance-entity cross-spec precedents (references-edge over FK; per-status lifecycle timestamps; terminal-states-are-terminal) AND inherits the `session-v2.md`-established narrowing on terminal-state field-editability for administrative correction.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-27-26 | Doug Bower / Claude Code | Initial draft. Produced by the PI-073 architectural-design conversation (SES-095). Establishes `conversation` as the topical sub-unit within a session — one session contains one or more conversations, each a focused topical discussion with its own lifecycle. Resolves PI-073 Q2 (planned-but-not-started conversations exist as records in `not_started` state — option (a)). The lifecycle states are `planned → in_flight → complete` with terminal options `cancelled`, `superseded`, `not_started`. Carries the topical-summary and decisions/PI-resolution attribution that the old session entity (now repurposed; see `session-v2.md`) used to carry. Companion to `session-v2.md`. |

---

## Change Log

**Version 1.0 (05-27-26):** Initial creation. Defines the new `conversation` as a topical sub-unit of a session — replacing both the original `conversation` entity (a chat-lifecycle wrapper that became redundant once `session-v2` carries the lifecycle) and the original `session` entity's role as topical-summary record. Each session has 1..N conversations; conversations do not span sessions. Cross-session topical continuity is expressed via the new `conversation_follows_from` (direct successor) and `conversation_relates_to` (related but not direct successor) reference edges. The schema is intentionally minimum-viable: identifier, title, purpose, description, status with per-status timestamps, mandatory `conversation_belongs_to_session` edge, plus optional cross-session linkage and supersession. Identifier-prefix `CONV` is retained — under the v2 model, `CONV-NNN` identifies a session (per `session-v2.md` §6 migration); the new conversation entity introduces a **new identifier prefix** to avoid collision. See §3.1 for the prefix choice.

---

## 1. Purpose and Position

This document specifies the redesigned `conversation` entity for V2's storage layer. It is the **second of two** specs produced by the PI-073 architectural-design conversation, designed after `session-v2.md` because every conversation belongs to a session.

The redesign collapses the original 1:0..1 `conversation` / `session` relationship into a 1:N `session` / `conversation` relationship. The old `conversation` entity (per DEC-119) was a lifecycle wrapper around what was structurally a single concept; the old `session` entity (per DEC-013) was a topical-summary append-only record. The redesign promotes session to the medium-agnostic communication container (carrying the lifecycle that conversation used to carry, plus medium metadata) and creates a new conversation entity as a focused topical sub-unit that can repeat 1..N within a session — letting one Zoom meeting hold three distinct topical discussions, or one email hold a single topical reply.

This spec **inherits four cross-spec precedents**:

- **References-edge over foreign-key** for the conversation→session parent linkage. The new `conversation_belongs_to_session` edge lives in `refs`, not as an FK column on conversations.
- **Per-status lifecycle timestamps** for the conversation's workflow-shaped lifecycle.
- **Terminal-states-are-terminal** at the lifecycle-transition level.
- **Administrative-correction PATCH on terminal-state field content** — per the narrowing `session-v2.md` established when superseding DEC-013. The new conversation inherits that narrowing: once a conversation reaches a terminal state, only administrative-correction PATCH is admitted.

This spec **does not establish a new cross-spec precedent.** It is a pure consumer of the v0.7 + `session-v2.md` precedents.

---

## 2. Summary

A `conversation` record in V2 represents one focused topical discussion within a session. Real examples under the new model: a Zoom meeting that covers (a) status review, (b) blocker resolution, (c) next-week planning is one session with three conversations; an email that asks a single question is one session with one conversation; a Claude.ai chat that walks through a design decision then closes is one session with one conversation; a Claude.ai chat that started on Topic X, drifted to Topic Y, and ended on Topic Z is one session with three conversations.

The schema is the thinnest shape that captures the topical-discussion concept faithfully: an identifier with a new prefix (`TOP` per §3.1 — distinct from the existing `TOP` topic entity? see §3.1 for the resolution), a title, a one-sentence purpose, a paragraph description, an optional summary captured at close, a five-status lifecycle (`planned` → `in_flight` → one of `complete` / `cancelled` / `not_started` / `superseded`) with timestamps for each non-starter transition, mandatory parent-session membership via `conversation_belongs_to_session`, optional cross-session linkage via `conversation_follows_from` (direct successor) and `conversation_relates_to` (loose relation), and supersession via the generic `supersedes` kind.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `conversation` (table renamed under the hood per §6 migration; the entity-type name is reused so the existing CHECK constraints and downstream code reference shape is preserved) |
| Display name (singular) | Conversation |
| Display name (plural) | Conversations |
| Identifier prefix | **`CNV` (proposed) — see decision discussion below** |
| Identifier format | `CNV-NNN`, zero-padded to 3 digits |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /conversations/next-identifier` |

**Identifier-prefix posture — decision.** The original conversation entity used `CONV-NNN`. Under the v2 redesign, per `session-v2.md` §6 migration, existing `CONV-NNN` identifiers stay as session identifiers (they semantically shift to mean session, not conversation). The new conversation entity therefore needs a **different prefix** to avoid collision with the migrated sessions.

Candidates considered:
- `CNV` — three-letter, visually distinct from `CONV`, no clash with existing prefixes (DEC, PI, SES, REF, PER, PROC, ENT, DOM, RSK, TOP, WS, REFB, WT, COP, DEP, COM, CDS, CNV). **Recommended.**
- `CON` — three-letter, but visually too close to old `CONV`; rejected.
- `TOPIC` — five-letter, semantically apt (a conversation IS a focused topic within a session), but collides with the existing methodology entity `topic` (`TOP-NNN`). Rejected.
- `SUB` — three-letter, but loses the "conversation" semantics entirely. Rejected.

**Final call:** `CNV-NNN`. The companion `session-v2.md` keeps `SES-NNN` for sessions; the existing `CONV-NNN` identifiers (1 through 64 at the time of this spec) move to the session table under the v2 migration and retain their `CONV` prefix as a historical artifact — only newly-created sessions under the v2 model use `SES-NNN`. New conversations under the v2 model use `CNV-NNN`. This is the cleanest path that preserves backward identifier readability while opening a fresh sequence for the new entity.

Build-planning may revisit. If `CNV` causes operator confusion in practice, a one-time renumbering migration is straightforward.

### 3.2 Fields

Field naming per DEC-046 prefix convention: all fields prefixed `conversation_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_identifier` | TEXT | yes | server-assigned | `^CNV-\d{3}$`, unique | The conversation identifier in `CNV-NNN` format. |
| `conversation_title` | TEXT | yes | — | non-empty trimmed | The topical title of the conversation. Examples: "Status review", "Blocker resolution — deployment cert renewal", "Q3 plan review". |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of what the conversation produces. |
| `conversation_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing the topical scope of the conversation. |
| `conversation_summary` | TEXT | no | — | — | Captured at close — the topical outcome. Optional at create; recommended at the transition to `complete`. Plain text. |
| `conversation_notes` | TEXT | no | — | — | Internal scratchpad. Same role as `session_notes` but at conversation grain. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_status` | TEXT | yes | `planned` | enum: `planned` \| `in_flight` \| `complete` \| `cancelled` \| `not_started` \| `superseded`; transitions per §3.4 | Lifecycle status. |

#### 3.2.4 Relationship fields

None. Every relationship lives in `refs` per the inherited precedent.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Not user-editable. |
| `conversation_updated_at` | DATETIME | yes | server-set on insert and update | ISO 8601 UTC | Not user-editable. |
| `conversation_deleted_at` | DATETIME | no | null | ISO 8601 UTC when set | Soft-delete marker. |
| `conversation_in_flight_at` | DATETIME | no | null | server-set on `planned → in_flight` | |
| `conversation_completed_at` | DATETIME | no | null | server-set on transition to `complete` | Mutually exclusive with the other terminals. |
| `conversation_cancelled_at` | DATETIME | no | null | server-set on transition to `cancelled` | |
| `conversation_not_started_at` | DATETIME | no | null | server-set on transition to `not_started` | The Q2-resolution column — a conversation planned within a session that never opened. Examples: a Zoom meeting that planned three topics but only covered two; the third conversation lands in `not_started` at the session's close. |
| `conversation_superseded_at` | DATETIME | no | null | server-set on transition to `superseded` | |

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

**Session membership (mandatory).** Every conversation belongs to exactly one session.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `conversation_belongs_to_session` | `conversation` | `session` | The conversation occurs within the named session. Cardinality: exactly one outgoing edge per conversation (post-create). |

**Cross-session direct continuity (Q2 extension).** A conversation in a new session may continue a topic from a prior conversation in a prior session — this is the cross-session topical chain that the PI-073 body called out explicitly. Distinct from `session_follows_from` (medium-driven session chain): `conversation_follows_from` is topic-driven, not medium-driven.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `conversation_follows_from` | `conversation` | `conversation` | This conversation directly continues a topic from the target conversation in a prior session (or earlier in the same session). Cardinality: many-to-many but with the strong convention that direct-continuity chains are linear (a→b→c, not a→b and a→c). No access-layer cycle check (linearity is operator discipline, not constraint). |

**Cross-session loose relation.** A conversation is relevant to another conversation without being a direct successor — related topics, prior context worth flagging, sibling-topic discussion.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `conversation_relates_to` | `conversation` | `conversation` | This conversation is loosely related to the target — same topical area, sibling discussion, useful prior context. Cardinality: many-to-many. |

**Supersession.** Generic `supersedes` reused.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `supersedes` (reused) | `conversation` | `conversation` | This conversation was redirected; the target carries forward. Required when `conversation_status == 'superseded'`. |

**Topical attribution to governance records.** A conversation produces decisions, surfaces planning items, references prior records — these use the existing `decided_in`, `addresses`, `resolves`, `is_about`, `references` kinds with no new vocabulary. The source/target conventions are unchanged from the v0.7 model except the `decided_in` reference now targets `conversation` instead of `session` for the per-topic attribution.

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `decided_in` (existing) | `decision` | `conversation` | The decision was made in the named conversation. Target type changes from `session` to `conversation` under the v2 model — per-topic decision attribution lives at conversation grain. Existing `decided_in → session` edges migrate per Slice F. |
| `addresses` (existing) | `planning_item` | `decision` \| `conversation` | The PI addresses the named decision or conversation. Unchanged. |
| `resolves` (existing) | `conversation` | `planning_item` | The conversation resolves the named PI. Source type changes from `session` to `conversation` under the v2 model. Existing `resolves` edges sourced from `session` migrate per Slice F. |

#### 3.3.2 Inbound relationships

| relationship_kind | source | target | semantics |
|-------------------|--------|--------|-----------|
| `decided_in` (declared above; listed here for completeness) | `decision` | `conversation` | |
| `resolves` (declared above) | `conversation` | `planning_item` | (this is outbound; included in the conversation→PI direction) |

#### 3.3.3 Hierarchy

Conversation is the child in the session→conversation hierarchy. No conversation-to-conversation parent-child hierarchy (the `_follows_from` and `_relates_to` kinds are DAGs, not trees).

#### 3.3.4 New reference vocabulary additions this spec requires

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `conversation_belongs_to_session` | Mandatory parent linkage. Successor to the old `conversation_records_session` (which expressed the inverse direction and was 1:0..1; the new edge is N:1 and parent-pointing). |
| `REFERENCE_RELATIONSHIPS` | `conversation_follows_from` | Cross-session direct topical continuity. New per Q2. |
| `REFERENCE_RELATIONSHIPS` | `conversation_relates_to` | Cross-session loose topical relation. New per Q2. |
| `_kinds_for_pair` | `(conversation, session) → conversation_belongs_to_session` | Source-target binding. |
| `_kinds_for_pair` | `(conversation, conversation) → conversation_follows_from` (alongside existing `supersedes`) | Source-target binding. |
| `_kinds_for_pair` | `(conversation, conversation) → conversation_relates_to` | Source-target binding. Sibling to `_follows_from`; the two kinds may co-exist on the same source-target pair (a conversation can both continue and relate to a sibling). |
| Retarget (existing kind, target type changes) | `decided_in`: `(decision, session)` → `(decision, conversation)` | Topical attribution lives at conversation grain. The CHECK on `refs.relationship_kind` is unchanged; only the operator-facing semantics shift. |
| Retarget | `resolves`: `(session, planning_item)` → `(conversation, planning_item)` | Source type shifts to conversation. Same CHECK posture. |

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status | Description | Predecessors | Successors |
|--------|-------------|--------------|------------|
| `planned` | The topical conversation is planned within its session but not yet opened. Default starter. | (starter) | `in_flight`, `cancelled`, `superseded`, `not_started` |
| `in_flight` | The topical conversation is in progress within its session. | `planned` | `complete`, `cancelled`, `superseded`, `not_started` |
| `complete` | The topical conversation has reached its conclusion. Terminal. | `in_flight` | (terminal) |
| `cancelled` | The conversation was stopped without conclusion and no successor carries the work. Terminal. | `planned`, `in_flight` | (terminal) |
| `not_started` | The conversation was planned but the session closed without opening it (Q2 resolution). Terminal. | `planned` | (terminal) |
| `superseded` | The conversation was redirected and a successor (recorded via `supersedes` edge) carries the work. Terminal. | `planned`, `in_flight` | (terminal) |

#### 3.4.2 Transition semantics

Forward-only; four terminals. Inherits the `session-v2.md`-established narrowing on terminal-state field-editability: a `complete` conversation admits administrative-correction PATCH for `conversation_summary` and `conversation_notes` content fields; lifecycle transitions out are not admitted.

**`not_started` automation hook (optional, build-planning).** When a parent session transitions to `complete` or `cancelled`, any `planned` conversations within that session may be auto-flipped to `not_started` by the access layer. Strawman: yes, auto-flip on session close. Build-planning decides whether to make this mandatory or opt-in via a PATCH parameter on the session-close transition.

#### 3.4.3 Complete-requires-summary (soft)

`conversation_status == 'complete'` should have `conversation_summary` populated — but this is a UX recommendation, not an access-layer constraint. Forcing it would break the existing pattern where a session record's `topics_covered` and `summary` are authored at close-out-payload time, after the lifecycle transition. Slice A's migration backfills `conversation_summary` from the old `session.summary` field for migrated records.

#### 3.4.4 Supersession-requires-edge

Inherited: `conversation_status == 'superseded'` requires an outgoing `supersedes` reference edge.

### 3.5 Validation

1. `conversation_identifier` matches `^CNV-\d{3}$` and is unique (or server-assigned).
2. `conversation_title`, `conversation_purpose`, `conversation_description` are non-empty after trimming.
3. `conversation_status` in the enum.
4. Lifecycle transitions valid per §3.4.1.
5. `conversation_belongs_to_session` edge present after create (post-insert validation).
6. `supersession_requires_edge` enforced at `superseded` transition.

### 3.6 REST endpoints

Standard nine-endpoint set per V2 envelope:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/conversations` | List conversations. Filters: `conversation_status`, `?session={CONV-NNN \| SES-NNN}`. |
| GET | `/conversations/{identifier}` | Fetch one. |
| GET | `/conversations/next-identifier` | Return next `CNV-NNN`. |
| POST | `/conversations` | Create. |
| PATCH | `/conversations/{identifier}` | Update. |
| PUT | `/conversations/{identifier}` | Replace. |
| DELETE | `/conversations/{identifier}` | Soft-delete. |
| POST | `/conversations/{identifier}/restore` | Restore. |
| GET | `/conversations/{identifier}/decisions` | Derived: decisions decided in this conversation. |

### 3.7 Acceptance criteria

1. POST with all required fields returns 201.
2. POST omitting identifier auto-assigns next `CNV-NNN`.
3. POST on a conversation without an accompanying `conversation_belongs_to_session` edge returns 422 (post-insert validation).
4. PATCH to `superseded` without `supersedes` edge returns 422.
5. PATCH to `complete` is admitted with or without `conversation_summary` (soft rule).
6. PATCH on a terminal-status conversation that attempts non-administrative content edits returns 422.
7. Cross-session `conversation_follows_from` edge resolves correctly when traversed via `?follows_from={CNV-NNN}`.
8. DELETE soft-deletes; restore reverses.
9. `GET /conversations/{id}/decisions` returns decisions with `decided_in → CNV-NNN` ordered by `decision_date` ascending.
10. Migration: existing `SES-NNN` records (per Slice F) appear as conversations with their original identifier-prefix preserved (`SES-NNN` reads as conversation identifier post-migration, accepted asymmetry).

### 3.8 Build-planning open questions

1. **Auto-flip planned → not_started on session close.** Default on, or opt-in? Recommendation: on by default; PATCH parameter to skip when manually-handling the case.
2. **`conversation_summary` required on `complete`?** Soft rule for now; hardening deferred.
3. **`decided_in` and `resolves` retargeting.** All existing edges migrate from session-targeted to conversation-targeted in Slice F. Build-planning confirms the per-row mapping (existing session SES-NNN has its associated conversation — under the v2 model, each old session becomes one conversation; the mapping is 1:1 on identifier-string, only the type label flips).

### 3.9 What this spec does NOT do

- Does not specify Alembic migration script (Slice A).
- Does not specify desktop UI nesting (Slice E).
- Does not specify the data-migration executable (Slice F).

---

## 4. Cross-spec consistency check

Against `session-v2.md`, `workstream.md`, `commit.md`:

- References-edge precedent — honored.
- Per-status timestamps — honored.
- Terminal-states-are-terminal (lifecycle level) — honored.
- Administrative-correction PATCH on terminal field content — inherited from `session-v2.md`'s narrowing.
- Identifier prefix `CNV` — three letters, no clash, distinct from `CONV`.
- Field-prefix convention (DEC-046) — honored.

---

## 5. Companion spec dependency

This spec depends on `session-v2.md` for the parent session shape. The new `conversation_belongs_to_session` outbound edge targets the new session entity.

---

## 6. Migration of existing records (strawman — Slice F authors the executable)

Per PI-073 Q4 resolution, and aligned with `session-v2.md` §6:

- **Existing `session` rows (SES-NNN) become new `conversation` rows.** `SES-NNN` identifiers stay (now meaning conversation). Each old session row maps to one conversation row in the new model, attached to the migrated session (which was the old conversation row paired with it).
  - `session.identifier` (SES-NNN) → `conversation_identifier` (SES-NNN — accepted asymmetry per §3.1).
  - `session.title` → `conversation_title`.
  - `session.topics_covered` + `session.summary` → `conversation_summary` (concatenated).
  - `session.conversation_reference` → `conversation_description` (the textual context summary).
  - `session.session_date` + `session.created_at` → `conversation_in_flight_at` and `conversation_completed_at` (the old session's data captured a single point-in-time event; under the new model both timestamps map to that event).
  - `session.status` → `conversation_status` (`Complete` → `complete`).
  - New `conversation_belongs_to_session` edge: links each migrated conversation to its parent session (the migrated old-conversation row per `session-v2.md` §6 mapping).
- **Net mapping shape.** Each existing old-conversation row (CONV-NNN) becomes a session. Each existing old-session row (SES-NNN) becomes a conversation belonging to it (via the old `conversation_records_session` edge, which identifies which session each conversation belongs to). Identifiers preserve across the migration; the type label flips per Slice F.
- **`decided_in` and `resolves` edge migration.** All existing `decided_in → session` edges retarget to the migrated conversation (same SES-NNN identifier, now a CNV-equivalent under the new model). All existing `resolves` edges from session to PI retarget the source from session to conversation. Same SES-NNN identifier, source-type-label flips.

---

## 7. Cross-references

- DEC-119 (original conversation-entity decision) — narrowed by DEC-314 (the lifecycle the original conversation carried now lives on session; the new conversation has its own narrower topical lifecycle).
- DEC-013 (sessions are append-only) — superseded by DEC-314.
- DEC-314 — the PI-073 redesign decision; authority for this spec.
- PI-073 — the planning item.
- `session-v2.md` — companion spec.
- `pi-073-execution-plan.md` — the master plan.
- v0.7 governance-entity precedent specs.
