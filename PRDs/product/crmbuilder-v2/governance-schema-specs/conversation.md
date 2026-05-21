# Governance Entity Schema Spec — `conversation`

**Last Updated:** 05-21-26 06:00
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** Second of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-048 (`workstream` schema-design conversation)
**Successor conversation:** `reference_book` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-21-26 06:00 | Doug Bower / Claude | Initial draft. Produced by the second schema-design conversation in the governance-entity schema-design workstream. Establishes the `conversation` entity type for V2 storage. Adopts the three cross-spec precedents locked by `workstream.md`: references-edge over foreign-key for parent-child governance relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, and terminal-states-are-terminal discipline. Resolves the kickoff's drift toward an FK on the sessions table in favour of a new references-edge kind `conversation_records_session` consistent with the precedent. Introduces a new same-type sequencing kind `conversation_succeeds_conversation` (the first divergence from workstream's defer-sequencing posture, justified by conversation-sequencing frequency). Commits a tentative kind name `conversation_opens_against_work_ticket` against the not-yet-designed `work_ticket` entity, with explicit reconciliation by build-planning. |

---

## Change Log

**Version 1.0 (05-21-26 06:00):** Initial creation. Defines `conversation` as the V2 governance entity type that hosts the conversational-work-unit concept through its full lifecycle, distinct from the after-the-fact session record per DEC-119. Establishes six content/classification fields (`conversation_identifier`, `conversation_title`, `conversation_purpose`, `conversation_description`, `conversation_notes`, `conversation_status`) plus nine timestamp columns (three inherited base, six per-status lifecycle), a seven-status lifecycle (`planned` → `kickoff_drafted` → `ready` → `in_flight` → one of `complete` / `cancelled` / `superseded`) with truly-terminal terminals inherited from workstream's precedent and a supersession-requires-edge rule inherited verbatim, no outgoing foreign-key columns (every relationship lives in `refs`), four references-edge kinds (`conversation_belongs_to_workstream` registered here per workstream.md's deferral to this spec, plus three new: `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation`), and the standard endpoint set with server-side status-transition validation and identifier auto-assignment. Establishes one new cross-spec precedent for the four remaining schemas: typed predecessor-successor edges within an entity family are introduced when the family's sequencing is structurally frequent, even where the workstream entity's parallel question was deferred to signal. Eighteen acceptance criteria captured.

---

## 1. Purpose and Position

This document specifies the `conversation` entity type for V2's storage layer. It is the **second of six** schema specs produced by the governance-entity schema-design workstream — designed after `workstream.md` because every conversation belongs to a workstream and designing in that order lets the conversation spec treat workstream as a settled referent.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, `conversation`, then `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event` — feeding a seventh build-planning conversation that integrates them into a coherent release.

`conversation`'s primary scope in this release is to host the unit-of-conversational-work concept through its full lifecycle, from the moment work is identified through to the moment the conversation closes with a session record. The schema is intentionally minimum-viable. Estimated duration, priority, conversation-kind enums, and outcome summaries are deliberately out of scope; each is deferred to a future release pending real-use signal.

This conversation **inherits three cross-spec precedents locked by SES-048** and applies them throughout:

- **References-edge over foreign-key for parent-child governance relationships.** Every conversation→other-entity relationship in this spec lives in `refs`, never as a foreign-key column. This includes the conversation→session relationship — resolving the kickoff's working-assumption drift toward an FK on the sessions table in favour of the locked precedent. No modification to the sessions table.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles.** Conversation carries one timestamp column per non-starter status, server-set on transition. The propose-verify pattern from the methodology entities does not apply.
- **Terminal-states-are-terminal discipline.** Once a conversation reaches `complete`, `cancelled`, or `superseded`, no transitions out are admitted — including transitions between terminal states. Reactivation is modelled as a new conversation that supersedes the prior.

This conversation also **establishes one new cross-spec precedent** the remaining four schemas inherit by default and may deviate from with rationale:

- **Typed predecessor-successor edges are introduced when the entity family's sequencing is structurally frequent.** Workstream deferred its `workstream_succeeds_workstream` kind to signal because workstream sequencing is rare. Conversation introduces `conversation_succeeds_conversation` in this release because conversation sequencing is structurally part of every conversation's existence within a workstream — the precedent is frequency-driven rather than dogmatic.

---

## 2. Summary

A `conversation` record in V2 represents one unit of conversational work through its full lifecycle. Real examples already implicit in the project's history include this conversation (the conversation schema-design conversation, in flight at this spec's authoring time); SES-048's conversation (the workstream schema-design conversation, complete); SES-046's conversation (the strategic scoping conversation that surfaced the governance gap, complete with an ad-hoc opening); SES-047's conversation (the governance workstream-establishing planning conversation, complete); and the not-yet-opened reference-book schema-design conversation (planned at this spec's authoring time, with its kickoff already drafted at `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md`). Each is structurally a conversational work unit with a defined beginning, middle, and end — but before this entity type lands, each exists only as free-text mention in session records and as a kickoff-prompt filename pattern. The `conversation` entity makes them queryable.

