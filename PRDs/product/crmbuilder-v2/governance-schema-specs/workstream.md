# Governance Entity Schema Spec — `workstream`

**Last Updated:** 05-20-26 23:30
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** First of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-047 (workstream-establishing planning conversation)
**Successor conversation:** `conversation` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-20-26 23:30 | Doug Bower / Claude | Initial draft. Produced by the first schema-design conversation in the governance-entity schema-design workstream. Establishes the `workstream` entity type for V2 storage, settles the deferred-from-DEC-120 nested-workstream question (no nesting in this release), confirms the references-table-edge mechanism for parent-child governance relationships per DEC-120's decision text, and locks the cross-spec consistency precedents the remaining five schemas inherit: `WS` identifier prefix posture (two-letter form acceptable, falling within the spec guide's 2–5 letter range), per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal transition discipline, references-edge-over-FK for parent-child relationships across the governance entity family. |

---

## Change Log

**Version 1.0 (05-20-26 23:30):** Initial creation. Defines `workstream` as the V2 governance entity type that hosts coherent lines of related conversations under minimum-viable scope. Establishes nine fields (`workstream_identifier`, `workstream_name`, `workstream_purpose`, `workstream_description`, `workstream_notes`, `workstream_status`, plus four lifecycle timestamps `workstream_started_at`, `workstream_completed_at`, `workstream_cancelled_at`, `workstream_superseded_at` in addition to the three inherited base timestamps), a five-status lifecycle (`planned` → `in_flight` → `complete` / `cancelled` / `superseded`) with truly terminal terminal states and an access-layer rule requiring an outgoing `supersedes` edge whenever status is `superseded`, no outgoing foreign-key columns (the parent-child relationship to conversations lives in `refs` per DEC-120), a master-plan reference-book linkage modelled as a references-edge with the new relationship kind `workstream_planned_in_reference_book`, and standard endpoint set with server-side status-transition validation and identifier auto-assignment. Establishes references-edge over foreign-key for all parent-child governance relationships as a cross-spec precedent; establishes per-status lifecycle timestamps for workflow-shaped lifecycles as a divergence from the methodology entities' propose-verify pattern. Nested workstreams deferred entirely — flat catalog in this release, retrofit path noted as a references-edge addition rather than a self-FK column. Six decisions and five planning items (none — see section 3.8) authored at conversation close; sixteen acceptance criteria captured.

---

## 1. Purpose and Position

This document specifies the `workstream` entity type for V2's storage layer. It is the **first of six** schema specs produced by the governance-entity schema-design workstream — the workstream that closes the gap between the V2 governance database's stated single-source-of-truth role and its actual coverage of the planning-and-execution machinery itself.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, then `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event` — feeding a seventh build-planning conversation that integrates them into a coherent release.

`workstream` is the first spec because it is the most independent — nothing else in the new set references it without going through `conversation` first. Designing it first lets every downstream schema treat workstream as a settled referent.

`workstream`'s primary scope in this release is to host the organizing-unit concept the project has been using as an English word and a Markdown filename pattern for its entire history. A workstream record names a coherent line of related conversations — typically 5 to 15 conversations over a few days to a few weeks — captures the workstream's lifecycle through planned, in-flight, and one of three terminal outcomes, and serves as the inbound reference target for conversations declaring their membership and for reference books declaring themselves to be a workstream's master plan. The schema is intentionally minimum-viable. Outcome narratives, target-version fields, predecessor-successor chains between workstreams, and nested-workstream hierarchies are deliberately out of scope; each is deferred to a future release pending real-use signal.

This conversation also **locks three cross-spec consistency precedents** that the next five schema-design conversations inherit unless they have specific cause to deviate:

- **References-edge over foreign-key for parent-child governance relationships.** The workstream-to-conversation relationship lives in `refs` (per DEC-120), not as a `workstream_id` column on conversation. The five downstream specs inherit this posture for analogous parent-child relationships (close_out_payload to conversation, work_ticket to conversation, deposit_event to close_out_payload, and so on).
- **Per-status lifecycle timestamps for workflow-shaped lifecycles.** Workstream's lifecycle is a workflow timeline rather than a propose-verify state machine; the schema carries one timestamp column per non-starter status. The methodology entities, whose lifecycles are propose-verify, carry only base timestamps. Other timeline-shaped governance entities (conversation in particular, with its seven-state lifecycle per DEC-119) inherit the per-status pattern by default.
- **Terminal-states-are-terminal discipline.** Once a workstream reaches `complete`, `cancelled`, or `superseded`, it admits no further status transitions; reactivation is modelled as a new workstream that supersedes the prior. Downstream entities with terminal states adopt the same discipline.

