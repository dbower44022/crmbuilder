# Governance Entity Schema Spec — `work_ticket`

**Last Updated:** 05-21-26 18:00
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** Fourth of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-050 (`reference_book` schema-design conversation)
**Successor conversation:** `close_out_payload` schema design — kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-21-26 18:00 | Doug Bower / Claude | Initial draft. Produced by the fourth schema-design conversation in the governance-entity schema-design workstream. Adopts the five cross-spec precedents now in force: the three from SES-048 (references-edge over foreign-key for parent-child governance relationships, per-status lifecycle timestamps for workflow-shaped lifecycles, terminal-states-are-terminal discipline), the one from SES-049 (typed sequencing edges introduced when entity-family frequency justifies), and the one from SES-050 (documentary-shaped lifecycles inherit base timestamps only). Establishes a new cross-spec precedent of its own: terminal-state consumption requires the inbound consumption edge — the inverse of the supersession-requires-edge pattern, applicable to any governance entity with a terminal state defined by an external act of consumption or application. Resolves the boundary question with `reference_book` in favour of intent-at-creation classification with no in-place re-categorization; a file that turns out to span both families is governed by two independent records pointing at the same `file_path`. Declines the tentative `work_ticket_consumed_by_conversation` kind named by `conversation.md`'s section 3.3.2 as redundant — the existing outbound `conversation_opens_against_work_ticket` edge declared in `conversation.md` is the sole canonical edge for the relationship, viewed from work_ticket's side as inbound. Declines a typed `work_ticket_reads_reference_book` kind for kickoff-prompt read-list citations on the strength of DEC-133's frequency-justified test — read-lists are operational metadata rather than queried-by structure; the generic `references` kind suffices. Adds no new relationship-kind vocabulary; only adds the entity type itself plus a reaffirmation of an entity type entry already named by `conversation.md`. |

---

## Change Log

**Version 1.0 (05-21-26 18:00):** Initial creation. Defines `work_ticket` as the V2 governance entity type that hosts the single-use seed document concept per DEC-117's second family — the workflow files produced for one specific conversation, consumed by that conversation, and not subsequently referenced as a source of truth. Establishes six content/classification fields (`work_ticket_identifier`, `work_ticket_title`, `work_ticket_description`, `work_ticket_notes`, `work_ticket_kind`, `work_ticket_status`) plus one file-pointer field (`work_ticket_file_path`) plus seven timestamp columns (three inherited base, four per-status lifecycle: `work_ticket_ready_at`, `work_ticket_consumed_at`, `work_ticket_cancelled_at`, `work_ticket_superseded_at`). Establishes a five-status workflow-shaped lifecycle (`drafted` → `ready` → `consumed`, plus terminals `cancelled` and `superseded`) with truly-terminal terminal states and a new consumed-requires-edge access-layer rule mirroring the supersession-requires-edge pattern. Adopts a closed four-value kind enum (`kickoff_prompt`, `claude_code_prompt`, `ad_hoc_prompt`, `other`) covering the project's observed work-ticket families with the sentinel as the documented escape hatch. No new relationship-kind vocabulary required — the inbound edge from conversation was pre-declared by `conversation.md` as `conversation_opens_against_work_ticket`; supersession reuses the existing generic `supersedes` kind for the same-type pair; read-list citations to reference books use the existing generic `references` kind per DEC-133's frequency-justified deferral test. Standard API endpoint set with no deviations. Default soft-delete with restore, explicitly distinct from `cancelled` status (a lifecycle outcome — the work_ticket was abandoned without being consumed) and `consumed` status (a successful-use outcome — the conversation opened against it). Default UI layout with two natural additions paralleling `reference_book.md`'s pattern: a Kind column in the master pane and a Status filter combo in the master-pane toolbar (because browse-by-status is the operational pattern named in the kickoff — "Work tickets often need to be browsed by status (`ready` to see what is queued up for opening)"). Sixteen acceptance criteria captured. Six decisions and zero planning items authored at conversation close (PI-022 covers retroactive backfill for work_ticket records as it does for the other governance entity types).

---

## 1. Purpose and Position

This document specifies the `work_ticket` entity type for V2's storage layer. It is the **fourth of six** schema specs produced by the governance-entity schema-design workstream — designed after `reference_book.md` so that the long-lived versioned reference document family is a settled referent and the boundary between the two file-tracking families (DEC-117's family 1 and family 2) can be drawn from work_ticket's side in contrast to reference_book's already-defined shape.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, `conversation`, `reference_book`, `work_ticket`, then `close_out_payload`, `deposit_event` — feeding a seventh build-planning conversation that integrates them into a coherent release.

`work_ticket`'s primary scope in this release is to host the single-use seed document concept per DEC-117's second family — the workflow files produced for one specific conversation, consumed by that conversation, and not subsequently referenced as a source of truth. The kickoff lists representative examples already in the project's operating history: the per-entity schema-design kickoff prompts in this workstream itself (`schema-design-kickoff-workstream.md`, `schema-design-kickoff-conversation.md`, `schema-design-kickoff-reference-book.md`, this conversation's `schema-design-kickoff-work-ticket.md`, the forthcoming two); the methodology workstream's analogous kickoffs (`schema-design-kickoff-domain.md`, `schema-design-kickoff-entity.md`, `schema-design-kickoff-process.md`, `schema-design-kickoff-crm_candidate.md`); the planning prompts that opened each user-interface version's planning conversation (`ui-v0.4-planning-prompt.md`, `ui-v0.5-conversation-1-kickoff.md`, etc.); the workstream-establishing kickoffs (`governance-entity-schema-workstream-establishing-kickoff.md`, `methodology-entity-schema-planning-prompt.md`); the Cleveland Business Mentors paper-test kickoff (`methodology-schemas-cbm-paper-test-kickoff.md`); and the Claude Code prompts under `prompts/` — both the apply-close-out variants (`CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md`, etc.) and the slice-execution variants (`CLAUDE-CODE-PROMPT-v2-ui-v0.4-B-domains-panel.md`, etc.).

The schema is intentionally minimum-viable. Author tracking, deliverable-checklist fields, separate target-deliverable description columns, content blob storage, automated path-existence validation, and retroactive backfill of historical work_ticket records are deliberately out of scope; each is deferred to a future release pending real-use signal, with backfill specifically deferred to PI-022.

This conversation **inherits five cross-spec precedents now in force** and applies them throughout:

- **References-edge over foreign-key for parent-child governance relationships** (DEC-124, SES-048). Work_ticket's relationships to other governance entities live in `refs`, not as foreign-key columns. The inbound consumption edge from conversation, the outbound supersession edge to another work_ticket, and the outbound generic-citation edges to reference books all follow.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles** (DEC-126, SES-048). Work_ticket's lifecycle is workflow-shaped (a forward-only consumption timeline: drafted → ready → consumed); the spec carries one timestamp column per non-starter status, server-set on transition. Unlike reference_book's documentary lifecycle, which DEC-137 confirmed inherits base timestamps only, work_ticket's lifecycle is operationally meaningful at each transition (consultants ask "when did this become ready?" and "when was it consumed?") and the per-status pattern earns its storage.
- **Terminal-states-are-terminal discipline** (DEC-125, SES-048). Work_ticket's three terminal statuses (`consumed`, `cancelled`, `superseded`) admit no transitions out — including no transitions between terminal states. A `consumed` work_ticket cannot become `superseded` even if the kickoff is later rewritten; the kickoff rewrite is a new work_ticket with its own `consumed` status when its successor conversation opens. Reactivation of a terminal work_ticket is not supported.
- **Typed sequencing edges introduced when entity-family frequency justifies** (DEC-133, SES-049). Work_ticket applies this precedent and **does not introduce** a typed sequencing kind. Work_tickets within a workstream are sequenced through the conversations they kick off, not through direct edges between work_tickets themselves; the conversation entity's `conversation_succeeds_conversation` chain already captures the sequencing. No `work_ticket_succeeds_work_ticket` kind is required.
- **Documentary-shaped lifecycles inherit base timestamps only** (DEC-137, SES-050). Work_ticket explicitly does NOT fit this category — its lifecycle is workflow-shaped, not documentary — so the spec carries per-status lifecycle timestamps per DEC-126 rather than inheriting base only per DEC-137. The distinction is named here because the next two specs (`close_out_payload`, `deposit_event`) apply the workflow-vs-documentary distinction on their own facts; close_out_payload's drafted-vs-applied lifecycle is workflow-shaped (per-status timestamps), and deposit_event's single-record-at-apply-time shape is append-only with one timestamp.

This conversation also **establishes one new cross-spec precedent** the remaining two schemas inherit by default and may deviate from with rationale:

- **Terminal-state consumption requires the inbound consumption edge.** The supersession-requires-edge rule established by DEC-125 enforces that a terminal `superseded` status requires an outgoing successor edge to be present. Work_ticket establishes the inverse pattern for the `consumed` terminal: transition to `consumed` requires the inbound `conversation_opens_against_work_ticket` edge to be present, because the consumption event is what defines the terminal. The precedent generalizes — for any governance entity with a terminal state defined by an external act of consumption or application, the transition to that terminal requires the inbound edge naming the consumer or applier. Close_out_payload's anticipated `applied` terminal status is the next case; its inbound edge from deposit_event would be required to be present before the transition to `applied` is admitted. Deposit_event's append-only-with-one-timestamp posture means it does not itself need a terminal-edge rule (the record's creation IS the apply event), but close_out_payload reads the pattern from this conversation's precedent.

---

## 2. Summary

A `work_ticket` record in V2 represents one single-use seed document — a workflow file authored for one specific conversation, consumed by that conversation when it opens against the file, and not subsequently referenced as a source of truth. Real examples already implicit in the project's history at this spec's authoring time include the kickoff prompt for this conversation itself (`schema-design-kickoff-work-ticket.md`); the kickoff prompts for the three predecessor schema-design conversations and the two successor conversations in this workstream; the per-entity kickoffs of the methodology workstream's four schema-design conversations; the user-interface version planning prompts (`ui-v0.4-planning-prompt.md`, `ui-v0.5-conversation-1-kickoff.md`, `ui-v0.5-conversation-2-kickoff.md`, `styling-conversation-1-kickoff.md`); the workstream-establishing kickoff prompts (`governance-entity-schema-workstream-establishing-kickoff.md`, `methodology-entity-schema-planning-prompt.md`); and the Claude Code prompts under `prompts/` — every file matching `CLAUDE-CODE-PROMPT-*.md` is structurally a single-use seed document for one Claude Code execution. Each is structurally a one-conversation seed file — but before this entity type lands, each exists only as a path string on the filesystem and as a filename pattern with no machine-resolvable backreference to the conversation it kicked off.

The schema in this release is the thinnest shape that captures the single-use-seed concept faithfully: a human-readable title, a paragraph description, an optional consultant notes field, a closed kind classification, a five-status workflow lifecycle with timestamps for each non-starter transition, a repo-relative file path string, references-edge linkage inbound from the conversation that consumes it (declared in `conversation.md` as `conversation_opens_against_work_ticket`), references-edge linkage outbound to another work_ticket when superseded (existing generic `supersedes` kind), and generic references-edge linkages outbound to reference books cited in the kickoff's read-list and to any other governance records the work_ticket references. The schema deliberately omits author/owner tracking, deliverable-checklist fields, target-deliverable description as a separate column (folded into `work_ticket_description`), content blob storage, automated path-existence validation, and a sub-kind taxonomy below the four named kinds — each grows additively in a later release if real-use signal supports it.

**Boundary with `reference_book`.** The same physical file may be governed by both a `work_ticket` record and a `reference_book` record. The two records describe two distinct governance views of the file: the work_ticket captures its one-use role for a specific conversation; the reference_book captures its long-lived multi-consumer role. The records have different identifiers, different lifecycles, and live in different tables. The schema does NOT enforce mutual exclusivity at the `work_ticket_file_path` / `reference_book_file_path` level — both columns are unique within their own table, not unique across the union. The methodology workstream master plan example raised in the kickoff (`ui-v0.4-planning-prompt.md`, which kicked off SES-011 but is now retroactively cited by successor planning documents) stays a work_ticket — the retroactive citations are archival mentions of what kicked off a past conversation, not authoritative reads of a long-lived reference. If the citation pattern intensifies enough to warrant authoritative-reference treatment, a separate reference_book record is authored against the same `file_path`; the two records co-exist as independent governance views. This intent-at-creation classification with no in-place re-categorization is the schema-level answer to the kickoff's three-way boundary question.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `work_ticket` |
| Display name (singular) | Work Ticket |
| Display name (plural) | Work Tickets |
| Identifier prefix | `WT` |
| Identifier format | `WT-NNN`, zero-padded to 3 digits (e.g., `WT-001`, `WT-042`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /work-tickets/next-identifier` |

**Identifier-prefix posture.** `WT` is two letters, matching `WS`, `RB`, and `PI` in the existing short-prefix set. DEC-123 affirmed two-letter form acceptable; the spec guide's section 6 range admits 2 to 5 letters. The collision list at this spec's writing has no conflict with `WT` — no existing or pending governance or methodology entity-type prefix begins with `W` other than `WS`, and the two-letter `WT` versus two-letter `WS` differs in the second character and reads without ambiguity. The kickoff's working assumption of `WT` is confirmed; the alternatives `WKT`, `TIX`, and `TKT` add no value beyond length and `TIX` / `TKT` carry connotations from ticket-tracking systems (Jira, Trello) that the project deliberately does not invoke — "work ticket" in this project is a single-use seed document, not an issue-tracking artifact.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier and timestamps are prefixed `work_ticket_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `work_ticket_identifier` | TEXT | yes | server-assigned | `^WT-\d{3}$`, unique | The work_ticket identifier in `WT-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /work-tickets/next-identifier` returns the next available value. |
| `work_ticket_title` | TEXT | yes | — | non-empty trimmed; case-insensitive unique within the engagement | Work ticket title in the project's working language (e.g., "Work ticket entity schema-design kickoff", "Apply close-out for SES-049", "User-interface version 0.5 engagement-management planning prompt"). Distinct from the file's own internal title, though typically aligned. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `work_ticket_description` | TEXT | yes | — | non-empty trimmed | Paragraph describing what the work_ticket is for — what conversation it is intended to kick off, what deliverables that conversation should produce, what context the kickoff loads. The kickoff's "intended-deliverable description" named as a candidate first-class field is folded into this paragraph rather than carried as a separate column. Plain text in this release. |
| `work_ticket_notes` | TEXT | no | — | — | Internal consultant scratchpad. Not part of the work_ticket's user-facing summary. Used to capture authoring context, drafting decisions worth surfacing in the close-out of the consuming conversation, or post-consumption observations (e.g., "the conversation deviated from the kickoff's outline at step 3 — kickoff was right, conversation drift was the issue"). Plain text in this release; structured-journal pattern deferred to signal. |

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `work_ticket_kind` | TEXT | yes | — | enum: `kickoff_prompt` \| `claude_code_prompt` \| `ad_hoc_prompt` \| `other` | Classification of what kind of single-use seed this work_ticket is. Closed enum; `other` is the sentinel for tickets that do not fit the named categories. See section 3.4.6 for the rationale on each value. |
| `work_ticket_status` | TEXT | yes | `drafted` | enum: `drafted` \| `ready` \| `consumed` \| `cancelled` \| `superseded`; valid transitions per section 3.4.1; additional rules for `consumed` and `superseded` per sections 3.4.3 and 3.4.4 | Lifecycle status. See section 3.4 for the full state machine. |

#### 3.2.4 Relationship fields

None. Every relationship — inbound consumption from conversation, outbound supersession to another work_ticket, outbound generic citations to reference books named in the kickoff's read-list, outbound generic references to other governance records — lives in the universal references table per the inherited precedent from `workstream.md` (DEC-124). No foreign-key columns on the work_ticket table.

#### 3.2.5 File pointer field

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `work_ticket_file_path` | TEXT | yes | — | non-empty trimmed; must be a repo-relative path (no leading slash, no `..` segments, no scheme prefix); unique within the engagement | Repo-relative path to the canonical file (e.g., `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md`, `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-049.md`). Resolution at use time is performed against the consuming repository's root — typically the crmbuilder repo for dogfood records and the client repo for engagement-specific records. The path is not validated for existence at write time (the file may be authored separately and the record updated to point at it); a future build prompt may add a "check path resolves" verification step. The same `file_path` value may legally coexist as a `reference_book_file_path` value on a parallel reference_book record per the section-2 boundary discipline; uniqueness is within the work_ticket table only, not across the union of work_ticket and reference_book file paths. |

**Path-semantics parity with `reference_book.md`.** The `work_ticket_file_path` column follows the same repo-relative semantics as `reference_book_file_path` per `reference_book.md` section 3.2.5. The two columns are independent; the same string may be the canonical file_path of both a work_ticket and a reference_book record in the same engagement database, with each record providing the governance view appropriate to its lifecycle.

**No `work_ticket_author` or `work_ticket_owner` column.** The project's working pattern has Doug as sole author and owner of every work_ticket, with most work_tickets co-authored by Claude at session close; no per-record author tracking is needed. If multi-author engagements emerge, the column is one migration away.

**No `work_ticket_target_deliverable` column.** The candidate first-class "target deliverable description" field named in the kickoff is folded into `work_ticket_description` for this release. Most kickoffs name the target deliverable in the first paragraph of their description; a separate column would duplicate the narrative. If a structured deliverable taxonomy emerges in operation (for example, a `target_deliverable_type` enum naming "schema specification", "Word document", "Markdown report", "Python module"), a future release adds it.

**No storage-level length caps** on text fields, matching the workstream / conversation / reference_book precedents.

#### 3.2.6 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `work_ticket_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `work_ticket_updated_at` | DATETIME | yes | server-set on insert and on each update | ISO 8601 UTC | Inherited base behavior; not user-editable. |
| `work_ticket_deleted_at` | DATETIME | no | null until soft-delete | ISO 8601 UTC when set | Inherited base behavior. Set on DELETE; cleared on POST `/restore`. |
| `work_ticket_ready_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `drafted` → `ready` transition. Once set, not user-editable. Captures the moment the kickoff was committed and the conversation became openable. |
| `work_ticket_consumed_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on the `ready` → `consumed` transition. Once set, not user-editable. Captures the moment the conversation opened against the work_ticket. Mutually exclusive with `work_ticket_cancelled_at` and `work_ticket_superseded_at` — exactly one of the three terminal-state timestamps is populated on any terminal record. |
| `work_ticket_cancelled_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `cancelled` (reachable from `drafted` or `ready`). Once set, not user-editable. |
| `work_ticket_superseded_at` | DATETIME | no | null | ISO 8601 UTC when set | Server-set on any transition to `superseded` (reachable from `drafted` or `ready`). Once set, not user-editable. |

**No `work_ticket_drafted_at` column.** A work_ticket's drafted-at moment is always equal to its `work_ticket_created_at` (the default starter status is `drafted`, set at insert time). A separate column would be redundant. The single exception — a backfilled record whose historical drafting happened before its database insert — uses `work_ticket_created_at` with the backfill timestamp; the distinction is not tracked separately in this release. Identical posture to workstream's `_planned_at` and conversation's `_planned_at` non-columns.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

Work_ticket has a deliberately narrow outbound edge set. Most relationships to work_tickets are inbound (the conversation reaches into the work_ticket; reference books are read into the work_ticket's kickoff; the work_ticket is referenced from session records and decisions). The two outbound kinds are supersession and generic citations.

**Supersession linkage.** When a work_ticket's status is set to `superseded`, it must have an outgoing reference edge identifying the successor work_ticket that carries the work forward. The relationship uses the existing generic `supersedes` reference kind (already permitted for `(work_ticket, work_ticket)` once `work_ticket` is in `ENTITY_TYPES` because `_kinds_for_pair`'s `source_type == target_type` rule admits `supersedes` for any same-type pair). No new kind is introduced for this relationship; the established vocabulary is reused, identical to workstream's, conversation's, and reference_book's patterns.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `supersedes` (existing kind, reused) | `work_ticket` | `work_ticket` | This work_ticket was redirected; the target work_ticket carries forward the work. Required when source.status = `superseded`; access-layer enforces. Typical case: the kickoff was rewritten enough to warrant a new ticket with its own identifier — the prior ticket is marked `superseded` and points at the successor. |

**Generic citation linkages.** A work_ticket may cite any other governance record using the existing generic `is_about` and `references` kinds — no new vocabulary required. The most common case is a kickoff prompt's "Read this first" list, which names reference books the conversation should load (the workstream master plan, the spec guide, predecessor specs, foundation decisions). Each named reference book is captured as an outbound `references` edge from the work_ticket to the reference_book record. The kickoff's open question on whether to introduce a typed `work_ticket_reads_reference_book` kind is resolved in favour of declining the typed kind per DEC-133's frequency-justified test — read-list citations are operational metadata, not queried-by structure, and the generic kind suffices.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `references` (existing kind, reused) | `work_ticket` | any governance entity type | Generic citation. Used for kickoff-prompt read-list references to reference books, to predecessor session records, to foundation decisions, and to any other governance record the kickoff names as context. |
| `is_about` (existing kind, reused) | `work_ticket` | any governance entity type | Generic topical reference. Used when the work_ticket's subject matter primarily concerns another governance record (rare; most work_tickets are about a conversation that has not yet opened, captured by the inbound consumption edge rather than an outbound is_about). |

#### 3.3.2 Inbound relationships (declared by source-side specs)

`work_ticket` is the target of inbound references from `conversation` and admits inbound generic citations from any governance entity type.

**Consumption from conversation.** The canonical inbound edge — the relationship that defines what makes a work_ticket a work_ticket rather than a reference_book. The edge was declared in `conversation.md` section 3.3.1 as outbound from conversation; this spec lists it as inbound for cross-spec consistency-check purposes and confirms the kind name as-is.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `conversation_opens_against_work_ticket` | `conversation` | `work_ticket` | references-table edge | one-to-one (each work_ticket has at most one inbound consumption edge; each conversation has at most one outbound consumption edge per `conversation.md` section 3.3.1) | The conversation opened against this work_ticket as its kickoff. **Required-when** rule from work_ticket's side: when work_ticket.status = `consumed`, exactly one inbound edge of this kind must be present (see section 3.4.3 for the consumed-requires-edge rule). **At-most-one** rule: a work_ticket may never have more than one inbound edge of this kind, enforced at the access layer. Multiple inbound edges return HTTP 422 `{"error": "work_ticket_single_use_violation"}` regardless of the work_ticket's current status. |

**Kind-name resolution.** The tentative `work_ticket_consumed_by_conversation` kind named by `conversation.md` section 3.3.2 is **declined as redundant**. The references table is directed source-first per DEC-048; one edge with one kind per logical relationship is the established pattern across the workstream and conversation specs (workstream→reference_book master plan, conversation→workstream membership, conversation→session record — each is one edge, one kind). The conversation→work_ticket consumption relationship is one edge with the kind `conversation_opens_against_work_ticket`; viewed from work_ticket's side it is inbound with the same kind. No separate work_ticket-side outbound kind is introduced. The vocab.py registration of `conversation_opens_against_work_ticket` belongs to `conversation.md` (already named there in section 3.3.4); this spec lists the kind in section 3.3.4 only as a confirmation re-listing for the build-planning conversation's consolidation pass.

**Generic citations from other governance entities.** Session records, decisions, planning items, and other governance records routinely cite the work_tickets they originated from or the work_tickets that produced them, using the existing generic `references` and `is_about` kinds. No new vocab needed.

| relationship_kind | source | target | mechanism | cardinality | semantics |
|-------------------|--------|--------|-----------|-------------|-----------|
| `references` (existing kind) | any governance entity type | `work_ticket` | references-table edge | many-to-many | Generic citation pointing at the work_ticket. Common case: a session record's `topics_covered` or `in_flight_at_end` text names the kickoff that opened the conversation; PI-022's backfill pass converts those text mentions to typed `conversation_opens_against_work_ticket` edges where applicable and leaves the rest as `references` edges. |
| `is_about` (existing kind) | any governance entity type | `work_ticket` | references-table edge | many-to-many | Generic topical reference. Rare for work_tickets — the typical "about" reference points at the conversation or the deliverable, not the kickoff. |

#### 3.3.3 Hierarchy

Work_ticket does not use the self-referential parent-child hierarchy pattern in this release. A work_ticket does not contain sub-tickets; the supersession chain captured by `supersedes` is a directed line, not a tree. No hierarchy pattern needed.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are named here and aggregated by the build-planning conversation into one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint, alongside the additions from the other five schema specs. **This spec's additions are minimal** — only the entity type itself, already named by `conversation.md`. No new relationship-kind values are introduced.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `ENTITY_TYPES` | `work_ticket` | This entity type. Already named in `conversation.md` section 3.3.4's additions table (as required-because-named-as-target-of-conversation-opens-against); re-listed here for completeness. The build-planning conversation deduplicates against the consolidated additions across the six specs. |
| `_kinds_for_pair` | (no change beyond conversation.md's clause) | The `_kinds_for_pair` clause `if source_type == 'conversation' and target_type == 'work_ticket': kinds.add('conversation_opens_against_work_ticket')` is already named in `conversation.md` section 3.3.4. No additional clauses are required from this spec. The existing same-type rule `if source_type == target_type: kinds.add('supersedes')` admits the `(work_ticket, work_ticket)` supersession edge once `work_ticket` is in `ENTITY_TYPES`. The existing defaults for the generic `references` and `is_about` kinds admit all generic citations to and from work_ticket without additional clauses. |

The existing generic `supersedes`, `references`, and `is_about` kinds cover every relationship this entity type requires. No new `REFERENCE_RELATIONSHIPS` entries are added by this spec — a structural parallel to `reference_book.md`, which also added zero relationship-kind entries. The build-planning conversation observes that work_ticket and reference_book together contribute zero new relationship kinds; only the conversation entity contributed multiple new typed kinds for governance relationships, justified by the conversation entity's central position in the planning-and-execution workflow.

### 3.4 Lifecycle

#### 3.4.1 Status values

| Status value | Description | Valid predecessors | Valid successors |
|--------------|-------------|--------------------|------------------|
| `drafted` | The kickoff or prompt file is being authored. The work_ticket record exists in the database but the file may be incomplete and the consuming conversation has not yet opened. **Default starter status.** | (none — starter) | `ready`, `cancelled`, `superseded` |
| `ready` | The file is complete and committed; the consuming conversation can be opened. The work_ticket is in the queue of openable conversations. | `drafted` | `consumed`, `cancelled`, `superseded` |
| `consumed` | The consuming conversation has opened against this work_ticket. Terminal. Requires an inbound `conversation_opens_against_work_ticket` edge per section 3.4.3. | `ready` | (none — terminal) |
| `cancelled` | The work_ticket was abandoned without being consumed — the conversation it was authored for was cancelled, the kickoff approach was scrapped, or other operational reason. Terminal. Reachable from `drafted` or `ready`. | `drafted`, `ready` | (none — terminal) |
| `superseded` | The work_ticket was abandoned without being consumed, but a successor work_ticket carries the work forward (typically a rewritten kickoff). Terminal. Requires an outgoing `supersedes` edge to the successor work_ticket per section 3.4.4. Reachable from `drafted` or `ready`. | `drafted`, `ready` | (none — terminal) |

The default starter status is `drafted`.

#### 3.4.2 Transition semantics

The status lifecycle is a **forward-only workflow timeline with three truly terminal terminal states**, identical posture to workstream, conversation, and reference_book per the inherited precedent. The two non-terminal states form a strict line (`drafted` → `ready`); neither admits a regressive transition. Each terminal state admits no outgoing transitions; reactivation of a terminal work_ticket is not supported. A work_ticket that needs to resume after reaching a terminal state is modelled as a new work_ticket record, typically created with status `drafted` and (in the supersession case) an inbound reference from the prior work_ticket via the `supersedes` kind.

Three corollaries of the forward-only posture, parallel to workstream's, conversation's, and reference_book's:

- **No regression through the drafting lifecycle.** A work_ticket that reaches `ready` cannot return to `drafted` even if the kickoff is partially withdrawn for further revision; the appropriate response is to cancel the work_ticket and create a new one (typically with a `supersedes` edge from the new to the old), or to make the revision in a follow-up commit and accept that the `ready_at` timestamp captures the moment of first readiness rather than the moment of latest revision.
- **No regression from terminal.** `consumed`, `cancelled`, and `superseded` cannot regress to any non-terminal state. A work_ticket whose role resumes after a terminal state is a new work_ticket, not an edit of the prior record.
- **No movement between terminal states.** A `cancelled` work_ticket cannot be reclassified as `superseded` even if a successor work_ticket emerges later. A `consumed` work_ticket cannot be reclassified as `superseded` even if the kickoff is later rewritten — the rewrite is a new work_ticket, and the old one remains `consumed` (its conversation did happen). The supersession relationship is modelled by the inbound reference from the successor when applicable; the source's status remains its original terminal value.

Server-side validation rejects invalid transitions with HTTP 422 and body `{"error": "invalid_status_transition", "from": <current>, "to": <requested>}`. The access-layer enforcement table mirrors the predecessor-successor map above.

#### 3.4.3 Consumed-requires-edge rule (new cross-spec precedent)

Setting `work_ticket_status` to `consumed` requires the record to have an inbound reference edge of kind `conversation_opens_against_work_ticket` from a conversation record. The access layer enforces this as a single combined validation, the inverse of the supersession-requires-edge pattern established by DEC-125:

- POST creating a record with `status = 'consumed'` and no inbound `conversation_opens_against_work_ticket` edge: HTTP 422 `{"error": "consumed_work_ticket_requires_consumption_edge"}`.
- PUT or PATCH transitioning an existing record to `status = 'consumed'` without an inbound `conversation_opens_against_work_ticket` edge present: same 422.
- The edge may be supplied in the same request body — typically the consuming conversation's POST/PATCH supplies the outbound edge from its side, and the work_ticket's status transition is a subsequent (or coordinated) operation that the access layer validates against the now-present edge.
- DELETE on the inbound `conversation_opens_against_work_ticket` edge while the source work_ticket still has `status = 'consumed'`: HTTP 422 `{"error": "consumed_work_ticket_requires_consumption_edge"}`. The status must be changed first (typically not changeable per terminal-states-are-terminal, in which case the appropriate operation is to soft-delete the work_ticket record administratively rather than detach the consumption edge).

**Cross-spec precedent.** This rule is the new precedent established by this conversation. The supersession-requires-edge rule from DEC-125 requires the **outgoing** successor edge when status = `superseded`. The consumed-requires-edge rule requires the **inbound** consumer edge when status = `consumed`. Both are terminal-state edge-requirement rules; they differ in edge direction because the verb-orientation of the relationship differs. The precedent generalizes — for any governance entity with a terminal state defined by an external act of consumption or application, the transition to that terminal requires the edge naming the consumer or applier to be present, in whichever direction (inbound or outbound) the relationship is canonically modelled. Close_out_payload's anticipated `applied` terminal status follows the same pattern: the transition to `applied` requires the inbound edge from a deposit_event record naming the apply event. Deposit_event's own append-only-with-one-timestamp shape sidesteps the question (the record's creation IS the apply event), but close_out_payload reads the pattern from this conversation's precedent.

#### 3.4.4 Single-use enforcement rule

Independent of the consumed-requires-edge rule, the work_ticket schema enforces single-use semantics at the access layer regardless of status. A work_ticket may **never** have more than one inbound edge of kind `conversation_opens_against_work_ticket` — at any status, in any state. The rule realizes DEC-117's family-2 definition: a single-use seed document has at most one consumer by family-defining property.

- POST attempting to add a second inbound edge of this kind to a work_ticket that already has one: HTTP 422 `{"error": "work_ticket_single_use_violation"}`.
- The rule applies whether the work_ticket's current status is `drafted`, `ready`, `consumed`, `cancelled`, or `superseded`. A `cancelled` work_ticket may have zero inbound edges (the typical case for a kickoff that was scrapped before a conversation opened). A `consumed` work_ticket has exactly one inbound edge (the consuming conversation's). A `superseded` work_ticket may have zero inbound edges (the typical case — the prior kickoff was rewritten before the conversation opened, the rewrite consumed the new work_ticket, the prior work_ticket was never consumed by its own conversation).

The single-use enforcement is family-definitional and is what distinguishes work_ticket from reference_book at the schema level. A `reference_book` may have many inbound `workstream_planned_in_reference_book` edges (one per workstream citing it as master plan), many generic citations from conversations and other governance entities, and so on. A `work_ticket` may have at most one inbound consumption edge from a conversation, full stop.

#### 3.4.5 Supersession-requires-edge rule

Setting `work_ticket_status` to `superseded` requires the record to have an outgoing reference edge of kind `supersedes` to another work_ticket record. The access layer enforces this as a single combined validation, identical to workstream's, conversation's, and reference_book's supersession-requires-edge patterns:

- POST or PATCH setting `status = 'superseded'` without an outgoing `supersedes` edge: HTTP 422 `{"error": "supersession_requires_successor_edge"}`.
- The edge may be supplied in the same request body.
- DELETE on the `supersedes` edge while the source record still has `status = 'superseded'`: HTTP 422 `{"error": "superseded_work_ticket_requires_supersedes_edge"}`.

#### 3.4.6 Kind enum semantics

Each value of the closed kind enum:

- `kickoff_prompt` — A prompt that opens a Claude.ai conversation. The dominant family — every conversation in the project's history was opened against a file of this kind. Examples: `schema-design-kickoff-work-ticket.md` (this conversation's kickoff), `ui-v0.4-planning-prompt.md`, `governance-entity-schema-workstream-establishing-kickoff.md`, `methodology-schemas-cbm-paper-test-kickoff.md`. Filename conventions vary across the project's history; the kind is captured here as the structural classification independent of naming.
- `claude_code_prompt` — A prompt that drives a Claude Code execution against a specific change set. Covers both apply-close-out variants (`CLAUDE-CODE-PROMPT-apply-close-out-ses-*.md`, `CLAUDE-CODE-PROMPT-apply-DEC-*.md`, `CLAUDE-CODE-PROMPT-apply-PI-*.md`, `CLAUDE-CODE-PROMPT-apply-status-update-*.md`) and slice-execution variants (`CLAUDE-CODE-PROMPT-v2-ui-*.md`, `CLAUDE-CODE-PROMPT-multi-tenancy-routing-fix-*.md`). The further subdivision into "apply" versus "build" subkinds is captured in the work_ticket's title and description rather than as a sub-enum; the operational distinction is querying by file-naming pattern, which the description's free text covers without storage cost.
- `ad_hoc_prompt` — A single-use prompt that does not fit the named kinds. Catches one-off seed prompts written outside the established conventions — for example, a quick instruction prompt to Claude or Claude Code for a non-recurring task. The category is intentionally narrow; most work_tickets fit `kickoff_prompt` or `claude_code_prompt`, and the `ad_hoc_prompt` value should be used sparingly.
- `other` — Sentinel for kinds that emerge in operation and do not fit the named values. The intent is that real use will surface additional structurally-distinct kinds (for example, the Cleveland Business Mentors `SESSION-PROMPT-*` and `UPDATE-PROMPT-*` file conventions named in the project's memory) and that those kinds will be added to the enum in a future migration rather than collapsed into `other` permanently. The sentinel is the documented escape hatch; a future release may expand the enum if the `other` bucket grows beyond a few records.

The `kickoff_prompt` versus `claude_code_prompt` distinction is the most operationally meaningful axis (the two families have different downstream consumers — one opens Claude.ai conversations, the other drives Claude Code executions); the master pane's Kind column surfaces this directly. The CBM `SESSION-PROMPT-*` and `UPDATE-PROMPT-*` convention is captured as `kickoff_prompt` in this release with the document-create-versus-document-update distinction recorded in the title or description; if those families grow enough to warrant first-class enum values, a future release adds them.

#### 3.4.7 Soft-delete semantics

Default V2 base behavior. `work_ticket_deleted_at` set on DELETE; soft-deleted records do not appear in `GET /work-tickets` by default; `?include_deleted=true` reveals them; POST `/restore` clears `work_ticket_deleted_at` and restores them to the active list. Soft-delete is administrative (the record is removed from the active view, typically used to undo an erroneous creation) and is distinct from both `cancelled` status (a lifecycle outcome — the work_ticket was abandoned without being consumed) and `consumed` status (a successful-use outcome — the conversation opened against it). A record that is both `consumed` and soft-deleted is a consumed work_ticket whose record was also administratively removed; restore puts it back with status still `consumed`.

### 3.5 API Surface

#### 3.5.1 Endpoints

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/work-tickets` | — | List active work tickets; `?include_deleted=true` shows soft-deleted; `?kind=<value>` filters by kind; `?status=<value>` filters by status. |
| GET | `/work-tickets/{identifier}` | — | Single fetch by identifier. |
| POST | `/work-tickets` | full work_ticket JSON; identifier optional | Create. Identifier server-assigned when omitted. Default `work_ticket_status` is `drafted` if omitted. The body may include a `references` array; if it includes an inbound `conversation_opens_against_work_ticket` edge (typically supplied by the conversation entity's coordinated POST/PATCH, not by direct work_ticket POST), the access layer validates the single-use rule and the consumed-requires-edge rule together at commit time. |
| PUT | `/work-tickets/{identifier}` | full work_ticket JSON | Full replace. Status-transition validation per section 3.4. |
| PATCH | `/work-tickets/{identifier}` | partial work_ticket JSON | Partial update. Same validation as PUT for any field touched. Coordinated edge-and-status updates (e.g., transition to `consumed` plus the matching consumption edge) are admitted in a single PATCH payload. |
| DELETE | `/work-tickets/{identifier}` | — | Soft-delete; sets `work_ticket_deleted_at`. |
| POST | `/work-tickets/{identifier}/restore` | — | Clears `work_ticket_deleted_at`. 422 if not currently soft-deleted. |
| GET | `/work-tickets/next-identifier` | — | Returns `{"next": "WT-NNN"}` for the next available value. Used by clients computing the identifier client-side, e.g., the desktop New Work Ticket dialog. |

No deviations from the standard endpoint set. The list endpoint adds the `?kind=` and `?status=` filter parameters, parallel to `reference_book.md`'s pattern; the filters cover the most common browse cases (the Status filter is the primary operational use, per the kickoff's note that browse-by-status is the work_ticket's natural pattern).

#### 3.5.2 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission. The helper endpoint `GET /work-tickets/next-identifier` exposes the same computation for clients that need the identifier before submitting (e.g., the desktop dialog populating a read-only Identifier label).

All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

### 3.6 User Interface Considerations

Default layout per spec guide section 3.6, with two natural additions paralleling `reference_book.md`'s pattern: a Kind column in the master pane (because kind is the most operationally meaningful classification for browsing the work_ticket catalog) and a Status filter combo in the master-pane toolbar (because browse-by-status is the work_ticket's natural pattern per the kickoff's note). Both follow naturally from this spec's field inventory and do not constitute architectural deviation.

#### 3.6.1 Sidebar

The Work Tickets panel goes in the Governance sidebar group, immediately after Reference Books in workstream order. Position within the new-six set is the build-planning conversation's call; the working assumption remains that the six new entities sit at the end of the existing Governance group in workstream order (workstream first, then conversation, reference book, work ticket, close-out payload, deposit event).

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with five columns — one more than workstream's four, with Kind added because kind is the most operationally meaningful classification for browsing the work_ticket catalog (consultants ask "what apply-close-out prompts are queued" or "what kickoffs are ready").

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `work_ticket_identifier` | Identifier | narrow | Sortable; default sort. |
| `work_ticket_title` | Title | wide | Project-language title. |
| `work_ticket_kind` | Kind | medium | Enum value rendered as a friendly label (e.g., "Kickoff prompt" instead of `kickoff_prompt`). |
| `work_ticket_status` | Status | narrow | Enum value rendered as-is. |
| `work_ticket_updated_at` | Updated | narrow | Localized date/time. |

Default sort: identifier ascending. Filter controls in the panel toolbar: a kind selector (filters by `?kind=`) and a status selector (filters by `?status=`). Both default to "all"; the status selector is the primary operational filter (a consultant browsing the work ticket catalog typically wants to see what is `ready` to be opened). Right-click context menu offers New / Edit / Delete / Restore, consistent with the user-interface version 0.3 governance-entity panels per DEC-035 and DEC-036.

**Default sort by identifier, not by status.** The kickoff's hint that "A status-first column ordering may suit better than the default identifier-first" is partially adopted: Status is the fourth column (not the second) and the default sort remains identifier ascending. The browse-by-status pattern is served by the Status filter combo in the toolbar — a consultant who wants to see only `ready` work_tickets selects `ready` from the combo, and the resulting filtered list is sorted by identifier ascending within the filter. This pattern matches `reference_book.md`'s handling of the parallel question (status not in the master pane by default; toolbar combo serves explicit filtering); cross-spec consistency on default sort is preserved.

#### 3.6.3 Detail pane

Vertical layout, fields in section-3.2 order:

1. `work_ticket_identifier` — read-only label.
2. `work_ticket_title` — single-line text editor.
3. `work_ticket_description` — multi-line text editor with placeholder "Paragraph describing the work_ticket — what conversation it kicks off, what deliverables that conversation produces."
4. `work_ticket_notes` — multi-line text editor under a collapsible "Internal notes" section header, collapsed by default. The collapsed default reinforces that the field is internal consultant scratchpad.
5. `work_ticket_kind` — combo box with the four enum values rendered as friendly labels.
6. `work_ticket_file_path` — single-line text editor with placeholder "Repo-relative path, e.g., `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md`". No file-system existence validation in this release; the value is stored verbatim after trim.
7. `work_ticket_status` — combo box with the five enum values; the combo's selectable subset at any moment is the union of `{current_status}` and the valid successors of the current status per section 3.4.1, so the user cannot select an invalid transition. Server-side validation is the final gate; the combo's filtering is a UX convenience.
8. **Lifecycle timestamps section** — read-only labels rendered only for the timestamps that are non-null, paralleling workstream's and conversation's pattern. A `drafted` work_ticket sees no lifecycle timestamps; a `ready` one sees Ready At; a `consumed` one sees Ready At and Consumed At; a `cancelled` one sees Cancelled At and (optionally) Ready At; a `superseded` one sees Superseded At and (optionally) Ready At. The conditional rendering mirrors the underlying nullable columns and keeps the detail pane clean.
9. `ReferencesSection` widget — renders the outbound `supersedes` edge (when present), outbound generic `references` and `is_about` edges (kickoff read-list citations to reference books and other governance entities), inbound `conversation_opens_against_work_ticket` edge (when present — typically displayed prominently as "Consumed by: CONV-NNN" since it is the family-defining relationship), inbound generic citations from session records and other governance entities. The "Add reference" affordance from the user-interface version 0.3 references-create dialog filters available kinds and target entity types by the strict vocab per `_kinds_for_pair`.

#### 3.6.4 Create dialog

Modal `EntityCrudDialog` subclass with field order matching the detail pane. Specifics:

- `work_ticket_identifier` not shown in create mode (server-assigned).
- `work_ticket_kind` required; no default; the user must select one of the four enum values.
- `work_ticket_status` defaults to `drafted`; the user may select a different starter value for backfill of historical records — for example, when creating a work_ticket record for a kickoff that was consumed before this entity type existed, the user can set status directly to `consumed` and the create endpoint accepts the matching inbound `conversation_opens_against_work_ticket` edge plus the user-supplied `work_ticket_consumed_at` timestamp for the backfill case. Backfill behavior is access-layer-detected by the absence of intermediate transitions and is documented as part of section 3.8 (Open questions — retroactive backfill).
- `work_ticket_file_path` required.
- Required-field validation client-side before submit.
- Server-side validation errors (uniqueness, format, transition, consumed-requires-edge, single-use, supersession-requires-edge) surface inline.

#### 3.6.5 Edit dialog

Same shape as create. `work_ticket_identifier` displayed as read-only label. Status transitions enforced per section 3.4.1; the combo box restricts selectable values to valid transitions plus the current value (no-op). Setting status to `consumed` requires the inbound `conversation_opens_against_work_ticket` edge to be present; the edit dialog detects this and surfaces a hint inline if the edge is missing ("This work ticket has no consuming conversation yet — add the consumption edge via the References section before transitioning to Consumed."). Setting status to `superseded` requires an outgoing `supersedes` edge to be present (added via the ReferencesSection's "Add reference" affordance before the status change is committed, or via the same patch payload); attempting to commit `superseded` without the edge surfaces the 422 inline.

#### 3.6.6 Delete dialog

`EntityCrudDeleteDialog` with edge-text confirmation. The user types the `work_ticket_identifier` value (e.g., `WT-002`) to enable the Delete button, matching the user-interface version 0.3 governance-entity patterns. Confirmation soft-deletes the record.

### 3.7 Acceptance Criteria

The following sixteen statements define what "this entity type is correctly implemented in the eventual build" looks like. Each is concrete and testable; the build-planning conversation translates these into specific test cases.

1. **Schema migration applies cleanly.** Alembic migration creates the `work_tickets` table with all eleven columns (`work_ticket_identifier`, `work_ticket_title`, `work_ticket_description`, `work_ticket_notes`, `work_ticket_kind`, `work_ticket_status`, `work_ticket_file_path`, `work_ticket_created_at`, `work_ticket_updated_at`, `work_ticket_deleted_at`, `work_ticket_ready_at`, `work_ticket_consumed_at`, `work_ticket_cancelled_at`, `work_ticket_superseded_at`), correct types and constraints, and runs both forward and backward without error.

2. **`work_ticket_identifier` format constraint enforced.** Insertions with `work_ticket_identifier` not matching `^WT-\d{3}$` raise a validation error at the access layer.

3. **`work_ticket_title` uniqueness enforced case-insensitively within the engagement.** Inserting a second row whose `work_ticket_title` matches an existing row by lowercase comparison raises a uniqueness violation.

4. **`work_ticket_kind` enum validation.** Insertions with `work_ticket_kind` outside the four-value enum (`kickoff_prompt`, `claude_code_prompt`, `ad_hoc_prompt`, `other`) are rejected at the access layer.

5. **`work_ticket_status` enum and transition validation.** Insertions with `work_ticket_status` outside the five-value enum are rejected. PATCH or PUT requesting an invalid transition (e.g., `consumed` → `ready`) returns HTTP 422 with `{"error": "invalid_status_transition", "from": ..., "to": ...}`.

6. **Terminal states are truly terminal.** All three terminal statuses (`consumed`, `cancelled`, `superseded`) reject every outgoing transition, including transitions between terminal states (e.g., `cancelled` → `superseded`, `consumed` → `superseded`). Same 422 shape.

7. **Consumed-requires-edge rule.** POST or PATCH setting `work_ticket_status = 'consumed'` without an inbound `conversation_opens_against_work_ticket` edge from a conversation record returns HTTP 422 with `{"error": "consumed_work_ticket_requires_consumption_edge"}`. The edge may be supplied via the consuming conversation's coordinated POST/PATCH in the same transaction. Deletion of an existing inbound `conversation_opens_against_work_ticket` edge on a `consumed`-status record returns the parallel 422.

8. **Single-use enforcement.** Attempting to add a second inbound `conversation_opens_against_work_ticket` edge to a work_ticket that already has one returns HTTP 422 with `{"error": "work_ticket_single_use_violation"}`. The rule applies regardless of the work_ticket's current status.

9. **Supersession-requires-edge rule.** POST or PATCH setting `work_ticket_status = 'superseded'` without an outgoing `supersedes` edge to another work_ticket record returns HTTP 422 with `{"error": "supersession_requires_successor_edge"}`. The edge may be supplied in the same request body. Deletion of an existing `supersedes` edge on a `superseded`-status record returns the parallel 422.

10. **Lifecycle timestamps server-set on transition.** `work_ticket_ready_at` is set when status transitions to `ready`; `work_ticket_consumed_at` when to `consumed`; `work_ticket_cancelled_at` when to `cancelled`; `work_ticket_superseded_at` when to `superseded`. Each is idempotent — a second update setting the same status does not change the timestamp. Each is mutually exclusive at the three-terminal level (exactly one of `_consumed_at`, `_cancelled_at`, `_superseded_at` is non-null on a terminal record). Client-supplied values for these columns are ignored on PUT and PATCH except in the documented backfill case (create with terminal status accepts user-supplied terminal timestamp).

11. **`work_ticket_file_path` repo-relative validation enforced.** Insertions with a leading slash, `..` segments, or scheme prefix (e.g., `http://`, `file://`) are rejected at the access layer. Uniqueness within the engagement is enforced case-sensitively (file paths are case-sensitive in the underlying filesystem). The same `file_path` value may coexist in a `reference_book` record in the same engagement; the work_ticket-side uniqueness check is against the work_tickets table only.

12. **Access-layer methods exist with expected signatures.** `client.list_work_tickets()`, `client.get_work_ticket(identifier)`, `client.create_work_ticket(...)`, `client.update_work_ticket(identifier, ...)`, `client.patch_work_ticket(identifier, ...)`, `client.delete_work_ticket(identifier)`, `client.restore_work_ticket(identifier)`, `client.next_work_ticket_identifier()` exist and pass unit tests covering happy path and at least one error case each.

13. **REST endpoints return expected responses for representative cases.** All eight endpoints from section 3.5 return correct HTTP status and JSON bodies for happy-path and validation-failure cases; 4xx errors use the V2 `{data, meta, errors}` envelope per `crmbuilder-v2/src/crmbuilder_v2/api/envelope.py`. List endpoint correctly filters by `?kind=` and `?status=` query parameters and combines them additively (filtering by both narrows the result set).

14. **Identifier auto-assignment helper returns next ID without race conditions.** `GET /work-tickets/next-identifier` returns `{"next": "WT-NNN"}` for the next available number. POST with `work_ticket_identifier` omitted assigns the same value. Two concurrent POSTs do not assign the same identifier.

15. **Soft-delete and restore round-trip correctly.** DELETE sets `work_ticket_deleted_at`; the record disappears from `GET /work-tickets`. `GET /work-tickets?include_deleted=true` shows it. POST `/restore` clears `work_ticket_deleted_at`; the record reappears. Restore on a record that is not soft-deleted returns 422.

16. **End-to-end backfill of this conversation's work_ticket.** A consultant can author a `work_ticket` record for this conversation's kickoff (`schema-design-kickoff-work-ticket.md`) through the New Work Ticket dialog with kind `kickoff_prompt`, status `consumed`, `work_ticket_consumed_at` backfilled to a plausible historical value, and the inbound `conversation_opens_against_work_ticket` edge pointing at the conversation record for this schema-design conversation (CONV-NNN once the conversation backfill lands per PI-022). The work_ticket record persists across application restart and across REST/MCP refetch. The consultant can subsequently browse the catalog filtered by `kind=kickoff_prompt`, find this record, and follow the inbound edge to the consuming conversation.

### 3.8 Open Questions and Deferred Decisions

Categorized per the spec guide section 3.8 convention. Each entry is one paragraph with an explicit category tag.

#### 3.8.1 For the build-planning conversation to settle

**[build] Sidebar grouping for the six new governance entities.** Inherited from `workstream.md` section 3.8.1 and `conversation.md` section 3.8.1 and `reference_book.md` section 3.8.1. The existing Governance group has eight entries; adding six more makes the group thirteen entries deep. Build-planning decides whether to introduce a sub-grouping (e.g., "Governance — workflow" for the six new ones) or accept the longer list as-is. This spec declares default position; build-planning may overrule.

**[build] Migration ordering across the six schemas.** Inherited from `workstream.md` section 3.8.1. Each governance schema requires its own Alembic migration creating the entity table; the references-vocab additions are consolidated into one migration across the six specs. Sequencing those migrations safely is build-planning's call. Work_ticket adds only the entity type to `ENTITY_TYPES` (no new relationship kinds); the consolidated vocab migration handles work_ticket's contribution alongside the other five specs'.

**[build] Backfill behavior on create with terminal status.** Inherited from `workstream.md` section 3.8.1. This spec admits the backfill-create case; the detailed validation behavior (whether terminal-timestamp ordering is enforced — e.g., `_consumed_at` ≥ `_ready_at` if both are supplied; whether the backfill case requires a special flag in the request payload; whether the inbound consumption edge must be supplied in the same transaction as the create or may be supplied in a follow-up coordinated PATCH from the conversation side) is left to build-planning. The minimum-viable rule documented here is "create with terminal status accepts user-supplied terminal timestamp; non-create transitions reject user-supplied timestamps and server-set them; the consumed-requires-edge rule applies in both cases."

**[build] Coordinated multi-record transaction for the consumed transition.** The consumed-requires-edge rule requires the inbound `conversation_opens_against_work_ticket` edge to be present when work_ticket transitions to `consumed`. The conversation entity's complete-requires-session-edge rule requires the outbound `conversation_records_session` edge to be present when conversation transitions to `complete`. The natural workflow at conversation close is: (a) conversation status transitions to `complete`, (b) work_ticket status transitions to `consumed`, (c) the inbound edge to work_ticket and the outbound edge to session are coordinated with both status transitions. Build-planning specifies whether the close-out apply script handles this as one transaction (all-or-nothing across both entity tables and the references table) or as a sequence of coordinated single-entity transactions, and how the access layer surfaces partial-failure cases.

**[build] Distinguishing apply-close-out vs slice-execution within `claude_code_prompt`.** The `claude_code_prompt` kind covers both apply-close-out variants and slice-execution variants. Build-planning may decide to introduce a sub-enum or a separate `apply_prompt` kind value if querying by this distinction becomes routine. The minimum-viable posture in this release keeps the four-value enum and captures the distinction in the title and description as free text; the `prompts/` directory's filename pattern (`apply-close-out-ses-*.md` versus `v2-ui-v0.X-Y-*.md`) is the de facto signal today.

#### 3.8.2 For retroactive backfill (PI-022) to surface

**[backfill] Historical work_ticket records for prior kickoff prompts and Claude Code prompts.** PI-022 covers retroactive population of work_ticket records for prior single-use seed documents — every kickoff prompt at the root of `PRDs/product/crmbuilder-v2/` (and the analogous CBM locations) and every `CLAUDE-CODE-PROMPT-*.md` under `prompts/`. The retroactive records require historical lifecycle timestamps; the backfill pass decides which dates to use (commit dates for `_ready_at`, the date of the consuming conversation's session record for `_consumed_at`) and resolves any ambiguity case-by-case. Most prior work_tickets are `consumed` (their conversations ran); a few are `cancelled` (the conversation was scrapped); a few are `superseded` (the kickoff was rewritten before the conversation opened, with the prior file retained in git history). PI-022's resolution determines the policy.

**[backfill] The methodology workstream master plan boundary case.** The kickoff explicitly raised the question of whether `ui-v0.4-planning-prompt.md` — the kickoff that opened SES-011, the planning conversation whose deliverable was the methodology workstream master plan — is a work_ticket or a reference_book. This spec's section 2 boundary discipline resolves it as a work_ticket (intent at creation was single-use; the retroactive forward-referencing by successor planning documents is archival mention, not authoritative re-reading). PI-022's backfill pass authors a work_ticket record for it with kind `kickoff_prompt`, status `consumed`, and the inbound consumption edge pointing at the SES-011 conversation's record. If a real authoritative-reference pattern emerges later, a separate reference_book record is authored against the same `file_path` per the section-2 boundary discipline; the two records co-exist.

**[backfill] Conversations whose kickoff is missing or unrecoverable.** A small number of prior conversations may have no recoverable kickoff prompt — for example, an ad-hoc conversation opened against a verbal description rather than a kickoff file. PI-022 decides whether such conversations are backfilled with a synthetic `ad_hoc_prompt` work_ticket record (capturing the verbal description in `work_ticket_description`) or whether the conversation backfill record simply has no outbound `conversation_opens_against_work_ticket` edge (the conversation entity's section 3.3.1 makes the edge required-when only past `kickoff_drafted` status; a `planned` conversation with no kickoff is admissible, and a backfilled `complete` conversation with no kickoff is a backfill-policy edge case).

**[backfill] Single-use enforcement against historical multi-consumer files.** A small number of prior kickoff-shaped files may have been used by more than one conversation in their lifetime — for example, if a planning prompt was reopened in a second Claude.ai session after the first session timed out. The single-use rule in this spec's section 3.4.4 prohibits multiple inbound consumption edges per work_ticket. PI-022's backfill pass decides whether such cases are backfilled as one work_ticket with the first consumption edge and a `references` edge for the second consumption (capturing the multi-use as a generic citation rather than a typed consumption), or as two work_ticket records with different identifiers pointing at the same `file_path` (each with its own typed consumption edge to the matching conversation). The schema admits the second approach via per-table uniqueness on `file_path` only; the policy decision is PI-022's.

#### 3.8.3 For a future release

**[future] Sub-kind enum for `claude_code_prompt`.** Not introduced in this release. The current single enum value covers both apply-close-out and slice-execution Claude Code prompts; if querying by sub-kind becomes routine (consultants asking "what apply-close-out prompts are queued" versus "what slice prompts are pending"), a future release adds a `work_ticket_sub_kind` column with the matching enum constrained by parent `work_ticket_kind`.

**[future] First-class enum values for CBM `SESSION-PROMPT-*` and `UPDATE-PROMPT-*` conventions.** The Cleveland Business Mentors engagement uses file-naming conventions (`SESSION-PROMPT-*` for new-document seeds, `UPDATE-PROMPT-*` for modification seeds) that this spec captures under `kickoff_prompt` with the distinction recorded in title or description. If those families grow enough to warrant their own enum values (`session_prompt`, `update_prompt`), a future release adds them via additive migration; the existing records remain `kickoff_prompt` until reclassified.

**[future] Author / owner tracking.** Not introduced. Doug is sole author and owner of every work_ticket; Claude is co-author at session close. If multi-author engagements emerge, the column is one migration away.

**[future] Path-existence validation.** Not introduced. The build prompt may add a "check path resolves" verification step that runs at write time and surfaces a warning (not a hard error) if the path does not resolve in the consuming repository. The minimum-viable posture stores the path verbatim after trim and defers existence checking to the consuming consultant or downstream automation.

**[future] Content blob storage and full-text search.** Not introduced. Mirrors `reference_book.md`'s deferral. The file lives in git; the database tracks metadata. If full-text search across work_tickets becomes a routine query, a future release adds an indexed content column with the matching write-through-on-file-change automation.

**[future] Deliverable-checklist field.** Not introduced. The work_ticket's intended deliverables are captured in `work_ticket_description` as free text. If a structured checklist (e.g., "produces a Word document at path X, a Python migration at path Y, a session record with topics A and B covered") becomes valuable for verification queries ("did the consuming conversation produce all the deliverables the kickoff named?"), a future release adds the column with the matching access-layer support.

**[future] Pause / resume / hold lifecycle states.** Parallel to workstream's and conversation's deferred pause/resume question. Work_ticket's lifecycle is forward-only with truly terminal terminals. If real operational signal supports a pause-and-resume case (a work_ticket whose drafting was paused mid-authoring), a future release may admit a `paused` status with transitions back to `drafted`. The minimum-viable posture preserves the timeline semantics by treating pauses as a free-text concern (note in `work_ticket_notes`).

**[future] Typed read-list edge `work_ticket_reads_reference_book`.** Deferred per DEC-133's frequency-justified test. The generic `references` kind covers read-list citations adequately in this release. If queries by read-list become routine ("what work_tickets read reference book RB-042?"), a future release adds the typed kind with the matching vocab and access-layer support. The retrofit is one vocab.py line plus a backfill pass converting existing generic `references` edges (work_ticket → reference_book) to the typed kind.

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_051.json` at conversation close. Each is linked to SES-051 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-141 through DEC-146) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-141 — `work_ticket` identifier prefix and format: `WT-NNN`, two-letter form, no collision with existing or pending prefixes.** Adopts `WT` as the prefix; confirms two-letter form acceptable per DEC-123's affirmation; resolves the kickoff's working assumption in favour of `WT` over `WKT`, `TIX`, `TKT`.
- **DEC-142 — `work_ticket` boundary discipline with `reference_book`: intent-at-creation classification, no in-place re-categorization, file_path may coexist across both tables.** Resolves the kickoff's three-way boundary question (bright line by intent, bright line by lifecycle, re-categorization) in favour of the first option with explicit support for parallel co-existence of work_ticket and reference_book records pointing at the same `file_path`. The methodology workstream master plan example stays a work_ticket; retroactive citation is archival, not authoritative.
- **DEC-143 — `work_ticket` workflow-shaped lifecycle with five statuses, truly terminal terminals, consumed-requires-edge rule, and supersession-requires-edge rule.** Adopts `drafted` / `ready` / `consumed` / `cancelled` / `superseded` with the transition map of section 3.4.1, the truly-terminal posture inherited from workstream and conversation, and the supersession-requires-edge rule mirroring the pattern from prior specs. Establishes the new cross-spec precedent of terminal-state consumption requiring the inbound consumption edge (consumed-requires-edge), the inverse of supersession-requires-edge, applicable to close_out_payload's anticipated `applied` terminal.
- **DEC-144 — `work_ticket` single-use enforcement: at most one inbound `conversation_opens_against_work_ticket` edge per work_ticket, regardless of status.** Realizes DEC-117's family-2 definition (single-use seed documents have at most one consumer) as a schema-level rule. The single-use enforcement is what distinguishes work_ticket from reference_book at the schema level; reference_book admits arbitrarily many inbound edges per record.
- **DEC-145 — `work_ticket` field inventory including four per-status lifecycle timestamps, declines tentative `work_ticket_consumed_by_conversation` kind, declines typed `work_ticket_reads_reference_book` kind.** Captures the eleven-column shape (identity, content, classification, no FK fields, file pointer, base plus four per-status lifecycle timestamps) per section 3.2. Declines the tentative inbound kind named by `conversation.md` section 3.3.2 as redundant — the existing `conversation_opens_against_work_ticket` edge is the sole canonical edge, viewed from work_ticket's side as inbound. Declines the typed read-list kind per DEC-133's frequency-justified test in favour of the generic `references` kind.
- **DEC-146 — `work_ticket` API surface, UI defaults with Kind column and Status filter combo, soft-delete posture, kind enum semantics, acceptance criteria.** Standard endpoint set with no deviations; default UI layout with Kind column (operationally meaningful classification, parallel to reference_book) and Status filter combo (browse-by-status pattern per kickoff); default soft-delete with restore; closed four-value kind enum (`kickoff_prompt`, `claude_code_prompt`, `ad_hoc_prompt`, `other`) with `other` as sentinel; sixteen acceptance criteria captured.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the next two schema-design conversations.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-work-ticket.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — first per-entity schema spec; source of the three foundational cross-spec precedents (references-edge over FK, per-status lifecycle timestamps for workflow lifecycles, terminal-states-are-terminal).
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` — second per-entity schema spec; source of the typed-sequencing-frequency-justified precedent; declarer of the inbound `conversation_opens_against_work_ticket` edge this spec inherits.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md` — third per-entity schema spec; source of the documentary-shaped-lifecycles-inherit-base-timestamps-only precedent and the contrast class against which work_ticket's single-use family-2 semantics are defined.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `work_ticket` records live in the per-engagement database.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary the new entity type registers against.
- `PRDs/process/conduct/charter.md`, `kickoff.md`, `question-library.md` — conduct framework documents; structurally the contrast class as long-lived multi-consumer references (reference_book candidates), reinforcing the boundary discipline this spec articulates in section 2.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` — canonical apply-prompt exemplar cited by the kickoff and by the methodology guide as the canonical post-fix close-out apply script.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. **Most directly extended.** `work_ticket` is family 2 (single-use seed documents with at most one consumer). This spec's single-use enforcement rule (section 3.4.4) is the schema-level realization of DEC-117's family-2-defining property.
- **DEC-118** — Two entities within the deposit bucket family. Not directly extended; the deposit-bucket family is families 3 (close_out_payload) and 4 (deposit_event), designed in the fifth and sixth schema-design conversations.
- **DEC-119** — Add a conversation entity. The conversation→work_ticket consumption edge declared in `conversation.md` as `conversation_opens_against_work_ticket` is the canonical edge this spec inherits as inbound.
- **DEC-120** — Add a workstream entity. The workstream→work_ticket relationship is via the conversation chain (workstream → conversation → work_ticket), not via a direct edge; this spec does not extend DEC-120 directly.
- **DEC-121** — Single-source-of-truth coverage extension. `work_ticket` makes the single-use seed document concept machine-resolvable; queries like "what kickoffs are queued up" and "what work_tickets has the methodology workstream consumed" become first-class without filesystem scanning of file naming patterns.
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. Work_ticket is soft-delete-with-restore rather than append-only because the parent record is organizing metadata (the kickoff's identity, kind, lifecycle), not transactional fact; the file content itself lives in git and is the immutable transactional artifact.
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.9.1's reliance on the close-out payload's apply script and the session record as the durable artifacts of this conversation.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail pane reference rendering in section 3.6.3, including the prominent display of the inbound `conversation_opens_against_work_ticket` edge as the family-defining relationship.
- **DEC-033** — Cascading reference create dialog driven by strict vocab. The work_ticket entity's outbound `supersedes` plus the generic `is_about`/`references` defaults all flow through the existing dialog without modification.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master pane patterns in section 3.6.2 including the addition of the Kind column and the toolbar filter combos.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields prefixed `work_ticket_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited. The declined `work_ticket_consumed_by_conversation` tentative kind would have followed the convention; declining it preserves the one-edge-per-relationship pattern across the workstream.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `work_ticket` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.
- **DEC-123 through DEC-128** — All six decisions from SES-048 (the workstream schema-design conversation). DEC-123 affirms the two-letter `WT` prefix is acceptable. DEC-124's references-edge cross-spec precedent applies to all of this spec's relationships. DEC-125's truly-terminal and supersession-requires-edge patterns are inherited verbatim; the new consumed-requires-edge rule is the inverse pattern locked here. DEC-126's per-status lifecycle timestamps precedent applies (work_ticket is workflow-shaped). DEC-127's flat-catalog posture is structurally analogous to this spec's no-hierarchy posture. DEC-128's standard-defaults posture is what this spec uses for API surface, UI layout, soft-delete, and acceptance-criteria framing.
- **DEC-129 through DEC-134** — All six decisions from SES-049 (the conversation schema-design conversation). DEC-130's references-edge precedent for parent-child relationships applies (work_ticket's inbound consumption edge from conversation is references-edge per the precedent). DEC-131's lifecycle patterns inform this spec's workflow-shaped five-state lifecycle. DEC-132's tentative-kind-name resolution is the precedent for this spec's decline of the tentative `work_ticket_consumed_by_conversation` kind named by conversation.md section 3.3.2. DEC-133's typed-sequencing-frequency-justified precedent is applied here to defer the typed read-list kind. DEC-134's standard-defaults-with-natural-additions posture is what this spec uses for API surface and UI layout.
- **DEC-135 through DEC-140** — All six decisions from SES-050 (the reference_book schema-design conversation). DEC-135 affirms each downstream conversation makes its own prefix-length call (two-letter `WT` is fine). DEC-137's documentary-vs-workflow distinction is the precedent this spec applies on its own facts — work_ticket is workflow-shaped (not documentary), so per-status lifecycle timestamps apply per DEC-126. DEC-138's closed kind enum with `other` sentinel is the structural pattern this spec follows for its four-value kind enum. DEC-139's repo-relative file path semantics are inherited verbatim, with the additional cross-table coexistence rule (the same `file_path` may exist in both `work_ticket` and `reference_book` records) added by this spec's section-2 boundary discipline. DEC-140's standard-API-with-natural-UI-additions posture is what this spec uses (Kind column, Status filter combo).

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-050 — reference_book schema-design conversation. Third per-entity schema-design conversation in the governance entity schema-design workstream. Locked the documentary-vs-workflow distinction this conversation applies on its own facts (work_ticket is workflow-shaped) and defined the contrast class (reference_book as long-lived multi-consumer) against which work_ticket's single-use family-2 semantics are defined.
- **Successor:** `close_out_payload` schema-design conversation. Kickoff at `PRDs/product/crmbuilder-v2/schema-design-kickoff-close-out-payload.md`. Inherits the six cross-spec precedents now in force: the three from workstream (references-edge over FK, per-status lifecycle timestamps for workflow lifecycles, terminal-states-are-terminal), the one from conversation (typed sequencing introduced when entity-family frequency justifies), the one from reference_book (documentary-shaped lifecycles inherit base timestamps only), and the one from this conversation (terminal-state consumption requires the inbound consumption edge). The close_out_payload entity is structurally related to this spec only indirectly — close-out payloads are produced by conversations, not by work_tickets, but the new consumed-requires-edge precedent from this conversation is the direct precedent for close_out_payload's anticipated `applied` terminal status requiring its inbound deposit_event edge.

---

*End of document.*