The schema in this release is the thinnest shape that captures the conversational-work-unit concept faithfully: a human-readable title, a one-sentence purpose, a paragraph description, an optional consultant notes field, a seven-status lifecycle with timestamps for each non-starter transition, mandatory membership in exactly one workstream via a references-edge to that workstream, and four kinds of additional references-edge linkage to its kickoff prompt (a work_ticket), its session record (when complete), its predecessor and successor conversations (when meaningfully chained), and any other conversations or governance records it references generically. The schema deliberately omits estimated duration, priority, conversation-kind taxonomy, outcome summaries, and direct close-out-payload or deposit-event linkages — each grows additively in a later release if real-use signal supports it, and the close-out-payload and deposit-event linkages are designed inbound from those entities' own specs.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `conversation` |
| Display name (singular) | Conversation |
| Display name (plural) | Conversations |
| Identifier prefix | `CONV` |
| Identifier format | `CONV-NNN`, zero-padded to 3 digits (e.g., `CONV-001`, `CONV-049`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /conversations/next-identifier` |

**Identifier-prefix posture.** `CONV` is four letters, deliberately distinguishing it from the two- and three-letter prefixes that dominate the existing set. The four-letter form matches the existing `PROC` and `CRMC` methodology-entity precedents and avoids the ambiguity of two-letter `CV` (which could read as "curriculum vitae" or other domain shorthand). DEC-123 affirmed that the cross-spec norm is not locked at two letters; each downstream conversation makes its own call within the spec guide's 2-to-5-letter range. The collision list has no conflict with `CONV`.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `conversation_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_identifier` | TEXT | yes | server-assigned | `^CONV-\d{3}$`, unique | The conversation identifier in `CONV-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /conversations/next-identifier` returns the next available value. |
| `conversation_title` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Conversation title in the project's working language (e.g., "Workstream entity schema design", "Conversation entity schema design", "Governance workstream-establishing planning"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of what the conversation produces and why it exists. Mirrors `workstream_purpose`'s role at conversation granularity — the priority-test artifact at the conversational-work-unit level. Plain text in this release. |
| `conversation_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing the scope and shape of the conversation — what deliverables are expected, what discussion structure is anticipated, what end-state defines completion. The intended-deliverable description that the kickoff prompt names as a candidate first-class field is folded into this paragraph rather than carried as a separate column. Plain text in this release. |
| `conversation_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the conversation's user-facing summary. Used to capture pre-conversation reasoning ("opening notes before drafting the kickoff"), mid-conversation context that doesn't fit the seed prompt, or post-conversation observations worth surfacing in the close-out. Plain text in this release; structured-journal pattern deferred to signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_status` | TEXT | yes | `planned` | enum: `planned` \| `kickoff_drafted` \| `ready` \| `in_flight` \| `complete` \| `cancelled` \| `superseded`; valid transitions per section 3.4; additional rules for `complete` and `superseded` per sections 3.4.3 and 3.4.4 | Lifecycle status. See section 3.4 for the full state machine. |

#### 3.2.4 Relationship fields

None. Every relationship — workstream membership, session linkage, kickoff-prompt linkage, predecessor/successor chaining, supersession, generic cross-references — lives in the universal references table per the inherited precedent from workstream.md and the locked Decision 1 (this conversation). No foreign-key columns on the conversation table.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `conversation_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `conversation_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `conversation_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |
| `conversation_kickoff_drafted_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `planned` → `kickoff_drafted` transition. Once set, not user-editable. |
| `conversation_ready_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `kickoff_drafted` → `ready` transition. Once set, not user-editable. |
| `conversation_started_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `ready` → `in_flight` transition. Once set, not user-editable. |
| `conversation_completed_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `in_flight` → `complete` transition. Once set, not user-editable. Mutually exclusive with `conversation_cancelled_at` and `conversation_superseded_at` — exactly one of the three terminal-state timestamps is populated on any terminal record. |
| `conversation_cancelled_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `cancelled` (reachable from `planned`, `kickoff_drafted`, `ready`, or `in_flight`). Once set, not user-editable. |
| `conversation_superseded_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `superseded` (reachable from `planned`, `kickoff_drafted`, `ready`, or `in_flight`). Once set, not user-editable. |

**No `conversation_planned_at` column.** A conversation's planned-at moment is always equal to its `conversation_created_at` (the default starter status is `planned`, set at insert time). A separate column would be redundant. The single exception — a backfilled record whose historical planning happened before its database insert — uses `conversation_created_at` with the backfill timestamp; the distinction is not tracked separately in this release. Identical posture to workstream.md.

**No storage-level length caps** on text fields, matching the workstream and methodology precedents. UI placeholder text provides soft guidance ("One sentence", "Paragraph describing the conversation"). Pathological-input handling deferred to real-use signal.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

Five outgoing reference kinds across four relationship semantics. All five are modelled as references-table edges per the inherited cross-spec precedent.

**Workstream membership.** Every conversation belongs to exactly one workstream. The relationship is mandatory at the access layer for any conversation past creation — the constraint is the realization of DEC-120's binding text ("Conversations belong to a workstream"). This kind was named in `workstream.md` section 3.3.2 as the inbound side; the registration in vocab.py and the access-layer enforcement of cardinality belong to this spec, per workstream.md's explicit note.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `conversation_belongs_to_workstream` | `conversation` | `workstream` | The conversation is a member of the named workstream. Cardinality: every conversation has exactly one outgoing edge of this kind; missing edge or multiple edges return HTTP 422 at the access layer. A workstream has many conversations (typically 5 to 15). |

**Session record linkage.** A conversation that has reached `complete` status has produced exactly one session record. The relationship from conversation to session is the realization of Decision 1 of this conversation — references-edge over the FK-on-sessions alternative offered by the kickoff's working assumption, preserving the locked precedent and avoiding any modification to the append-only sessions table shape per DEC-013.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `conversation_records_session` | `conversation` | `session` | The session record is the after-the-fact record of this conversation. Cardinality: a conversation has at most one outgoing edge of this kind; a session record is referenced by at most one such edge (one session, one conversation per DEC-013). Required when `conversation_status = 'complete'`; absence on a complete record returns HTTP 422 at the access layer. |

**Kickoff prompt linkage.** A conversation that has reached `kickoff_drafted` status or later has a kickoff prompt, modelled as a work_ticket record (the entity designed in the fourth schema-design conversation of this workstream). The relationship is one-to-one — each conversation opens against at most one kickoff; each work_ticket is consumed by exactly one conversation per the workstream plan's single-use-seed-document framing.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `conversation_opens_against_work_ticket` | `conversation` | `work_ticket` | The conversation opens against the named work_ticket as its kickoff prompt. Cardinality: at most one outgoing edge per conversation; exactly one inbound edge per work_ticket (the work_ticket's single-use property is enforced from work_ticket's side in that spec). Required when `conversation_status` is in `{kickoff_drafted, ready, in_flight, complete}`; optional for `planned`, `cancelled`, and `superseded`. |

**Kind-name posture.** `conversation_opens_against_work_ticket` is committed tentatively in this spec, parallel to workstream.md's tentative `workstream_planned_in_reference_book` commitment. The work_ticket schema-design conversation (third after this one in the workstream) may refine the verb tense or framing for consistency with work_ticket's other inbound kinds (for example, if work_ticket ends up with a uniform "consumed-by" verb pattern across multiple inbound kinds, this kind might shift to `conversation_consumes_work_ticket` for symmetry). The build-planning conversation reconciles any drift between the two specs before the consolidated vocab.py migration is authored.

**Predecessor-successor chaining.** Within a workstream, conversations are often sequenced — every conversation in this governance schema-design workstream has a defined predecessor and successor, captured today only in the in_flight_at_end fields of session records. The `conversation_succeeds_conversation` kind makes the chaining queryable.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `conversation_succeeds_conversation` | `conversation` | `conversation` | This conversation succeeds the target conversation in the workstream's planned sequence. The source is the successor; the target is the predecessor. Cardinality: many-to-many (a build-planning conversation has six predecessor schema-design conversations; a workstream-establishing conversation has multiple direct successors). No required-when rule — chaining is optional, captured when meaningfully sequenced. Direction is enforced at the access layer (no cycles; the workstream entity may impose further constraints in a later release if needed). |

**Cross-spec precedent established by this kind.** Workstream deferred its parallel `workstream_succeeds_workstream` kind to signal because workstream sequencing is rare. Conversation introduces sequencing in this release because conversation sequencing is structurally frequent — every conversation in a sequenced workstream has predecessors and successors, and the existing fallback (text matching against in_flight_at_end fields) is exactly the weak coupling DEC-121 says to eliminate. The remaining four schema specs inherit the principle that typed sequencing kinds are introduced when the entity family's sequencing is structurally frequent.

**Supersession linkage.** When a conversation's status is set to `superseded`, it must have an outgoing reference edge identifying the successor conversation that carries the work forward. The relationship uses the existing generic `supersedes` reference kind (already permitted for `(conversation, conversation)` once `conversation` is in `ENTITY_TYPES` because `_kinds_for_pair`'s `source_type == target_type` rule admits `supersedes` for any same-type pair). No new kind is introduced for this relationship; the established vocabulary is reused, identical to workstream's pattern.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `supersedes` (existing kind, reused) | `conversation` | `conversation` | This conversation was redirected; the target conversation carries forward the work. Required when source.status = `superseded`; access-layer enforces. The same edge expresses two semantically related but distinct cases: (a) scope-change supersession (the kickoff was rewritten enough to warrant a new conversation with its own identifier) and (b) bootstrap-redirect supersession (a planned conversation was replaced by a different planned conversation before either opened). |

**Distinguishing supersession from succession.** The `supersedes` kind expresses a redirect — one conversation was abandoned and another carries the work forward, with the source's lifecycle terminating at `superseded`. The `conversation_succeeds_conversation` kind expresses normal sequencing — both conversations exist as healthy lifecycle objects, with the source positioned after the target in the workstream's planned sequence. The two kinds never co-occur on the same source-target pair; a supersession is a directed replacement, succession is a directed continuation.

**Generic cross-references.** A conversation may reference any other governance record using the existing generic `is_about` and `references` kinds — no new vocabulary required. Cross-workstream conversation references (a conversation in one workstream pointing at work done in a conversation of another) use these generic kinds.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`conversation` is the target of inbound references from three other governance entities — work_ticket, close_out_payload, and deposit_event — whose schema-design conversations follow this one. Each declares its outbound edge to conversation in that spec; conversation.md lists the relationships here for cross-spec consistency-check purposes. The kind names below are tentative and may be refined by the source-side specs.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `work_ticket_consumed_by_conversation` (tentative; work_ticket.md may rename) | `work_ticket` | `conversation` | references-table edge | one-to-one (each work_ticket has exactly one consumer; each conversation has at most one consumed work_ticket as captured by the outbound `conversation_opens_against_work_ticket`) | A work_ticket's single-use property realized from the work_ticket side. |
| `close_out_payload_produced_by_conversation` (tentative; close_out_payload.md may rename) | `close_out_payload` | `conversation` | references-table edge | one-to-one (each close-out payload has exactly one producing conversation; each completed conversation produces at most one payload) | The conversation produced this close-out payload at its close per the apply-script pattern. |
| `deposit_event_records_apply_of_close_out_payload_from_conversation` (tentative shape; deposit_event.md will design) | `deposit_event` | `conversation` (indirectly via close_out_payload) | references-table edge or computed via close_out_payload | one-to-one or one-to-many depending on retry semantics | The deposit event records an apply of a payload originating in this conversation. The deposit_event schema-design conversation decides whether deposit_event references conversation directly or only via close_out_payload. |

These rows are informational from `conversation.md`'s perspective. The vocab.py registration of these kinds and the access-layer enforcement of their cardinalities belong to the source-side specs.

#### 3.3.3 Hierarchy

Conversation does not use the self-referential parent-child hierarchy pattern in this release. A conversation does not contain sub-conversations; the chained sequence pattern captured by `conversation_succeeds_conversation` is a DAG, not a tree. No hierarchy pattern needed.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are named here and aggregated by the build-planning conversation into one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint, alongside the additions from the other five schema specs.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `conversation_belongs_to_workstream` | Member-of relationship. Declared inbound in workstream.md; registered here as outbound (per workstream.md's explicit deferral note). |
| `REFERENCE_RELATIONSHIPS` | `conversation_records_session` | Linkage from a conversation to its session record. Realizes Decision 1 of this conversation. |
| `REFERENCE_RELATIONSHIPS` | `conversation_opens_against_work_ticket` | Linkage from a conversation to its kickoff prompt (a work_ticket). Tentative kind name; work_ticket.md may refine. |
| `REFERENCE_RELATIONSHIPS` | `conversation_succeeds_conversation` | Predecessor-successor chaining within a workstream. New cross-spec precedent — typed sequencing introduced when family-frequency justifies. |
| `ENTITY_TYPES` | `conversation` | This entity type. Already named in workstream.md's additions table; re-listed here for completeness. |
| `ENTITY_TYPES` | `work_ticket` | Required because `conversation_opens_against_work_ticket` names it as target; the work_ticket entity is designed in the fourth conversation. |
| `_kinds_for_pair` | `if source_type == 'conversation' and target_type == 'workstream': kinds.add('conversation_belongs_to_workstream')` | Source-target constraint binding the membership kind to the matching pair only. Already named in workstream.md; re-listed here for completeness. |
| `_kinds_for_pair` | `if source_type == 'conversation' and target_type == 'session': kinds.add('conversation_records_session')` | Source-target constraint binding the session-linkage kind to the matching pair only. |
| `_kinds_for_pair` | `if source_type == 'conversation' and target_type == 'work_ticket': kinds.add('conversation_opens_against_work_ticket')` | Source-target constraint binding the kickoff-linkage kind to the matching pair only. |
| `_kinds_for_pair` | `if source_type == 'conversation' and target_type == 'conversation': kinds.add('conversation_succeeds_conversation')` | Source-target constraint binding the sequencing kind to the same-type pair only. The existing `_kinds_for_pair` rule `if source_type == target_type: kinds.add('supersedes')` already admits `supersedes` for this pair; the new clause adds `conversation_succeeds_conversation` alongside without conflict. |

The existing generic `supersedes` kind is reused for the `(conversation, conversation)` supersession edge; no addition required for that relationship. The existing generic `is_about` and `references` kinds are admitted for any pair by the existing `_kinds_for_pair` defaults and cover all generic cross-references including cross-workstream conversation references; no additions required.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `planned` | The conversation has been identified as work to do but no kickoff prompt has been drafted yet. **Default starter status.** | (none — starter) | `kickoff_drafted`, `cancelled`, `superseded` |
| `kickoff_drafted` | A kickoff prompt has been drafted (a work_ticket record exists with this conversation as its consumer) but upstream dependencies prevent the conversation from being opened against it. Typical case: a predecessor conversation has not yet reached `complete`. | `planned` | `ready`, `cancelled`, `superseded` |
| `ready` | The kickoff prompt is drafted and all upstream dependencies are satisfied; the conversation can be opened in Claude.ai immediately. | `kickoff_drafted` | `in_flight`, `cancelled`, `superseded` |
| `in_flight` | The conversation is currently open in Claude.ai; dialogue with Doug is in progress. | `ready` | `complete`, `cancelled`, `superseded` |
| `complete` | The conversation has closed with a session record and any artifacts committed. Terminal. Requires an outgoing `conversation_records_session` edge per section 3.4.3. | `in_flight` | (none — terminal) |
| `cancelled` | The conversation was stopped without satisfying its scope, and no successor conversation carries the work forward. Terminal. Reachable from any non-terminal state. | `planned`, `kickoff_drafted`, `ready`, `in_flight` | (none — terminal) |
| `superseded` | The conversation was stopped without satisfying its scope, but a successor conversation carries the work forward. Terminal. Requires an outgoing `supersedes` edge to the successor conversation per section 3.4.4. Reachable from any non-terminal state. | `planned`, `kickoff_drafted`, `ready`, `in_flight` | (none — terminal) |

The default starter status is `planned`.

#### 3.4.2 Transition semantics

The status lifecycle is a **forward-only workflow timeline with three truly terminal terminal states**, identical posture to workstream's per the inherited precedent. The four non-terminal states form a strict line (`planned` → `kickoff_drafted` → `ready` → `in_flight`); none of them admits a regressive transition. Each terminal state admits no outgoing transitions; reactivation of a terminal conversation is not supported. A conversation that needs to resume after reaching a terminal state is modelled as a new conversation record, typically created with status `planned` and (in the resumption case) an inbound reference from the prior conversation via the `supersedes` kind.

Three corollaries of the forward-only posture, parallel to workstream's:

- **No regression through the planning lifecycle.** A conversation that reaches `kickoff_drafted` cannot return to `planned` even if the kickoff is withdrawn; the appropriate response is to cancel the conversation and create a new one. A conversation that reaches `ready` cannot return to `kickoff_drafted` even if a new upstream dependency surfaces; the appropriate response is to cancel and re-plan, or to delay the conversation's actual opening (the `ready` status reflects readiness at the time of transition, not perpetual readiness).
- **No regression from terminal.** `complete`, `cancelled`, and `superseded` cannot regress to any non-terminal state. A conversation whose scope shifts after completion is a new conversation, not an edit of the prior record.
- **No movement between terminal states.** A `cancelled` conversation cannot be reclassified as `superseded` even if a successor conversation emerges later. The supersession relationship is modelled by the inbound reference from the successor; the source's status remains its original terminal value.

Server-side validation rejects invalid transitions with HTTP 422 and body `{"error": "invalid_status_transition", "from": <current>, "to": <requested>}`. The access-layer enforcement table mirrors the predecessor-successor map above.

#### 3.4.3 Complete-requires-session-edge rule

Setting `conversation_status` to `complete` requires the record to have an outgoing reference edge of kind `conversation_records_session` to a session record. The access layer enforces this as a single combined validation, identical to workstream's supersession-requires-edge pattern:

- POST creating a record with `status = 'complete'` and no `conversation_records_session` edge: HTTP 422 `{"error": "complete_conversation_requires_session_edge"}`.
- PUT or PATCH transitioning an existing record to `status = 'complete'` without an outgoing `conversation_records_session` edge present: same 422.
- The edge may be added in the same request body (the create or update payload may include a `references` array; the access layer evaluates the status transition and the edge state together at commit time).
- DELETE on the `conversation_records_session` edge while the source record still has `status = 'complete'`: HTTP 422 `{"error": "complete_conversation_requires_session_edge"}`. The status must be changed first (e.g., via supersession with a new conversation) or the source conversation must be soft-deleted.

#### 3.4.4 Supersession-requires-edge rule

Setting `conversation_status` to `superseded` requires the record to have an outgoing reference edge of kind `supersedes` to another conversation record. Validation pattern identical to workstream's supersession-requires-edge rule and parallel to section 3.4.3:

- POST or PATCH setting `status = 'superseded'` without an outgoing `supersedes` edge: HTTP 422 `{"error": "supersession_requires_successor_edge"}`.
- The edge may be supplied in the same request body.
- DELETE on the `supersedes` edge while the source record still has `status = 'superseded'`: HTTP 422 `{"error": "superseded_conversation_requires_supersedes_edge"}`.

#### 3.4.5 Soft-delete semantics

Default V2 base behavior. `conversation_deleted_at` set on DELETE; soft-deleted records do not appear in `GET /conversations` by default; `?include_deleted=true` reveals them; POST `/restore` clears `conversation_deleted_at` and restores them to the active list. Soft-delete is administrative (the record is removed from the active view) and is distinct from `cancelled` status (which is a lifecycle outcome). A record that is both `cancelled` and soft-deleted is a cancelled conversation whose record was also administratively removed; restore puts it back with status still `cancelled`.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/conversations` | — | List active conversations; `?include_deleted=true` shows soft-deleted; `?workstream_identifier=WS-NNN` filters by workstream membership; `?status=<value>` filters by status. |
| GET | `/conversations/{identifier}` | — | Single fetch by identifier. |
| POST | `/conversations` | full conversation JSON; identifier optional | Create. Identifier server-assigned when omitted. Default `conversation_status` is `planned` if omitted. The mandatory `conversation_belongs_to_workstream` edge may be supplied in a `references` array in the same body; validation requires it before commit. |
| PUT | `/conversations/{identifier}` | full conversation JSON | Full replace. Status-transition validation per section 3.4. Lifecycle timestamps server-set on the matching transition; client-supplied values for those columns are ignored except in the documented backfill-on-create case. |
| PATCH | `/conversations/{identifier}` | partial conversation JSON | Partial update. Same validation as PUT for any field touched. |
| DELETE | `/conversations/{identifier}` | — | Soft-delete; sets `conversation_deleted_at`. |
| POST | `/conversations/{identifier}/restore` | — | Clears `conversation_deleted_at`. 422 if not currently soft-deleted. |
| GET | `/conversations/next-identifier` | — | Returns `{"next": "CONV-NNN"}` for the next available value. Used by clients computing the identifier client-side, e.g., the desktop New Conversation dialog. |

All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

**List-endpoint filters.** Two query-string filters (`workstream_identifier`, `status`) are added beyond the default `include_deleted` flag because conversations are queried operationally — "what conversations are queued up in workstream X?" and "what conversations are currently in_flight?" are routine consultant questions, materially friction-reducing if the API answers them directly rather than the client filtering an unfiltered list. The two filters compose (both may be applied in one request).

#### 3.5.2 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission. The helper endpoint `GET /conversations/next-identifier` exposes the same computation for clients that need the identifier before submitting (e.g., the desktop New Conversation dialog populating a read-only Identifier label).

### 3.6 User Interface Considerations

Default layout per spec guide section 3.6, with three additions documented below. Each follows naturally from this spec's lifecycle and relationship decisions and does not constitute architectural deviation.

#### 3.6.1 Sidebar

The Conversations panel goes in the Governance sidebar group, immediately after Workstreams in workstream order. Position within the new-six set is the build-planning conversation's call; the working assumption is the six new entities sit at the end of the existing Governance group in workstream order (workstream first, then conversation, reference book, work ticket, close-out payload, deposit event).

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with five columns — one more than workstream's four, with Workstream added because conversations are members of workstreams and consultants need workstream membership visible at a glance for filtering and triage.

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `conversation_identifier` | Identifier | narrow | Sortable; default sort. |
| `conversation_title` | Title | wide | Project-language title. |
| `workstream_identifier` (derived via `conversation_belongs_to_workstream` edge) | Workstream | narrow-medium | Workstream identifier of the membership edge's target. Shown as a link to the parent workstream's detail pane. |
| `conversation_status` | Status | narrow | Enum value rendered as-is. |
| `conversation_updated_at` | Updated | narrow | Localized date/time. |

Default sort: identifier ascending. Filter controls in the panel toolbar: a workstream selector (filters by `?workstream_identifier=`) and a status selector (filters by `?status=`). The filter combo defaults to "all" on both. Right-click context menu offers New / Edit / Delete / Restore, consistent with the user-interface version 0.3 governance-entity panels per DEC-035 and DEC-036.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `conversation_identifier` — read-only label.
2. `conversation_title` — single-line text editor.
3. `conversation_purpose` — single-line text editor with placeholder "One sentence".
4. `conversation_description` — multi-line text editor with placeholder "Paragraph describing the conversation".
5. `conversation_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default. The collapsed default reinforces that the field is internal consultant scratchpad.
6. `conversation_status` — combo box with the seven enum values; the combo's selectable subset at any moment is the union of `{current_status}` and the valid successors of the current status per section 3.4.1, so the user cannot select an invalid transition. Server-side validation is the final gate; the combo's filtering is a UX convenience.
7. **Lifecycle timestamps section** — read-only labels rendered only for the timestamps that are non-null. A `planned` conversation sees no lifecycle timestamps. A `kickoff_drafted` conversation sees Kickoff drafted. A `ready` conversation sees Kickoff drafted, Ready. An `in_flight` conversation sees Kickoff drafted, Ready, Started. A `complete` conversation sees the four progress timestamps plus Completed. A `cancelled` conversation sees whatever progress timestamps it accumulated before cancellation, plus Cancelled. A `superseded` conversation similarly shows accumulated progress plus Superseded. The conditional rendering mirrors the underlying nullable columns and keeps the detail pane clean.
8. `ReferencesSection` widget — renders the outbound workstream-membership edge (`conversation_belongs_to_workstream`) prominently at top, then outbound kickoff-linkage edge (`conversation_opens_against_work_ticket`) when present, outbound session-linkage edge (`conversation_records_session`) when present, outbound predecessor edges (`conversation_succeeds_conversation`) when present, outbound supersession edge (`supersedes`) when present, and inbound edges (other conversations that succeed this one; the kickoff's inbound edge from work_ticket; the close-out-payload's inbound edge; the deposit-event's inbound edge once those specs ship). The "Add reference" affordance from the user-interface version 0.3 references-create dialog filters available kinds and target entity types by the strict vocab per `_kinds_for_pair`.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `conversation_identifier` not shown in create mode (server-assigned).
- `conversation_status` defaults to `planned`; the user may select a different starter value for backfill of historical records — for example, when creating a conversation record for a conversation that completed before this entity type existed, the user can set status directly to `complete` and the create endpoint accepts the matching lifecycle timestamps as user-supplied for the backfill case. Backfill behavior is access-layer-detected by the absence of intermediate transitions and is documented as part of section 3.8 (Open questions — retroactive backfill).
- **Workstream selector** — required in create mode. A combo box populated by `GET /workstreams` lets the user pick the parent workstream. The dialog binds the selection to a `conversation_belongs_to_workstream` edge in the create payload's `references` array. Submitting without selecting a workstream is blocked client-side; the server-side validation is the final gate.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, complete-requires-session-edge, supersession-requires-edge, missing-workstream-edge) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `conversation_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; the combo box restricts selectable values to valid transitions plus the current value (no-op). Setting status to `complete` requires an outgoing `conversation_records_session` edge to be present (added via the ReferencesSection's "Add reference" affordance before the status change is committed, or via the same patch payload); attempting to commit `complete` without the edge surfaces the 422 inline. Setting status to `superseded` requires an outgoing `supersedes` edge analogously.

The workstream-membership edge is editable from the ReferencesSection but the conversation cannot be saved without it; removing the edge in the dialog requires adding a replacement edge in the same operation.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `conversation_identifier` value (e.g., `CONV-008`) to enable the Delete button, matching the user-interface version 0.3 governance-entity patterns. Confirmation soft-deletes the record. Deletion of a `complete` conversation does not invalidate its session record (sessions remain append-only); the soft-deleted conversation simply disappears from the active view.

### 3.7 Acceptance Criteria

The following eighteen statements define what "this entity type is correctly implemented in the eventual build" looks like. Each is concrete and testable; the build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `conversations` table with all fifteen columns (`conversation_identifier`, `conversation_title`, `conversation_status`, `conversation_purpose`, `conversation_description`, `conversation_notes`, `conversation_created_at`, `conversation_updated_at`, `conversation_deleted_at`, `conversation_kickoff_drafted_at`, `conversation_ready_at`, `conversation_started_at`, `conversation_completed_at`, `conversation_cancelled_at`, `conversation_superseded_at`), correct types and constraints, and runs both forward and backward without error.

2. **`conversation_identifier` format constraint enforced.** Insertions with `conversation_identifier` not matching `^CONV-\d{3}$` raise a validation error at the access layer.

3. **`conversation_title` uniqueness enforced case-insensitively.** Inserting a second row whose `conversation_title` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`conversation_status` enum and transition validation.** Insertions with `conversation_status` outside the seven-value enum are rejected. PATCH or PUT requesting an invalid transition (e.g., `ready` → `planned`, `complete` → `in_flight`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Terminal states are truly terminal.** All three terminal statuses (`complete`, `cancelled`, `superseded`) reject every outgoing transition, including transitions between terminal states (e.g., `cancelled` → `superseded`). Same 422 shape.

6. **Forward-only planning lifecycle.** The four non-terminal states (`planned`, `kickoff_drafted`, `ready`, `in_flight`) reject all regressive transitions (e.g., `kickoff_drafted` → `planned`, `ready` → `kickoff_drafted`, `in_flight` → `ready`). Same 422 shape.

7. **Workstream-membership-required rule.** POST creating a record without a `conversation_belongs_to_workstream` edge in the request body's `references` array returns HTTP 422 `{"error": "missing_workstream_membership_edge"}`. PATCH or PUT removing the membership edge from an existing record without replacing it returns the parallel 422.

8. **Complete-requires-session-edge rule.** POST or PATCH setting `conversation_status = 'complete'` without an outgoing `conversation_records_session` edge to a session record returns HTTP 422 `{"error": "complete_conversation_requires_session_edge"}`. The edge may be supplied in the same request body. Deletion of the edge on a `complete` conversation returns the parallel 422.

9. **Supersession-requires-edge rule.** POST or PATCH setting `conversation_status = 'superseded'` without an outgoing `supersedes` edge to another conversation record returns HTTP 422 `{"error": "supersession_requires_successor_edge"}`. The edge may be supplied in the same request body. Deletion of the edge on a `superseded` conversation returns the parallel 422.

10. **Lifecycle timestamps server-set on transition.** `conversation_kickoff_drafted_at` is set when status transitions to `kickoff_drafted`; `conversation_ready_at` when to `ready`; `conversation_started_at` when to `in_flight`; `conversation_completed_at` when to `complete`; `conversation_cancelled_at` when to `cancelled`; `conversation_superseded_at` when to `superseded`. Each is idempotent — a second update setting the same status does not change the timestamp. The three terminal timestamps are mutually exclusive at the terminal level (exactly one is non-null on a terminal record). Client-supplied values for these columns are ignored on PUT and PATCH except in the documented backfill case (create with terminal status accepts user-supplied terminal timestamp).

11. **Access-layer methods exist with expected signatures.** `client.list_conversations()`, `client.get_conversation(identifier)`, `client.create_conversation(...)`, `client.update_conversation(identifier, ...)`, `client.patch_conversation(identifier, ...)`, `client.delete_conversation(identifier)`, `client.restore_conversation(identifier)`, `client.next_conversation_identifier()` exist and pass unit tests covering happy path and at least one error case each.

12. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the V2 `{data, meta, errors}` envelope per `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`. List-endpoint filters (`workstream_identifier`, `status`) work both independently and composed.

13. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /conversations/next-identifier` returns `{"next": "CONV-NNN"}` for the next available number. POST with `conversation_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

14. **Soft-delete and restore round-trip correctly.** DELETE sets `conversation_deleted_at`; the record disappears from `GET /conversations`. `GET /conversations?include_deleted=true` shows it. POST `/restore` clears `conversation_deleted_at`; the record reappears. Restore on a record that is not soft-deleted returns 422.

15. **Vocabulary additions registered.** `REFERENCE_RELATIONSHIPS` includes `conversation_belongs_to_workstream`, `conversation_records_session`, `conversation_opens_against_work_ticket`, and `conversation_succeeds_conversation`; `ENTITY_TYPES` includes `conversation` and `work_ticket` (alongside the `workstream`, `reference_book`, and pre-existing types); `_kinds_for_pair` returns the correct kind sets for the four new pairs; the matching Alembic migration on `refs.relationship_kind`'s CHECK constraint passes. The `work_ticket` entity type is admitted here for vocabulary registration; its own table lands with the work_ticket schema-design conversation's resulting build slice. The cardinality rule "at most one outgoing edge of kind X per conversation" is enforced at the access layer for `conversation_records_session` and `conversation_opens_against_work_ticket`; "exactly one outgoing edge" for `conversation_belongs_to_workstream`; no cardinality cap for `conversation_succeeds_conversation`.

16. **`Conversations` sidebar entry appears in the Governance group.** Position within the new-six set is whatever the build-planning conversation chooses; the entry exists, the panel opens, the panel is bound to the access-layer methods.

17. **Master pane columns, filters, and default sort.** The Conversations panel shows columns Identifier / Title / Workstream / Status / Updated, sorted by Identifier ascending. Workstream selector and status selector in the panel toolbar filter the list by the corresponding query-string parameters. Right-click context menu offers New / Edit / Delete / Restore. Detail pane renders all fields in section-3.2 order, including the conditional lifecycle-timestamps section and the ReferencesSection widget with all relationship kinds correctly grouped by direction.

18. **End-to-end backfill of this conversation's record.** A consultant can author a `conversation` record for this conversation (the conversation schema-design conversation) through the New Conversation dialog with status `complete`, all six lifecycle timestamps backfilled to plausible historical values, the mandatory `conversation_belongs_to_workstream` edge pointing at the governance workstream's record, the `conversation_opens_against_work_ticket` edge pointing at the work_ticket record for `schema-design-kickoff-conversation.md`, the `conversation_records_session` edge pointing at SES-049, and the `conversation_succeeds_conversation` edge pointing at the workstream conversation's record. The conversation record persists across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For the build-planning conversation to settle

**[build] Sidebar grouping for the six new governance entities.** Inherited from workstream.md section 3.8.1. The existing Governance group has eight entries; adding six more makes the group thirteen entries deep. Build-planning decides whether to introduce a sub-grouping (e.g., "Governance — workflow" for the six new ones) or accept the longer list as-is. This spec declares default position; build-planning may overrule.

**[build] Migration ordering across the six schemas.** Inherited from workstream.md section 3.8.1. Each governance schema requires its own Alembic migration creating the entity table; the references-vocab additions are consolidated into one migration across the six specs. Sequencing those migrations safely is build-planning's call.

**[build] Tentative kind name `conversation_opens_against_work_ticket`.** This kind name was settled in this conversation as the kickoff-prompt linkage. The work_ticket schema-design conversation (fourth in the workstream) may have cause to refine the verb tense or the source-target framing (for example, if work_ticket ends up with a uniform "consumed-by" verb pattern across multiple inbound kinds, this kind might shift to `conversation_consumes_work_ticket` for symmetry). Build-planning reconciles any drift between the two specs.

**[build] Tentative kind names on the inbound side.** Section 3.3.2 lists three tentative kind names for inbound edges from work_ticket, close_out_payload, and deposit_event. Those names are placeholders for cross-spec consistency checking; the actual kind names are the source-side specs' calls. Build-planning aggregates whatever the source-side specs land on.

**[build] Backfill behavior on create with terminal status.** Inherited from workstream.md section 3.8.1. This spec admits the backfill-create case; the detailed validation behavior (whether full progression timestamps must be supplied for a `complete` backfill, whether terminal-timestamp ordering is enforced, whether the case requires a special flag) is left to build-planning. Conversation's case is richer than workstream's because the planning lifecycle has more states; a `complete` backfill plausibly supplies five non-null timestamps (`_kickoff_drafted_at`, `_ready_at`, `_started_at`, `_completed_at`, plus `_created_at`) and the build-planning conversation decides which combinations the create endpoint requires.

**[build] Cycle prevention in `conversation_succeeds_conversation`.** The DAG nature of the chaining kind needs cycle-prevention enforcement at the access layer (no conversation may transitively succeed itself). Build-planning specifies the cycle-check mechanism (insert-time DFS, periodic batch check, or graph-database-style closure table) and the error-response shape (HTTP 422 `{"error": "circular_conversation_succession"}` is the working assumption).

#### 3.8.2 For retroactive backfill (PI-022) to surface

**[backfill] Historical lifecycle timestamps for prior conversations.** Roughly 50 session records exist at this writing, implying 50 prior conversations to backfill. The retroactive records require historical lifecycle timestamps; the backfill pass decides which dates to use (kickoff-prompt commit dates for `_kickoff_drafted_at`, session-record dates for `_completed_at`, in_flight_at_end text in the prior session record for indirect `_started_at` evidence) and resolves ambiguity case-by-case. Most prior conversations lack clean `_ready_at` and `_in_flight_started_at` evidence; PI-022's resolution determines whether those columns remain null for backfilled records or are populated with best-effort approximations.

**[backfill] Status assignment for prior conversations.** Most are `complete`. SES-046's conversation has an unusual lifecycle (ad-hoc opening, no formal kickoff, conducted across multiple sessions over weeks per the session record) — PI-022's call whether its backfilled record's status is `complete` with backfilled timestamps or whether the ad-hoc shape warrants a different posture. The schema admits standard backfill; the ad-hoc case is a policy decision for the backfill pass.

**[backfill] Predecessor-successor edges from in_flight_at_end text.** PI-022's backfill pass reconstructs `conversation_succeeds_conversation` edges from the in_flight_at_end fields of session records, where the next conversation is named in plain text. Most reconstructions are unambiguous (sequential workstreams have explicit "Next workstream conversation: X" language); some are not (workstreams with parallel successors, or session records whose in_flight_at_end did not name the next conversation explicitly). The backfill pass's policy for ambiguous cases is PI-022's call.

**[backfill] Kickoff prompt to work_ticket edges.** PI-022's backfill pass also reconstructs `conversation_opens_against_work_ticket` edges from the seed prompts and topics_covered fields of session records, where the kickoff prompt's path is named in plain text. The matching to work_ticket records depends on the work_ticket schema-design conversation's decisions about how kickoff prompt files map to work_ticket records (one-to-one, or one work_ticket per file, with versioning if a kickoff was amended). Resolution sits in PI-022 plus the work_ticket conversation.

**[backfill] Mandatory-workstream-membership for ad-hoc conversations.** The strategic scoping conversation (SES-046) had no formal workstream; the backfill record needs a workstream parent because the schema's access layer requires one. PI-022 decides whether such conversations are backfilled with an ad-hoc workstream record ("Governance gap identification" or similar) or simply not backfilled because they predate the entity types.

#### 3.8.3 For a future release

**[future] Estimated duration field.** Not introduced in this release. Conversations vary widely in duration (some close in an hour, some span days across multiple sessions). If a real query need surfaces (consultants planning capacity), a future release adds `conversation_estimated_duration` and `conversation_actual_duration` columns; the schema admits them additively.

**[future] Priority field.** Not introduced. Workstream sequencing answers most prioritization questions; parallel conversations within a workstream are rare. If a real query need surfaces, a future release adds `conversation_priority` as an enum.

**[future] Conversation kind/type field.** Not introduced. Conversation type (schema-design, build-planning, build-execution, planning, ad-hoc, retrospective) is currently captured in title and description; if querying by kind becomes routine, a future release adds `conversation_kind` as an enum with the matching vocab. The minimum-viable posture keeps the schema kind-agnostic.

**[future] Outcome summary field.** Parallel to workstream's deferred outcome field per workstream.md section 3.8.3. The session record's `topics_covered` and `in_flight_at_end` carry the outcome narrative; `conversation_status` carries the binary outcome. If a real query need surfaces ("show me the outcome summaries for all complete conversations in workstream X"), a future release adds the column.

**[future] Pause / resume / hold lifecycle states.** Parallel to workstream's deferred pause/resume question per workstream.md section 3.8.3. Conversation's lifecycle is forward-only with truly terminal terminals. If real operational signal supports a pause-and-resume case (a conversation that is intentionally on hold but not cancelled — for example, an in-flight conversation that has been paused for a few days awaiting external input), a future release may admit a `paused` status with transitions back to `in_flight`. The minimum-viable posture preserves the timeline semantics by treating pauses as a free-text concern.

**[future] Cross-workstream conversation linkage beyond generic `references`/`is_about`.** Conversations sometimes reference work done in conversations of other workstreams (for example, the build-planning conversation of the methodology workstream is structurally relevant to the build-planning conversation of the governance workstream). Today this is captured via the generic `references` kind; a future release may introduce a typed cross-workstream-reference kind (`conversation_consults_conversation`?) if querying by this relationship becomes routine. The minimum-viable posture defers.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_049.json` at conversation close. Each is linked to SES-049 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-129 through DEC-134) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-129 — `conversation` identifier prefix and format.** Adopts `CONV` as the prefix; affirms four-letter form aligns with `PROC` and `CRMC` precedents.
- **DEC-130 — `conversation`-to-session relationship via references-table edge, with new relationship kind `conversation_records_session`.** Resolves the kickoff prompt's drift toward an FK column on the sessions table in favour of the cross-spec precedent locked by SES-048. No modification to the append-only sessions table.
- **DEC-131 — `conversation` lifecycle: seven statuses with truly terminal terminals, forward-only planning lifecycle, complete-requires-session-edge rule, supersession-requires-edge rule.** Adopts the seven-status set from DEC-119 in full (no collapsing of `kickoff_drafted`/`ready`). Inherits truly-terminal posture and supersession-requires-edge from workstream's precedent; adds the parallel complete-requires-session-edge rule realising the conversation→session linkage from Decision 1.
- **DEC-132 — `conversation`-to-kickoff (work_ticket) relationship via references-table edge, with tentative new kind `conversation_opens_against_work_ticket`.** Required-when rule binds the edge to statuses past `kickoff_drafted`; the work_ticket schema-design conversation may refine the kind name; build-planning reconciles.
- **DEC-133 — `conversation_succeeds_conversation` introduced for predecessor-successor chaining within a workstream.** Diverges from workstream's defer-sequencing posture on the strength of conversation-sequencing frequency. Establishes cross-spec precedent that typed sequencing edges are introduced when entity-family frequency justifies.
- **DEC-134 — `conversation` field inventory, list-endpoint filters, master-pane Workstream column, soft-delete posture, and acceptance criteria.** Captures the six-field-plus-nine-timestamp shape (identity, content, classification, no FK fields, base plus six per-status lifecycle timestamps), `workstream_identifier`/`status` list-endpoint filters, Workstream column as the fifth master-pane column, default soft-delete with restore, eighteen acceptance criteria.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the next four schema-design conversations.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — settled referent for the workstream membership relationship and source of the three inherited cross-spec precedents.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `conversation` records live in the per-engagement database.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary the new entity type and relationship kinds register against.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — methodology workstream's first schema spec, structurally parallel for cadence reference.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. `conversation` is not one of the three file-tracking families; it is the conversational-work-unit organizing complement.
- **DEC-118** — Two entities within the deposit bucket family. Not directly extended; the conversation→close_out_payload and conversation→deposit_event relationships are designed inbound from those specs.
- **DEC-119** — Add a conversation entity. **Most directly extended.** This spec is the realization of DEC-119, including the explicit confirmation of the seven-state lifecycle and the resolution of the kickoff's drift on the conversation→session relationship.
- **DEC-120** — Add a workstream entity. The `conversation_belongs_to_workstream` kind is registered here per workstream.md's deferral and realizes DEC-120's binding text on workstream membership.
- **DEC-121** — Single-source-of-truth coverage extension. The conversation entity makes the conversational-work-unit concept machine-resolvable; the references-edge over FK choice for the conversation→session relationship also serves DEC-121's principle directly (an FK-on-sessions modelling would have been a partial coverage extension; a references-edge is fully consistent with the database's existing relationship-graph posture).
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. **Directly informs Decision 1's resolution.** The append-only sessions table is the most delicate table in the governance system; the references-edge choice for conversation→session means the table is not modified at all, preserving its append-only posture without any backfill-column complication.
- **DEC-014** — Sessions are written exclusively by Claude at conversation close. Informs the session-record-at-close pattern this conversation also follows.
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.9.1's reliance on the close-out payload's apply script and the session record as the durable artifacts of this conversation. Also informs section 3.8.2's backfill posture — the descriptive text in `session.conversation_reference` is the reconstruction key for matching historical sessions to their conversation parents.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3, including the multi-kind, multi-direction grouping the conversation entity requires (more kinds than any prior governance entity).
- **DEC-033** — Cascading reference create dialog driven by strict vocab. The conversation entity's four new outgoing kinds plus the reused `supersedes` plus the generic `is_about`/`references` defaults all flow through the existing dialog without modification.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master pane patterns in section 3.6.2 including the addition of the Workstream column and the toolbar filter combos.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields prefixed `conversation_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited and applied to all four new kinds.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `conversation` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.
- **DEC-123 through DEC-128** — All six decisions from SES-048 (the workstream schema-design conversation). DEC-123 affirms the four-letter `CONV` prefix is within the spec guide's range without requiring justification. DEC-124's references-edge cross-spec precedent is the precedent this conversation's Decision 1 follows. DEC-125's truly-terminal and supersession-requires-edge patterns are inherited verbatim. DEC-126's per-status lifecycle timestamps pattern is extended from four columns (workstream) to six (conversation). DEC-127's flat-catalog posture is structurally analogous to this spec's no-hierarchy posture (sections 3.3.3 and 3.8.3). DEC-128's standard-defaults posture is what this spec uses for API surface, UI layout, soft-delete, and acceptance-criteria framing.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-048 — workstream schema-design conversation. First per-entity schema-design conversation in the governance entity schema-design workstream. Locked the three cross-spec precedents this conversation inherits and named `conversation_belongs_to_workstream` as the membership kind that this conversation registers.
- **Successor:** `reference_book` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-reference-book.md`. Inherits the four cross-spec precedents now in force: the three from workstream (references-edge over FK, per-status lifecycle timestamps, terminal-states-are-terminal) plus the one new precedent from this conversation (typed sequencing introduced when entity-family frequency justifies). The reference_book entity is structurally most directly related to this spec through the master-plan linkage kind already declared in workstream.md (`workstream_planned_in_reference_book`); the conversation entity's relationship to reference_book is via the generic `references`/`is_about` kinds, not a typed kind, in this release.

---

*End of document.*