These precedents are documented in each remaining schema-design conversation's read-first list. Deviation from any of them in a downstream spec is acceptable with rationale; the cross-spec consistency check before the build-planning conversation opens validates that intentional deviations are documented as such.

---

## 2. Summary

A `workstream` record in V2 represents one coherent line of related conversations — an organizing unit of work with its own purpose, scope, and lifecycle. Real examples already implicit in the project's history include the methodology entity schema-design workstream (five schema-design conversations plus a build-planning conversation), the user-interface version 0.5 engagement-management workstream, the user-interface version 0.6 styling workstream, the multi-tenancy routing fix workstream, the Cleveland Business Mentors paper test workstream, and this governance entity schema-design workstream. Each is structurally a sequence of related conversations that produce a coherent body of work and reach a defined end-state — but before this entity type lands, each exists only as an English word in document text and a Markdown filename pattern. The `workstream` entity makes them queryable.

The schema in this release is the thinnest shape that captures the organizing-unit concept faithfully: a human-readable name, a one-sentence purpose, a paragraph description, an optional consultant notes field, a five-status lifecycle with timestamps for each non-starter transition, and references-edge linkages to (a) the conversations that belong to the workstream and (b) the reference book that documents the workstream's master plan when one exists. The schema deliberately omits outcome summaries, target-version fields, nested-workstream hierarchies, and predecessor-successor chains between workstreams — each grows additively in a later release if real-use signal supports it.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `workstream` |
| Display name (singular) | Workstream |
| Display name (plural) | Workstreams |
| Identifier prefix | `WS` |
| Identifier format | `WS-NNN`, zero-padded to 3 digits (e.g., `WS-001`, `WS-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /workstreams/next-identifier` |

**Identifier-prefix posture.** `WS` is two letters, deliberately the shortest serviceable form. The spec guide section 6 allows 2 to 5 letters. The two-letter form matches the existing `PI` prefix; the three-letter form is the more common existing pattern (`DEC`, `SES`, `RSK`, `TOP`, `REF`, `CHR`, `STA`, `DOM`, `ENT`); the four-letter form appears in `PROC` and `CRMC`. This spec affirms the two-letter form as acceptable without locking it as a strict requirement; downstream conversations may adopt three or four letters where the two-letter form would collide or read ambiguously. The remaining five governance entities' working prefixes (`CONV`, `RB`, `WT`, `COP`, `DEP`) span a mix of two-to-four letters; each downstream conversation makes its own call.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `workstream_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `workstream_identifier` | TEXT | yes | server-assigned | `^WS-\d{3}$`, unique | The workstream identifier in `WS-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /workstreams/next-identifier` returns the next available value. |
| `workstream_name` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Workstream name in the project's working language (e.g., "Methodology entity schema design", "Governance entity schema design", "User-interface version 0.5 engagement management"). |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `workstream_purpose` | TEXT | yes | — | non-empty trimmed | One-sentence statement of what the workstream produces and why it exists. Mirrors `domain_purpose`'s role in the methodology workstream — the priority-test artifact at workstream granularity. Plain text in this release. |
| `workstream_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing the scope and shape of the work — what conversations are anticipated, what artifacts are expected, what end-state defines completion. Plain text in this release. |
| `workstream_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the workstream's user-facing summary. Used to capture mid-workstream reasoning, scope adjustments, points worth surfacing in the workstream's close-out. Plain text in this release; structured-journal pattern deferred to signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `workstream_status` | TEXT | yes | `planned` | enum: `planned` \| `in_flight` \| `complete` \| `cancelled` \| `superseded`; valid transitions per section 3.4; additional rule for `superseded` per section 3.4.3 | Lifecycle status. See section 3.4 for the full state machine. |

#### 3.2.4 Relationship fields

None. The parent-child relationship from conversations to their workstream lives in the universal references table per Decision 1 (this conversation) and DEC-120. The master-plan linkage to a reference book and the supersession linkage to a successor workstream also live in `refs`. No foreign-key columns on the workstream table.

#### 3.2.5 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `workstream_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `workstream_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `workstream_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |
| `workstream_started_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `planned` → `in_flight` transition. Once set, not user-editable. Remains null on workstreams that move from `planned` directly to `cancelled` or `superseded` without ever entering `in_flight`. |
| `workstream_completed_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `in_flight` → `complete` transition. Once set, not user-editable. Mutually exclusive with `workstream_cancelled_at` and `workstream_superseded_at` — exactly one of the three terminal-state timestamps is populated. |
| `workstream_cancelled_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `cancelled` (from `planned` or `in_flight`). Once set, not user-editable. |
| `workstream_superseded_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `superseded` (from `planned` or `in_flight`). Once set, not user-editable. |

**No `workstream_planned_at` column.** A workstream's planned-at moment is always equal to its `workstream_created_at` (the default starter status is `planned`, set at insert time). A separate column would be redundant. The single exception — a backfilled record whose historical planning happened before its database insert — uses `workstream_created_at` with the backfill timestamp; the distinction is not tracked separately in this release.

**No storage-level length caps** on text fields, matching the methodology precedent. UI placeholder text provides soft guidance ("One sentence", "Paragraph describing the work"). Pathological-input handling deferred to real-use signal; length caps are an easy migration in a later release if needed.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

Two outgoing reference kinds in this release, both modelled as references-table edges per Decision 1's references-over-FK precedent and consistent with DEC-120's decision text.

**Master plan linkage.** A workstream may have a master plan documented in a reference book record. The relationship is optional (some workstreams, particularly smaller or ad-hoc ones, never have a written master plan). When the linkage exists, exactly one reference book record serves as the workstream's master plan.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `workstream_planned_in_reference_book` | `workstream` | `reference_book` | The reference book record contains the workstream's master plan document. Cardinality: a workstream has at most one master plan; a reference book may serve as the master plan for one or more workstreams (typically one). |

**Supersession linkage.** When a workstream's status is set to `superseded`, it must have an outgoing reference edge identifying the successor workstream that carries the work forward. The relationship uses the existing generic `supersedes` reference kind (already registered in `vocab.py`'s `REFERENCE_RELATIONSHIPS`, and already permitted for `(workstream, workstream)` once `workstream` is added to `ENTITY_TYPES` because `_kinds_for_pair`'s `source_type == target_type` rule admits `supersedes` for any same-type pair). No new kind is introduced for this relationship; the established vocabulary is reused.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `supersedes` (existing kind, reused) | `workstream` | `workstream` | This workstream was redirected; the target workstream carries forward the work. Required when source.status = `superseded`; access-layer enforces. |

No other outgoing reference kinds in this release. Predecessor-successor chains between non-superseding workstreams (e.g., "the governance workstream follows the methodology workstream") are not modelled in this release; if a real query need surfaces, a `workstream_succeeds_workstream` kind is one vocab.py line away in a future release.

#### 3.3.2 Inbound relationships (declared by source-side specs)

`workstream` is the target of inbound references from `conversation`, declared in `conversation.md` (the next schema-design conversation). The kind, mechanism, and cardinality:

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `conversation_belongs_to_workstream` | `conversation` | `workstream` | references-table edge | many-to-one (each conversation belongs to exactly one workstream; a workstream has many conversations) | A conversation is a member of its workstream. The access layer requires every conversation to have exactly one outgoing edge of this kind; missing edge or multiple edges return 422. |

This table is informational from `workstream.md`'s perspective. The `vocab.py` registration of `conversation_belongs_to_workstream` and the access-layer enforcement that every conversation has exactly one such edge belong to the `conversation.md` schema-design conversation. This spec lists the kind here because the cross-spec consistency check before build-planning relies on both specs naming the relationship.

#### 3.3.3 Hierarchy

Workstream does not use the self-referential parent-child hierarchy pattern in this release. Per Decision 3, no nesting: workstream records are siblings, not a tree. The kickoff prompt's concrete examples are all flat, and the project's operating history has zero observed instances of nested workstreams. If a future real-use signal demands nesting, the retrofit is additive: a new reference kind (provisional name `workstream_parent_of_workstream`) plus the access-layer rule "at most one parent edge per workstream" plus the user-interface tree rendering. The retrofit deliberately uses references-edge rather than a self-FK column so the workstream table is not retroactively modified.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are named here and aggregated by the build-planning conversation into one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `conversation_belongs_to_workstream` | Member-of relationship for inbound conversation references (declared inbound here; registered in `conversation.md` as outbound). |
| `REFERENCE_RELATIONSHIPS` | `workstream_planned_in_reference_book` | Outbound master-plan linkage to a reference book record. |
| `ENTITY_TYPES` | `workstream` | This entity type. |
| `ENTITY_TYPES` | `conversation` | Required because `conversation_belongs_to_workstream` names it as source; the conversation entity is designed in the next conversation. |
| `ENTITY_TYPES` | `reference_book` | Required because `workstream_planned_in_reference_book` names it as target; the reference_book entity is designed in the third conversation. |
| `_kinds_for_pair` | `if source_type == 'conversation' and target_type == 'workstream': kinds.add('conversation_belongs_to_workstream')` | Source-target constraint binding the new kind to the matching pair only. |
| `_kinds_for_pair` | `if source_type == 'workstream' and target_type == 'reference_book': kinds.add('workstream_planned_in_reference_book')` | Source-target constraint binding the master-plan kind to the matching pair only. |

The existing generic `supersedes` kind is reused for the `(workstream, workstream)` supersession edge; no addition required for that relationship. The `_kinds_for_pair` rule already admits `supersedes` for any same-type pair, so once `workstream` is in `ENTITY_TYPES`, the rule applies automatically.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `planned` | The workstream has been created but no conversations have opened against its scope yet. **Default starter status.** | (none — starter) | `in_flight`, `cancelled`, `superseded` |
| `in_flight` | At least one conversation has opened against the workstream's scope; the work is underway. | `planned` | `complete`, `cancelled`, `superseded` |
| `complete` | The workstream's scope has been satisfied. Terminal. | `in_flight` | (none — terminal) |
| `cancelled` | The workstream was stopped without satisfying its scope, and no successor workstream carries the work forward. Terminal. | `planned`, `in_flight` | (none — terminal) |
| `superseded` | The workstream was stopped without satisfying its scope, but a successor workstream carries the work forward. Requires an outgoing `supersedes` edge to the successor workstream. Terminal. | `planned`, `in_flight` | (none — terminal) |

#### 3.4.2 Transition semantics

The status lifecycle is a **forward-only workflow timeline with three truly terminal terminal states**. Each terminal state admits no outgoing transitions; reactivation of a terminal workstream is not supported. The rationale: a workstream is an organizing unit of work with a defined beginning, middle, and end, and "reopening" a finished workstream blurs the timeline semantics. A workstream that needs to resume after reaching a terminal state is modelled as a new workstream record — typically created with status `planned` and (in the resumption case) an inbound reference from prior conversations declaring continuity. Reactivation as a status transition is not a workflow this release supports.

Three corollaries of the truly-terminal posture:

- **`complete` cannot regress to `in_flight`.** A workstream's scope is either satisfied or it is not. If scope shifts after completion, the appropriate response is a new workstream — not editing the prior workstream's terminal status.
- **`cancelled` and `superseded` cannot regress.** A workstream that was stopped and is now resuming is a new workstream, by definition. The prior cancelled or superseded record stands as the historical fact.
- **Movement between the three terminal states is also forbidden.** A `cancelled` workstream cannot be reclassified as `superseded` even if a successor workstream emerges later. The supersession relationship is modelled by the inbound reference from the successor (a new workstream may declare it `supersedes` the prior cancelled one, in which case both records co-exist with their original terminal statuses intact and a `supersedes` edge connecting them — the source's status remains `cancelled`). The status field captures the original lifecycle outcome at the moment the terminal transition happened; the references table captures the relationship to successors.

Server-side validation rejects invalid transitions with HTTP 422 and body `{"error": "invalid_status_transition", "from": <current>, "to": <requested>}`. The access-layer enforcement table mirrors the predecessor-successor map above.

The propose-verify gate pattern from the methodology entities (where movement between `confirmed` and `deferred` is permitted in either direction) does not apply to workstream. Workstream's lifecycle is a workflow timeline, not a deliberation-state machine.

#### 3.4.3 Supersession-requires-edge rule

Setting `workstream_status` to `superseded` requires the record to have an outgoing reference edge of kind `supersedes` to another workstream record. The access layer enforces this as a single combined validation:

- POST creating a record with `status = 'superseded'` and no `supersedes` edge: HTTP 422 `{"error": "supersession_requires_successor_edge"}`.
- PUT or PATCH transitioning an existing record to `status = 'superseded'` without an outgoing `supersedes` edge present: same 422.
- The edge may be added in the same request body (the create or update payload may include a `references` array; the access layer evaluates the status transition and the edge state together at commit time).
- DELETE on the `supersedes` edge while the source record still has `status = 'superseded'`: HTTP 422 `{"error": "superseded_workstream_requires_supersedes_edge"}`. The status must be changed first, or the source workstream must be soft-deleted (which removes both the record and its edges from the active view).

#### 3.4.4 Soft-delete semantics

Default V2 base behavior. `workstream_deleted_at` set on DELETE; soft-deleted records do not appear in `GET /workstreams` by default; `?include_deleted=true` reveals them; POST `/restore` clears `workstream_deleted_at` and restores them to the active list. Soft-delete is administrative (the record is removed from the active view) and is distinct from `cancelled` status (which is a lifecycle outcome). A record that is both `cancelled` and soft-deleted is a cancelled workstream whose record was also administratively removed from the active list; restore puts it back, with status still `cancelled`.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/workstreams` | — | List active workstreams; `?include_deleted=true` shows soft-deleted. |
| GET | `/workstreams/{identifier}` | — | Single fetch by identifier. |
| POST | `/workstreams` | full workstream JSON; identifier optional | Create. Identifier server-assigned when omitted. Default `workstream_status` is `planned` if omitted. |
| PUT | `/workstreams/{identifier}` | full workstream JSON | Full replace. Status-transition validation per section 3.4. Lifecycle timestamps server-set on the matching transition; client-supplied values for those columns are ignored. |
| PATCH | `/workstreams/{identifier}` | partial workstream JSON | Partial update. Same validation as PUT for any field touched. |
| DELETE | `/workstreams/{identifier}` | — | Soft-delete; sets `workstream_deleted_at`. |
| POST | `/workstreams/{identifier}/restore` | — | Clears `workstream_deleted_at`. 422 if not currently soft-deleted. |
| GET | `/workstreams/next-identifier` | — | Returns `{"next": "WS-NNN"}` for the next available value. Used by clients computing the identifier client-side, e.g., the desktop New Workstream dialog. |

All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

#### 3.5.2 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission. The helper endpoint `GET /workstreams/next-identifier` exposes the same computation for clients that need the identifier before submitting (e.g., the desktop dialog populating a read-only Identifier label).

### 3.6 User Interface Considerations

Default layout per spec guide section 3.6, with two additions documented below (lifecycle-timestamp display and supersession-edge UX). Both additions follow naturally from this spec's lifecycle decisions and do not constitute architectural deviations.

#### 3.6.1 Sidebar

The Workstreams panel goes in the Governance sidebar group. Position within the group is the build-planning conversation's call; the working assumption is that the six new governance entities sit at the end of the existing Governance group in workstream order (workstream first, then conversation, reference book, work ticket, close-out payload, deposit event). The build-planning conversation may introduce a sub-grouping if the resulting Governance group becomes hard to scan; that question is out of scope for this spec.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with columns:

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `workstream_identifier` | Identifier | narrow | Sortable; default sort. |
| `workstream_name` | Name | wide | Project-language name. |
| `workstream_status` | Status | narrow | Enum value rendered as-is. |
| `workstream_updated_at` | Updated | narrow | Localized date/time. |

Default sort: identifier ascending. Right-click context menu offers New / Edit / Delete / Restore, consistent with the user-interface version 0.3 governance-entity panels per DEC-035 and DEC-036.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `workstream_identifier` — read-only label.
2. `workstream_name` — single-line text editor.
3. `workstream_purpose` — single-line text editor with placeholder "One sentence".
4. `workstream_description` — multi-line text editor with placeholder "Paragraph describing the work".
5. `workstream_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default. The collapsed default reinforces that the field is internal consultant scratchpad, not part of the workstream's user-facing summary.
6. `workstream_status` — combo box with the five enum values; the combo's selectable subset at any moment is the union of `{current_status}` and the valid successors of the current status per section 3.4.1, so the user cannot select an invalid transition. Server-side validation is the final gate; the combo's filtering is a UX convenience.
7. **Lifecycle timestamps section** — read-only labels rendered only for the timestamps that are non-null. A `planned` workstream sees no lifecycle timestamps; an `in_flight` one sees Started; a `complete` one sees Started and Completed; a `cancelled` one sees Cancelled and (optionally) Started; a `superseded` one sees Superseded and (optionally) Started. The conditional rendering mirrors the underlying nullable columns and keeps the detail pane clean.
8. `ReferencesSection` widget — renders inbound conversation memberships (kind `conversation_belongs_to_workstream`), outbound master plan linkage (kind `workstream_planned_in_reference_book`) when present, and outbound supersession edge (kind `supersedes`) when present. The "Add reference" affordance from the user-interface version 0.3 references-create dialog filters available kinds and target entity types by the strict vocab per `_kinds_for_pair`.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `workstream_identifier` not shown in create mode (server-assigned).
- `workstream_status` defaults to `planned`; the user may select a different starter value for backfill of historical records — for example, when creating a workstream record for a workstream that completed before this entity type existed, the user can set status directly to `complete` and the create endpoint accepts the matching lifecycle timestamp (`workstream_completed_at`) as user-supplied for the backfill case. Backfill behavior is access-layer-detected by the absence of intermediate transitions and is documented as part of section 3.8 (Open questions — retroactive backfill).
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, supersession-requires-edge) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `workstream_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; the combo box restricts selectable values to valid transitions plus the current value (no-op). Setting status to `superseded` requires an outgoing `supersedes` edge to be present (added via the ReferencesSection's "Add reference" affordance before the status change is committed, or via the same patch payload); attempting to commit `superseded` without the edge surfaces the 422 inline.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `workstream_identifier` value (e.g., `WS-002`) to enable the Delete button, matching the user-interface version 0.3 governance-entity patterns. Confirmation soft-deletes the record.

### 3.7 Acceptance Criteria

The following sixteen statements define what "this entity type is correctly implemented in the eventual build" looks like. Each is concrete and testable; the build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `workstreams` table with all thirteen columns (`workstream_identifier`, `workstream_name`, `workstream_status`, `workstream_purpose`, `workstream_description`, `workstream_notes`, `workstream_created_at`, `workstream_updated_at`, `workstream_deleted_at`, `workstream_started_at`, `workstream_completed_at`, `workstream_cancelled_at`, `workstream_superseded_at`), correct types and constraints, and runs both forward and backward without error.

2. **`workstream_identifier` format constraint enforced.** Insertions with `workstream_identifier` not matching `^WS-\d{3}$` raise a validation error at the access layer.

3. **`workstream_name` uniqueness enforced case-insensitively.** Inserting a second row whose `workstream_name` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`workstream_status` enum and transition validation.** Insertions with `workstream_status` outside the five-value enum are rejected. PATCH or PUT requesting an invalid transition (e.g., `complete` → `in_flight`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

5. **Terminal states are truly terminal.** All three terminal statuses (`complete`, `cancelled`, `superseded`) reject every outgoing transition, including transitions between terminal states (e.g., `cancelled` → `superseded`). Same 422 shape.

6. **Supersession-requires-edge rule.** POST or PATCH setting `workstream_status = 'superseded'` without an outgoing `supersedes` edge to another workstream record returns HTTP 422 with `{"error": "supersession_requires_successor_edge"}`. The edge may be supplied in the same request body. Deletion of an existing `supersedes` edge on a `superseded`-status record returns the parallel 422.

7. **Lifecycle timestamps server-set on transition.** `workstream_started_at` is set when status transitions to `in_flight`; `workstream_completed_at` when to `complete`; `workstream_cancelled_at` when to `cancelled`; `workstream_superseded_at` when to `superseded`. Each is idempotent — a second update setting the same status does not change the timestamp. Each is mutually exclusive at the three-terminal level (exactly one of `_completed_at`, `_cancelled_at`, `_superseded_at` is non-null on a terminal record). Client-supplied values for these columns are ignored on PUT and PATCH except in the documented backfill case (create with terminal status accepts user-supplied terminal timestamp).

8. **Access-layer methods exist with expected signatures.** `client.list_workstreams()`, `client.get_workstream(identifier)`, `client.create_workstream(...)`, `client.update_workstream(identifier, ...)`, `client.patch_workstream(identifier, ...)`, `client.delete_workstream(identifier)`, `client.restore_workstream(identifier)`, `client.next_workstream_identifier()` exist and pass unit tests covering happy path and at least one error case each.

9. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the V2 `{data, meta, errors}` envelope per `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`.

10. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /workstreams/next-identifier` returns `{"next": "WS-NNN"}` for the next available number. POST with `workstream_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier (verified by a concurrent-insert test).

11. **Soft-delete and restore round-trip correctly.** DELETE sets `workstream_deleted_at`; the record disappears from `GET /workstreams`. `GET /workstreams?include_deleted=true` shows it. POST `/restore` clears `workstream_deleted_at`; the record reappears. Restore on a record that is not soft-deleted returns 422.

12. **Vocabulary additions registered.** `REFERENCE_RELATIONSHIPS` includes `conversation_belongs_to_workstream` and `workstream_planned_in_reference_book`; `ENTITY_TYPES` includes `workstream`, `conversation`, and `reference_book`; `_kinds_for_pair` returns the correct kind sets for the new pairs; the matching Alembic migration on `refs.relationship_kind`'s CHECK constraint passes. (The `conversation` and `reference_book` entity types are admitted here for vocabulary registration; their own schema specs land their entity tables.)

13. **`Workstreams` sidebar entry appears in the Governance group.** Position within the new-six set is whatever the build-planning conversation chooses; the entry exists, the panel opens, the panel is bound to the access-layer methods.

14. **Master pane columns and default sort.** The Workstreams panel shows columns Identifier / Name / Status / Updated, sorted by Identifier ascending. Right-click context menu offers New / Edit / Delete / Restore.

15. **Detail pane renders all fields in section-3.2 order, with conditional lifecycle timestamps.** Identifier (read-only), Name, Purpose, Description, Notes (collapsed under "Internal notes" header), Status, lifecycle-timestamps section (showing only non-null timestamps), ReferencesSection — all present and bound to the correct fields. A freshly-created `planned` workstream shows no lifecycle timestamps; an `in_flight` one shows Started; a terminal one shows Started plus its terminal timestamp (when started_at is non-null).

16. **End-to-end backfill of the governance schema-design workstream.** A consultant can author a `workstream` record for this workstream (the governance entity schema-design workstream) through the New Workstream dialog with status `in_flight` and `workstream_started_at` backfilled to 05-20-26, observe the conversation entity's eventual record landing as an inbound `conversation_belongs_to_workstream` reference (once the conversation entity ships), and later transition the workstream to `complete` with its `workstream_completed_at` server-set. The workstream record persists across application restart and across REST/MCP refetch.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For the build-planning conversation to settle

**[build] Sidebar grouping for the six new governance entities.** The existing Governance group has eight entries (charter, status, decisions, sessions, risks, planning items, topics, references); adding six more makes the group thirteen entries deep. The build-planning conversation decides whether to introduce a sub-grouping (e.g., "Governance — workflow" for the six new ones) or to reorder the existing group, or to accept the longer list as-is. This spec declares default position (Governance group, somewhere among the six new entries in workstream order); the build-planning conversation may overrule.

**[build] Migration ordering across the six schemas.** Each of the six governance schemas requires its own Alembic migration creating the entity table; the references-vocab additions are consolidated into one migration across the six specs (per the spec guide section 9 aggregation rule). Sequencing those migrations safely — entity tables first, then the consolidated refs-vocab migration, then any access-layer cutover — is the build-planning conversation's call.

**[build] Vocabulary kind name `workstream_planned_in_reference_book`.** This kind name was settled in this conversation as the master-plan linkage for the workstream side. The reference_book schema-design conversation (third in the workstream) may have cause to refine the verb tense or the source-target framing (for example, if `reference_book` ends up with multiple inbound kinds and a different verb pattern reads better at the family level). The build-planning conversation reconciles any drift between the two specs.

**[build] Backfill behavior on create with terminal status.** This spec admits a backfill-create case (POST with `workstream_status = 'complete'` plus user-supplied `workstream_completed_at`). The detailed validation behavior — for example, whether `workstream_started_at` must also be supplied for `complete`, whether terminal-timestamp ordering is enforced (cannot have `_completed_at` earlier than `_started_at`), whether the backfill case requires a special flag in the request payload — is left to the build-planning conversation's implementation pass. The minimum-viable rule documented here is "create with terminal status accepts user-supplied terminal timestamp; non-create transitions reject user-supplied timestamps and server-set them."

#### 3.8.2 For retroactive backfill (PI-022) to surface

**[backfill] Historical lifecycle timestamps for prior workstreams.** PI-022 covers retroactive population of workstream records for prior workstreams (the methodology workstream, the user-interface version 0.5 engagement-management workstream, the user-interface version 0.6 styling workstream, the multi-tenancy routing fix workstream, the Cleveland Business Mentors paper test workstream, this governance workstream itself). The retroactive records require historical lifecycle timestamps; the backfill pass determines which dates to use (commit dates, session-record dates, kickoff-prompt commit dates) and resolves any ambiguity case-by-case. This is a question for PI-022's resolution, not for this spec.

**[backfill] Status assignment for prior workstreams.** Similarly, whether the methodology workstream's record is `complete` (the workstream concluded with the build-planning conversation) or whether the original v0.4 user-interface workstream was `superseded` by the methodology workstream (per the kickoff prompt's example) is PI-022's call. The schema supports both outcomes; the policy is for the backfill pass to decide.

#### 3.8.3 For a future release

**[future] Outcome summary field.** Not introduced in this release. The closing conversation's session record carries the outcome narrative; status alone (`complete` / `cancelled` / `superseded`) carries the binary outcome. If a real query need surfaces ("show me the outcome summaries for all complete workstreams"), a future release adds a `workstream_outcome` field with a migration; the schema admits it additively.

**[future] Target user-interface version field.** Not every workstream targets a specific user-interface version; the build-planning conversation sets the target at build time. Free text in `workstream_description` covers the case where a workstream wants to claim a target version. If a real query need surfaces, a future release adds the column.

**[future] Predecessor-successor reference kinds between workstreams (other than supersession).** Sequential relationships between workstreams ("the governance workstream follows the methodology workstream") are not modelled in this release. If a real use case surfaces, the addition is one vocab.py line plus the build-planning aggregation.

**[future] Nested workstreams.** Deferred per Decision 3. If a real use case surfaces — for example, a future Cleveland Business Mentors implementation workstream containing four domain-specific sub-workstreams — the retrofit path is a new reference kind `workstream_parent_of_workstream` (references-edge, not self-FK column) plus the access-layer "at most one parent edge per workstream" rule plus the user-interface tree rendering. The retrofit deliberately avoids touching the workstream table.

**[future] Pause / resume / hold lifecycle states.** Not introduced in this release. Workstream's lifecycle is forward-only with truly terminal terminals. If real operational signal supports a pause-and-resume case (a workstream that is intentionally on hold but not cancelled), a future release may admit a `paused` status with transitions back to `in_flight`. The minimum-viable posture preserves the timeline semantics by treating pauses as a free-text concern (note in `workstream_notes` or `workstream_description`).

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_048.json` at conversation close. Each is linked to SES-048 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-123 through DEC-128) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-123 — `workstream` identifier prefix and format.** Adopts `WS` as the prefix; affirms two-letter form as acceptable without locking the cross-spec norm at two letters (downstream conversations may choose three or four letters where useful).
- **DEC-124 — `workstream` workstream-to-conversation relationship via references-table edge.** Confirms DEC-120's decision text. Names the relationship kind `conversation_belongs_to_workstream`. Sets the cross-spec precedent of references-edge over foreign-key for parent-child governance relationships.
- **DEC-125 — `workstream` lifecycle: five statuses with truly terminal terminals and supersession-requires-edge rule.** Adopts `planned` / `in_flight` / `complete` / `cancelled` / `superseded` with the transition map of section 3.4.1, the truly-terminal posture of section 3.4.2, and the supersession-requires-edge access-layer rule of section 3.4.3. Sets cross-spec precedent of the truly-terminal posture for governance entities with workflow-shaped lifecycles.
- **DEC-126 — `workstream` field inventory including per-status lifecycle timestamps.** Captures the nine-field shape (identity, content, classification, no FK fields, base plus four per-status lifecycle timestamps) per section 3.2. Sets cross-spec precedent of per-status lifecycle timestamps for workflow-shaped lifecycles.
- **DEC-127 — `workstream` flat catalog, no nesting in this release.** Defers nested workstreams. Documents the retrofit path as a references-edge addition (not a self-FK column) per section 3.3.3 and section 3.8.3. Sets a soft precedent for downstream governance entities considering hierarchy questions.
- **DEC-128 — `workstream` master plan linkage, API surface, UI defaults, soft-delete posture, and acceptance criteria.** Master plan modelled as a references-edge with new kind `workstream_planned_in_reference_book`; supersession reuses existing generic `supersedes` kind for `(workstream, workstream)` pair; standard endpoint set with no deviations; default UI layout with the lifecycle-timestamp display addition; default soft-delete with restore; sixteen acceptance criteria captured.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the next five schema-design conversations.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-workstream.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `workstream` records live in the per-engagement database.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary the new entity type and relationship kinds register against.
- `PRDs/product/crmbuilder-v2/methodology-schema-specs/domain.md` — methodology workstream's first schema spec, structurally parallel to this document.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. `workstream` is not one of the three file-tracking families (reference book, work ticket, deposit bucket); it is the organizing-unit complement that DEC-119 / DEC-120 added alongside.
- **DEC-118** — Two entities within the deposit bucket family. Not directly extended by this spec but cited as foundation.
- **DEC-119** — Add a conversation entity. The `conversation` entity references `workstream` via the kind named in this spec.
- **DEC-120** — Add a workstream entity. **Most directly extended.** This spec is the realization of DEC-120, including the explicit resolution of the deferred nested-workstream question (section 3.3.3) and the confirmation of the references-table-edge mechanism (section 3.3.1 and section 3.3.2).
- **DEC-121** — Single-source-of-truth coverage extension. `workstream` is one of the six new entity types closing the coverage gap.
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. This spec's soft-delete-not-append-only posture for `workstream` is informed by this decision's framing of when append-only is the right pattern: append-only fits transactional records (a decision, a session, a deposit event), not organizing structures (a workstream).
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.9.1's reliance on the close-out payload's apply script and the session record as the durable artifacts of this conversation.
- **DEC-029** — Charter and Status replace via JSON editor with Validate + Make Current. Not directly applicable to `workstream` (the entity does not use the versioned-replace pattern), but informs the API write-pattern norms this spec adopts.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master pane patterns in section 3.6.2.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields are prefixed `workstream_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited; `conversation_belongs_to_workstream` and `workstream_planned_in_reference_book` both follow the pattern.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `workstream` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-047 — workstream-establishing planning conversation for the governance entity schema-design workstream. Produced the workstream plan, the schema spec methodology guide, and the six per-entity kickoff prompts.
- **Successor:** `conversation` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-conversation.md`. Inherits the precedents established here: references-edge over foreign-key for parent-child relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline. The conversation entity is structurally the workstream's most direct downstream consumer — every conversation record carries an outbound `conversation_belongs_to_workstream` edge to its workstream.

---

*End of document.*
