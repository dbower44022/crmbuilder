# Governance Entity Product Requirements Document — Version 0.1

**Last Updated:** 05-22-26 17:30
**Status:** Draft v0.1 — produced by the build-planning conversation (SES-055) at the close of the governance entity schema-design workstream
**Target user-interface version:** v0.7
**Predecessor workstream conversations:** SES-047 (workstream-establishing), SES-048 (workstream entity), SES-049 (conversation entity), SES-050 (reference_book entity), SES-051 (work_ticket entity), SES-052 (close_out_payload entity), SES-054 (deposit_event entity)
**Companion documents:** `governance-entity-implementation-plan.md` (slice topology, dependency order, acceptance aggregation), six per-entity schema specifications under `governance-schema-specs/`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-22-26 17:30 | Doug Bower / Claude (build-planning conversation SES-055) | Initial draft. Produced by the build-planning conversation that closes the governance entity schema-design workstream. Integrates the six per-entity schema specifications (workstream, conversation, reference_book, work_ticket, close_out_payload, deposit_event) into a single coherent release targeting user-interface version 0.7. Aggregates eight new relationship-kind vocabulary additions, six new entity types, six new entity tables, one new child table (reference_book_versions), and one reduced API surface (deposit_event POST + GET only). Documents the apply-script modification slice that integrates deposit_event creation atomically with successful applies. Refines PI-022 retroactive backfill into a phased execution plan with phase 1 (governance workstream's seven conversations) executed in Slice E and subsequent phases deferred to follow-on planning items. Sidebar grouping policy: append the six new entities to the existing Governance group in workstream order, no sub-grouping in this release. Deposit-event log file tracking policy: git-tracked under `PRDs/product/crmbuilder-v2/deposit-event-logs/`. Six decisions authored at conversation close. One known cross-spec consistency finding settled before drafting (close_out_payload.md §3.3.2 and §3.4.3 reconciled to zero-or-more inbound edge cardinality per DEC-158); two new findings surfaced and resolved as Slice A implementation concerns (references-row addressing for the deposit_event_wrote_record kind; change_log.entity_type CHECK extension). |

---

## Change Log

**Version 0.1 (05-22-26 17:30):** Initial creation. Defines the v0.7 release of CRMBuilder v2 — the governance entity release. Six new entity types (workstream, conversation, reference_book, work_ticket, close_out_payload, deposit_event) with associated tables, REST endpoints, desktop UI panels, and access-layer methods. Eight new relationship-kind vocabulary entries aggregated across the six specs. Apply script (`apply_close_out.py`) modified to write log files and POST deposit_event records atomically as its final step. PI-022 refined into a phased backfill plan; phase 1 (the seven conversations of the governance entity schema-design workstream) executes in Slice E. Sidebar grouping appends to existing Governance group. Deposit-event log files git-tracked. About-dialog version bumps to 0.7.0. Cross-spec consistency reconciliation already executed at SES-055 open: close_out_payload.md revised to v1.1 to admit zero-or-more inbound deposit_event_applies_close_out_payload edges per DEC-158. No methodology entity changes; no modifications to in-flight parallel work (multi-tenancy routing fix, styling, Cleveland Business Mentors Planning Item 001). No backward-compatibility concerns beyond incidental: the existing references-table CHECK constraint admits the new relationship kinds via Alembic migration; the existing change_log.entity_type CHECK admits the new entity types via the same migration.

---

## 1. Purpose

This Product Requirements Document specifies the v0.7 release of CRMBuilder v2 — the **governance entity release**. The release closes the gap between V2's governance database's stated single-source-of-truth role and its actual coverage of the planning-and-execution machinery itself. The release lands six new entity types that make the project's organizing units, workflow files, and apply events queryable as governance objects.

The release is the cumulative deliverable of the governance entity schema-design workstream, which produced seven prior conversations (SES-047 through SES-054, plus SES-053 as a parallel conversation outside this workstream) and six schema specifications at `PRDs/product/crmbuilder-v2/governance-schema-specs/`. This document does not re-derive the schemas — each spec is the authoritative source for its entity type. This document integrates them into a coherent release: shared infrastructure changes, sidebar placement, migration sequencing, the apply script modification that connects the deposit_event entity to the existing apply path, and the PI-022 refinement that converts the retroactive backfill planning item into a concrete execution plan.

---

## 2. Scope

### 2.1 In scope for v0.7

**Six new governance entity types**, each per its per-entity schema specification:

1. **`workstream`** (per `governance-schema-specs/workstream.md`) — coherent line of related conversations; nine fields, five-status workflow lifecycle, identifier prefix `WS`.
2. **`conversation`** (per `conversation.md`) — unit of conversational work through its full lifecycle; fifteen fields, seven-status workflow lifecycle, identifier prefix `CONV`.
3. **`reference_book`** (per `reference_book.md`) — long-lived versioned reference document; ten parent-table fields plus a sibling `reference_book_versions` child table, three-status documentary lifecycle, eleven-value kind enum, identifier prefix `RB`.
4. **`work_ticket`** (per `work_ticket.md`) — single-use seed document; eight fields plus seven timestamp columns, five-status workflow lifecycle, four-value kind enum, identifier prefix `WT`.
5. **`close_out_payload`** (per `close_out_payload.md` v1.1) — single-use state-write package produced at conversation close; six content/classification fields plus the file-pointer field plus seven timestamp columns, five-status workflow lifecycle, identifier prefix `COP`.
6. **`deposit_event`** (per `deposit_event.md`) — durable record of a close_out_payload apply attempt; nine columns (one timestamp only, no `_updated_at`, no `_deleted_at`), born-terminal append-only lifecycle, two-value outcome enum, identifier prefix `DEP`.

**Six new database tables** plus one child table (`reference_book_versions`), each with appropriate Alembic migration.

**Eight new relationship-kind vocabulary entries** aggregated into one `vocab.py` update and one Alembic migration on the `refs.relationship_kind` CHECK constraint:

| Kind | Source | Target | Declared by |
|------|--------|--------|-------------|
| `conversation_belongs_to_workstream` | `conversation` | `workstream` | conversation.md |
| `workstream_planned_in_reference_book` | `workstream` | `reference_book` | workstream.md |
| `conversation_records_session` | `conversation` | `session` | conversation.md |
| `conversation_opens_against_work_ticket` | `conversation` | `work_ticket` | conversation.md |
| `conversation_succeeds_conversation` | `conversation` | `conversation` | conversation.md |
| `close_out_payload_produced_by_conversation` | `close_out_payload` | `conversation` | close_out_payload.md |
| `deposit_event_applies_close_out_payload` | `deposit_event` | `close_out_payload` | deposit_event.md |
| `deposit_event_wrote_record` | `deposit_event` | `session` / `decision` / `planning_item` / `reference` | deposit_event.md |

The existing generic kinds (`is_about`, `references`, `supersedes`, `decided_in`) are reused for all generic and same-type-supersession relationships across the new entities; no additions to those.

**Six new sidebar entries** in the desktop application's Governance sidebar group, appended in workstream order after the existing eight Governance entries (charter, status, decisions, sessions, risks, planning items, topics, references). The resulting group is fourteen entries. The build-planning conversation decided against sub-grouping in this release (see Decision Record DEC-163 below).

**REST API endpoint set** for each entity type, with reduced surface for deposit_event:

- Workstream, conversation, reference_book, work_ticket, close_out_payload: standard eight-endpoint set per each spec (list, get, post, put, patch, delete, restore, next-identifier).
- Reference_book: plus three version-management sub-endpoints (`GET /reference-books/{id}/versions`, `POST /reference-books/{id}/versions`, `GET /reference-books/{id}/version-at?as_of=...`).
- Deposit_event: reduced to two endpoints only (POST `/deposit-events`, GET `/deposit-events` and `GET /deposit-events/{identifier}`), per born-terminal append-only posture. No PUT, PATCH, DELETE, or restore.

**Apply script modification** at `crmbuilder-v2/scripts/apply_close_out.py`: the script is modified to write its stdout to a log file under `deposit-event-logs/`, capture per-record HTTP outcomes for the `records_summary` field, and POST a deposit_event record as its last step. The POST atomically creates the deposit_event record, the outbound `deposit_event_applies_close_out_payload` edge to the target payload, the outbound `deposit_event_wrote_record` edges to each record the apply created, and (on `outcome=success` against a `ready` payload) transitions the close_out_payload from `ready` to `applied`.

**PI-022 phased backfill execution** in Slice E: phase 1 backfills the seven conversations of the governance entity schema-design workstream (SES-047, 048, 049, 050, 051, 052, 054) plus this build-planning conversation (SES-055) — eight conversations, one workstream, the eight close-out payload files at `close-out-payloads/ses_047.json` through `ses_055.json`, the eight kickoff prompts (work_tickets), and seven reference books (the workstream master plan, the spec guide, the six schema specs, this PRD, the implementation plan). Phases 2 and beyond (prior workstreams, ad-hoc conversations, historical applies as deposit_events) are deferred to follow-on planning items authored at v0.7 close.

**Deposit-event log file tracking** under `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log`, git-tracked alongside the close-out payload commits.

**About-dialog version bump** to 0.7.0; README and `crmbuilder/CLAUDE.md` v2 section updated to reflect the release.

### 2.2 Out of scope for v0.7

- Modifications to methodology entity types (domain, entity, process, crm_candidate, engagement). Those remain unchanged.
- In-flight parallel work: multi-tenancy routing fix slices, Cleveland Business Mentors Planning Item 001, any newer in-flight workstreams.
- Cleveland Business Mentors redo Phase 1 conversation (waits on CBM Planning Item 001 regardless).
- Retroactive backfill phases 2 and beyond (prior workstreams' workstream and conversation records; prior payloads' close_out_payload records; historical applies as deposit_events). Deferred to follow-on planning items.
- Future-add features explicitly named in the six schema specifications' section 3.8.3 entries: in-app log viewer; full-text search across reference books; per-target-type back-reference kind expansion; pause/resume lifecycle states; outcome summary fields on workstream and conversation; predecessor-successor non-supersession chains between workstreams; target user-interface version field on workstream; etc.

---

## 3. Architecture

### 3.1 Storage layer

Six new entity tables under SQLite plus one child table for reference_book versions. All tables follow the V2 per-engagement isolation pattern (DEC-115 / DEC-116): records live in the per-engagement SQLite file, and the CRMBuilder dogfood engagement is where the first records of each new type land. Other engagements receive the new entity types as part of their initialization once v0.7 ships.

Schema migrations are sequenced in Slice A (see implementation plan section 3.1): the references-vocab migration first (relaxes the `refs.relationship_kind` CHECK constraint to admit the eight new kinds and the `refs.source_type` / `refs.target_type` CHECK constraints plus `change_log.entity_type` CHECK constraint to admit the six new entity types); then per-entity table creation migrations in workstream order (workstream → conversation → reference_book → reference_book_versions → work_ticket → close_out_payload → deposit_events).

The `refs.source_type` and `refs.target_type` CHECK constraints, the `refs.relationship_kind` CHECK constraint, and the `change_log.entity_type` CHECK constraint are all extended in one migration. The pattern follows migration 0007's precedent (`_NEW_CHANGELOG_ENTITY_TYPE_CHECK` plus the references-table extensions in the methodology workstream).

### 3.2 Access layer

One repository module per new entity type at `crmbuilder-v2/src/crmbuilder_v2/access/repositories/`:

- `workstreams.py`
- `conversations.py`
- `reference_books.py` (and child versions logic inline)
- `work_tickets.py`
- `close_out_payloads.py`
- `deposit_events.py`

Each module exposes the standard method set (`list_*`, `get_*`, `create_*`, `update_*`, `patch_*`, `delete_*`, `restore_*`, `next_*_identifier`) with deviations per spec (deposit_event has only `list_deposit_events`, `get_deposit_event`, `create_deposit_event`, `next_deposit_event_identifier`).

Cross-cutting access-layer rules:

- **Status-transition validation.** Each entity with a status field enforces its transition map per the spec's section 3.4.1 table. Workflow-shape entities follow the truly-terminal discipline (no transitions out of terminal states; no transitions between terminal states). Documentary reference_book follows its own three-state transition map.
- **Edge-required-at-terminal rules** (DEC-125 supersession; DEC-143 work_ticket consumption; DEC-149 close_out_payload applied). Each rule is enforced at commit time, accepting in-transaction edge supply per the per-entity specs.
- **At-most-one rules** (work_ticket single-use; close_out_payload single-producer). Enforced regardless of status, at the access layer.
- **First-success-transitions semantics** (v1.1 reconciliation; close_out_payload.md §3.4.3). The first inbound `deposit_event_applies_close_out_payload` edge with `outcome=success` drives the close_out_payload's `ready → applied` transition; subsequent inbound edges admitted without further state change.
- **Atomic deposit_event POST behavior.** The POST creates the deposit_event row, the outbound `deposit_event_applies_close_out_payload` edge, the outbound `deposit_event_wrote_record` edges, and (on `outcome=success` against a `ready` payload) transitions the close_out_payload to `applied` — all in one transaction.

### 3.3 REST API

One router module per new entity type at `crmbuilder-v2/src/crmbuilder_v2/api/routers/`:

- `workstreams.py`
- `conversations.py`
- `reference_books.py`
- `work_tickets.py`
- `close_out_payloads.py`
- `deposit_events.py`

Each router exposes its endpoints per the per-entity spec's section 3.5. All endpoints return the `{data, meta, errors}` envelope per existing V2 convention. The deposit_event router omits PUT, PATCH, DELETE, and restore handlers; the framework default of HTTP 405 Method Not Allowed responds for the omitted methods.

The router-level path identifiers use hyphenated plurals matching existing V2 conventions (`/workstreams`, `/conversations`, `/reference-books`, `/work-tickets`, `/close-out-payloads`, `/deposit-events`).

### 3.4 Desktop UI

Six new panels at `crmbuilder-v2/src/crmbuilder_v2/ui/panels/`:

- `workstreams_panel.py`
- `conversations_panel.py`
- `reference_books_panel.py`
- `work_tickets_panel.py`
- `close_out_payloads_panel.py`
- `deposit_events_panel.py`

Each panel extends the `ListDetailPanel` base per the user-interface version 0.4 governance-entity pattern. Master/detail layout, sidebar integration, and dialog patterns follow each spec's section 3.6.

Cross-panel UI conventions:

- **Sidebar:** the six panels appear in the Governance sidebar group at the end of the existing eight entries, in workstream order: Workstreams, Conversations, Reference Books, Work Tickets, Close-Out Payloads, Deposit Events. No sub-grouping in v0.7 (DEC-163).
- **Master pane:** ListDetailPanel-backed; columns and filters per each spec. Reference_book and work_ticket panels carry Kind columns and Kind filter combos. Reference_book panel additionally carries a Current Version column. Close_out_payload and deposit_event panels carry Outcome/Status filter combos. Deposit_event panel uniquely sorts identifier descending (audit-log deviation).
- **Detail pane:** Vertical layout per each spec's section 3.6.3. References-section widget renders inbound and outbound edges per the user-interface version 0.3 references pattern (DEC-031). Reference_book additionally carries the inline version-history section.
- **Create/Edit/Delete dialogs:** `EntityCrudDialog` and `EntityCrudDeleteDialog` subclasses per each spec, following the user-interface version 0.3 governance-entity dialog pattern. Deposit_event omits Create, Edit, Delete, and Restore dialogs entirely (read-only audit log per DEC-160); its right-click context menu offers Copy Identifier and Copy Log Path only.

### 3.5 Apply path integration

The existing apply script (`crmbuilder-v2/scripts/apply_close_out.py`) is modified by Slice D to integrate deposit_event creation. The modification:

1. **Open a log file** at `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (where NNN is the next deposit_event identifier, fetched from `GET /deposit-events/next-identifier` at script start). All subsequent stdout is duplicated to this file as the apply runs.
2. **Capture per-record HTTP responses.** Each existing `_request()` call's status code and response body are recorded into an in-memory `records_summary` accumulator and a `wrote_records` accumulator (the records that returned HTTP 200/201, excluding 409 SKIPs).
3. **Determine outcome.** At the end of the section processing loop, `outcome` is `failure` if any non-409 error occurred (the existing `ok` variable equivalent), `success` otherwise.
4. **POST the deposit_event** at the apply's last step. The POST body is the fully assembled deposit_event JSON: identity fields (auto-generated title and description from outcome and counts), classification (`_outcome`), three diagnostic JSON fields (`_records_summary`, `_error_info` populated on failure / null on success, `_apply_context` capturing the script invocation), `_log_file_path` pointing at the captured log, and the `references` array containing exactly one `deposit_event_applies_close_out_payload` edge to the target close_out_payload (identifier extracted from the payload file's `label` or session-section identifier-prefix matching) plus zero or more `deposit_event_wrote_record` edges to each record the apply actually wrote.
5. **The deposit_event POST is atomic** at the access layer — it creates the row, the outbound edges, and (on success against a `ready` close_out_payload) transitions the close_out_payload to `applied`, all in one transaction. The apply script does not need to issue a separate close_out_payload status update.
6. **For payloads not yet represented as `close_out_payload` records** (the bootstrap case during v0.7 deployment, and the historical-backfill case for prior payload files), the apply script's deposit_event POST step is deferred behind a `--skip-deposit-event` flag, or the close_out_payload record is created lazily as a side-effect of the deposit_event POST. The build-planning conversation chooses the safer path: **lazy creation** in Slice D's implementation. When the apply script POSTs a deposit_event whose target close_out_payload identifier does not yet exist as a record, the access layer creates the close_out_payload record on the fly (with status `ready` and file_path inferred from the payload file argument), then creates the deposit_event and its edges and transitions the close_out_payload to `applied`. The behavior makes the apply path forward-compatible with both backfill scenarios and routine new applies. See implementation plan section 4.D for the full transactional behavior.

### 3.6 Retroactive backfill (PI-022 refinement)

PI-022 was authored by SES-046 to track "Retroactive migration: whether to backfill governance entity records for sessions, decisions, planning items, references, and prior workstreams already in the database." The build-planning conversation refines it into a phased execution plan; the refinement is recorded in DEC-166 and executed via Slice E.

**Phase 1 (executed in Slice E of v0.7).** Backfill the governance entity schema-design workstream itself:

- **1 workstream record:** WS-001 — "Governance entity schema-design workstream" (status: `in_flight` at Slice E execution time, transitioning to `complete` at v0.7 ship; `_started_at` backfilled to 05-20-26).
- **8 conversation records:** CONV-001 through CONV-008 — SES-047 (workstream-establishing), SES-048 (workstream schema), SES-049 (conversation schema), SES-050 (reference_book schema), SES-051 (work_ticket schema), SES-052 (close_out_payload schema), SES-054 (deposit_event schema), SES-055 (this build-planning conversation). Each `complete` with `_completed_at` backfilled to the SES record's `session_date`; chained via `conversation_succeeds_conversation` edges; each carries `conversation_belongs_to_workstream` edge to WS-001 and `conversation_records_session` edge to its SES record.
- **8 close_out_payload records:** COP-001 through COP-008 — one per `close-out-payloads/ses_047.json` through `ses_055.json`. Each `applied` with `_applied_at` backfilled. Each carries `close_out_payload_produced_by_conversation` edge to the corresponding CONV record.
- **8 deposit_event records:** DEP-001 through DEP-008 — one per historical apply (and the v0.7-time applies of SES-054 and SES-055). For the historical applies, `_outcome` is `success`, `_log_file_path` is a placeholder (`deposit-event-logs/dep_NNN-historical.log` containing a one-line note that the log was not captured because the entity type didn't exist at apply time), `_records_summary` is reconstructed from the corresponding payload file's section counts, `_apply_context` uses runner `"backfill_script"`, and `_created_at` is backfilled to the close_out_payload's `_applied_at`. Each carries the parent edge and (where reconstructable) `deposit_event_wrote_record` edges.
- **8 work_ticket records:** WT-001 through WT-008 — one per kickoff prompt file consumed by the eight conversations. Each `consumed` with `_consumed_at` backfilled. Each carries `conversation_opens_against_work_ticket` edge inbound from its conversation.
- **9 reference_book records:** RB-001 through RB-009 — the workstream master plan (`governance-schema-workstream-plan.md`), the spec guide (`governance-entity-schema-spec-guide.md`), the six schema specs, this PRD, and the implementation plan. Each `active`. RB-001 (the workstream master plan) carries `workstream_planned_in_reference_book` edge inbound from WS-001.
- **Per-version rows:** for each `reference_book` with explicit version history in its Revision Control table (the spec guide v1.0; workstream.md v1.0; conversation.md v1.0; reference_book.md v1.0 and v1.1; work_ticket.md v1.0; close_out_payload.md v1.0 and v1.1; deposit_event.md v1.0; this PRD v0.1; the implementation plan v0.1), one row per `reference_book_versions`.

Phase 1 totals: 1 workstream, 8 conversations, 8 close_out_payloads, 8 deposit_events, 8 work_tickets, 9 reference_books, ~14 reference_book_versions, plus ~80 references (one `conversation_belongs_to_workstream` per CONV, one `conversation_records_session` per CONV, six `conversation_succeeds_conversation` chains, one `conversation_opens_against_work_ticket` per CONV, one `close_out_payload_produced_by_conversation` per COP, one `deposit_event_applies_close_out_payload` per DEP, plus the wrote_record back-references where reconstructable). Slice E executes Phase 1 as a one-off Python script.

**Phase 2 and beyond (deferred to follow-on planning items at v0.7 close).** Prior workstreams (methodology entity schema-design, user-interface v0.5 engagement management, user-interface v0.6 styling, multi-tenancy routing fix, Cleveland Business Mentors paper test, catalog ingestion), prior conversations (SES-001 through SES-045), prior payload files (close-out-payloads/ses_001 through ses_044.json), and historical applies as deposit_events. Each subsequent phase is its own follow-on planning item, scoped at that time. PI-022 itself remains Open at v0.7 ship; its discharge waits on the completion of all phases.

The conservative posture: backfill what gives end-to-end validation of the new entity types against real content (Phase 1), then accept that further phases are operationally optional and can be sequenced independently.

---

## 4. Cross-cutting concerns

### 4.1 References-row addressing for `deposit_event_wrote_record`

The `deposit_event_wrote_record` kind admits `reference` as one of its four target types. References-table rows do not currently have prefixed identifiers (unlike sessions, decisions, planning_items, which do). Slice A introduces an addressing scheme for individual reference rows so they can be targeted by deposit_event back-references.

**Working approach (Slice A's call):** add a `reference_identifier` column to the `refs` table with format `REF-NNN` zero-padded to four digits (because there are 234+ existing reference rows; `REF-NNN` to three digits would collide; four digits gives headroom for the next decade of project growth). The column is server-assigned on POST and back-filled in the migration for existing rows by row order. The existing rows are addressed as `REF-0001` through `REF-NNNN`; new rows assigned at insert. The `REFERENCES` endpoint's response shape gains the `reference_identifier` field; existing consumers (the apply script's section processing for references) are unaffected because they POST without an identifier.

Alternative: synthesize a composite addressing string `"refs/{source_type}/{source_identifier}/{target_type}/{target_identifier}/{kind}"` and store the synthesized string as the `target_id` value in the `deposit_event_wrote_record` edge. This requires no schema change but complicates the back-reference rendering (the synthesized string must be parsed at render time to navigate to the underlying refs row).

The working approach (`reference_identifier` column with `REF-NNNN` format) is preferred because it parallels the addressing scheme for the other three target types and renders cleanly in the references-section widget. The implementation plan section 3.1 names this as a Slice A migration step.

### 4.2 Migration sequencing

Slice A produces one migration file (or possibly a small numbered series) that:

1. Extends `refs.source_type` and `refs.target_type` CHECK constraints to admit the six new entity types.
2. Extends `refs.relationship_kind` CHECK constraint to admit the eight new relationship kinds.
3. Extends `change_log.entity_type` CHECK constraint to admit the six new entity types.
4. Adds the `reference_identifier` column to `refs` with `REF-NNNN` format; back-fills existing rows by `id` order.
5. Creates the `workstreams`, `conversations`, `reference_books`, `reference_book_versions`, `work_tickets`, `close_out_payloads`, `deposit_events` tables.

The CHECK extensions happen before the new tables are created because the new tables' foreign-key-or-reference relationships may need to be exercised in fixture data or test setup against the extended constraint. The `reference_identifier` back-fill happens after the constraint extensions but before the new entity tables so the back-fill query has the full schema available.

### 4.3 `vocab.py` aggregated update

The `vocab.py` update consolidates additions from all six specs into one commit:

- **`REFERENCE_RELATIONSHIPS` frozenset** gains eight entries (`conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`, `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation`, `close_out_payload_produced_by_conversation`, `deposit_event_applies_close_out_payload`, `deposit_event_wrote_record`).
- **`ENTITY_TYPES` frozenset** gains six entries (`workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`).
- **`_kinds_for_pair()` function** gains source-target binding clauses per the per-entity specs' section 3.3.4 tables. The clauses are grouped in source-then-target order for readability; existing same-type `supersedes` clause naturally admits the new same-type supersession pairs (`(workstream, workstream)`, `(conversation, conversation)`, `(reference_book, reference_book)`, `(work_ticket, work_ticket)`, `(close_out_payload, close_out_payload)`) without modification.

The cross-cutting `deposit_event_wrote_record` clause matches four target types in one conditional (`if source_type == 'deposit_event' and target_type in ('session', 'decision', 'planning_item', 'reference')`) per the deposit_event spec's section 3.3.4.

### 4.4 About-dialog version bump

`crmbuilder-v2/src/crmbuilder_v2/__init__.py`'s `__version__` bumps from `"0.6.0"` to `"0.7.0"`. The About dialog's content (currently rendered from the version constant per the user-interface version 0.3 About dialog implementation) reflects the new version automatically. The About dialog text may also be augmented with a short release-name summary line ("Governance entity release") per the implementation plan's Slice F.

### 4.5 Documentation updates

- **`crmbuilder/CLAUDE.md` v2 section** receives a new subsection describing the six new governance entity types, the apply-path integration with deposit_events, the deposit-event-logs/ directory convention, and the PI-022 phased backfill status. Added in Slice F.
- **README.md** receives a short bullet under the v2 feature list naming the governance entity release. Added in Slice F.
- **The v2 Product Requirements Document index** (if such an index exists in any aggregating document) is updated to add this PRD's entry.

### 4.6 Backward compatibility

No existing data lives in the new tables (they don't exist yet). Backward compatibility concerns are limited to:

- **Existing references-table data must continue to validate** against the relaxed CHECK constraint. Since the relaxation is additive (new values admitted, no existing values restricted), all existing rows continue to pass.
- **Existing close_out_payload-semantic behavior** must continue to hold under the at-most-one → zero-or-more relaxation. Since the relaxation applies only at the `deposit_event_applies_close_out_payload` cardinality level and existing data has zero such edges (the kind doesn't exist yet), no existing behavior is affected.
- **The change_log.entity_type CHECK extension** is additive; existing change-log rows continue to pass.

No existing API endpoints change. No existing access-layer signatures change. No existing user-interface panels change.

---

## 5. Acceptance criteria (aggregated)

Acceptance criteria are tracked per-slice in the implementation plan. Aggregated across the six specs, the release accepts when:

- **All seven new tables exist** with correct columns, types, constraints, and indexes per the per-entity specs' field tables.
- **All eight new relationship kinds** are registered in `vocab.py` and the `_kinds_for_pair` function returns correct kind sets for the new pairs.
- **The references-table CHECK constraint admits all six new entity types** as source_type and target_type values; the relationship_kind CHECK constraint admits the eight new kinds; the change_log.entity_type CHECK admits the six new entity types; the references table carries a `REF-NNNN` reference_identifier column on all rows.
- **All access-layer methods exist** with expected signatures and pass unit tests per per-entity spec section 3.7.
- **All REST endpoints return expected responses** for representative happy-path and validation-failure cases, including the `{data, meta, errors}` envelope shape.
- **The deposit_event endpoint set is restricted** to POST and GET only; PUT/PATCH/DELETE/restore return HTTP 405.
- **The applied-requires-edge rule fires correctly** for close_out_payload's `ready → applied` transition: first inbound success edge transitions; subsequent edges admitted without re-transition; failure edges never transition.
- **The work_ticket consumed-requires-edge rule fires correctly** for the `ready → consumed` transition.
- **The supersession-requires-edge rule fires correctly** on all five workflow-shape entities and reference_book.
- **The six sidebar entries appear in the Governance group** in workstream order, after the existing eight entries.
- **Each panel's master pane lists records** with the correct columns and sort; right-click context menus offer the correct action set (reduced to two read affordances for deposit_event).
- **Each panel's detail pane renders all fields** including references-section integration; create/edit/delete dialogs work end-to-end (with deposit_event's no-CRUD-dialogs deviation honored).
- **Reference_book detail pane renders the inline version-history section** with Add Version affordance; the version-at endpoint resolves correctly against various as-of timestamps.
- **The apply script writes a log file** at `deposit-event-logs/dep_NNN.log` on each apply run; the file is committed alongside the payload commit.
- **The apply script POSTs a deposit_event record** at its last step with all fields populated, the parent edge, the wrote_record back-references, and (on success against a ready payload) drives the close_out_payload's transition to applied.
- **PI-022 Phase 1 backfill executes** in Slice E: 1 workstream, 8 conversations, 8 close_out_payloads, 8 deposit_events, 8 work_tickets, 9 reference_books, ~14 reference_book_versions, plus ~80 references are created. WS-001 is in_flight at Slice E execution and transitions to complete at v0.7 ship.
- **About-dialog version bumps to 0.7.0**; README and `crmbuilder/CLAUDE.md` reflect the release.
- **The v2 test suite is green** (`uv run pytest tests/crmbuilder_v2/`) including all new tests added by the slices.

---

## 6. Decision records

The following six decisions are authored at conversation close (SES-055) and apply via the standard close-out path. Anticipated identifiers DEC-161 through DEC-166; actual identifiers assigned at apply time and may shift if other conversations close before this one applies.

- **DEC-161** — Target user-interface version 0.7. The governance entity release lands as v0.7, a dedicated release after v0.6 styling. No bundling with adjacent work. Bumps `__version__` to `"0.7.0"`.
- **DEC-162** — Six-slice topology (A schema and access; B API endpoints; C UI panels; D apply-script and deposit-event integration; E PI-022 Phase 1 backfill; F documentation, version bump, closeout). Sequential dependency order. Per-slice acceptance criteria aggregated from per-entity spec section 3.7 lists.
- **DEC-163** — Sidebar grouping: append the six new entities to the existing Governance group in workstream order; no sub-grouping in v0.7. The resulting fourteen-entry Governance group is accepted as scannable for v0.7; a future release may sub-group if signal emerges.
- **DEC-164** — Deposit-event log files git-tracked under `PRDs/product/crmbuilder-v2/deposit-event-logs/`. Files committed alongside the close-out payload commit. The capture is durable diagnostic value worth the modest repo-size cost (~5KB per apply attempt).
- **DEC-165** — Cross-spec consistency reconciliation executed: close_out_payload.md v1.1 admits zero-or-more inbound `deposit_event_applies_close_out_payload` edges per DEC-158. The `ready → applied` transition fires on the first inbound success edge; subsequent edges admitted without further state change. The reconciliation is in-place revision of close_out_payload.md (Revision Control v1.1 row, Change Log v1.1 entry, §3.3.2 cardinality language, §3.4.3 applied-requires-edge rule expansion).
- **DEC-166** — PI-022 refinement: phased backfill execution. Phase 1 in Slice E backfills the governance entity schema-design workstream's eight conversations, one workstream, eight close_out_payloads, eight deposit_events, eight work_tickets, and nine reference_books. Phases 2 and beyond (prior workstreams, prior conversations, prior payload-and-deposit history) are deferred to follow-on planning items authored at v0.7 close. PI-022 itself remains Open at v0.7 ship; its discharge waits on completion of all phases.

---

## 7. Cross-references

### 7.1 Schema specifications (the six this release implements)

- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` v1.0
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` v1.0
- `PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md` v1.1
- `PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md` v1.0
- `PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md` v1.1 (reconciled by this conversation per DEC-165)
- `PRDs/product/crmbuilder-v2/governance-schema-specs/deposit_event.md` v1.0

### 7.2 Workstream artifacts

- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — the template each spec follows
- `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md` — this conversation's seed prompt

### 7.3 Implementation plan and slice prompts

- `PRDs/product/crmbuilder-v2/governance-entity-implementation-plan.md` — the per-slice plan
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-A-schema-and-access.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-B-api-endpoints.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-C-ui-panels.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-D-apply-script-and-deposit-events.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-E-pi022-backfill.md`
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-F-closeout.md`

### 7.4 Foundation decisions

- DEC-117 (three workflow-file families) through DEC-122 (workstream opens immediately) — the workstream's foundation, recorded by SES-046.
- DEC-123 through DEC-160 — the six-decisions-per-conversation outputs of SES-048 through SES-054. Cited individually by the per-entity specs.

### 7.5 Related architectural references

- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; new entity types are per-engagement.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary; consolidated update in Slice A.
- `crmbuilder-v2/scripts/apply_close_out.py` — apply script; Slice D modification target.
- `crmbuilder-v2/migrations/versions/0007_v0_4_create_domains_table.py` — migration precedent for entity-type CHECK constraint extensions.

### 7.6 Related parallel work (not modified by v0.7)

- `PRDs/product/crmbuilder-v2/ui-PRD-v0.6.md` — styling workstream's PRD; v0.6 shipped 05-22-26 (approximate).
- `PRDs/product/crmbuilder-v2/multi-tenancy-routing-fix-slice-plan.md` — routing fix slices in flight; parallel to v0.7.
- Cleveland Business Mentors engagement Planning Item 001 (sub-domain hierarchy) — parallel, in CBM engagement scope only.

---

*End of document.*
