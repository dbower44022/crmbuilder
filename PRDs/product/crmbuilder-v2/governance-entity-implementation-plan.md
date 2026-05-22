# Governance Entity Implementation Plan

**Last Updated:** 05-22-26 17:30
**Status:** Draft v0.1 — produced by build-planning conversation (SES-055) alongside `governance-entity-PRD-v0.1.md`
**Target user-interface version:** v0.7
**Companion documents:** `governance-entity-PRD-v0.1.md` (release scope, architecture, decisions), six per-entity schema specifications under `governance-schema-specs/`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-22-26 17:30 | Doug Bower / Claude (build-planning conversation SES-055) | Initial draft. Produced by the build-planning conversation that closes the governance entity schema-design workstream. Breaks the v0.7 governance entity release into six Claude Code execution slices in strict dependency order: A (schema migrations and access layer for all six new entity types plus the references-row addressing scheme and the change_log.entity_type CHECK extension), B (REST API routers and envelope handling for the six new types with deposit_event's reduced surface), C (desktop UI panels for the six new types with sidebar integration), D (apply_close_out.py modifications: log file capture, deposit_event POST as last step, atomic close_out_payload transition), E (PI-022 Phase 1 retroactive backfill of the governance entity schema-design workstream's eight conversations and supporting records), and F (documentation updates, About-dialog version bump to 0.7.0, README and CLAUDE.md updates, build closeout). Each slice has its own Claude Code prompt under `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-{A..F}-*.md`. Total acceptance criteria across the six slices: 90 statements aggregated from the six per-entity specs' section 3.7 lists plus cross-cutting items. |

---

## Change Log

**Version 0.1 (05-22-26 17:30):** Initial creation. Defines the six-slice execution plan for the v0.7 governance entity release. Each slice is a single Claude Code execution with its own Markdown prompt under `prompts/`. The slices run sequentially, in dependency order, with the slice's own acceptance gate before the next slice opens. Slice A is the foundation (schema and access layer); Slice B adds the REST API; Slice C adds the desktop UI; Slice D integrates the apply path; Slice E executes PI-022 Phase 1 backfill; Slice F closes the release. Per-slice acceptance criteria aggregated from per-entity spec section 3.7 lists plus cross-cutting concerns from PRD section 4.

---

## 1. Slice topology

```
Slice A    Schema migrations + access layer + vocab.py update
              ↓
Slice B    REST API endpoints + envelope handling
              ↓
Slice C    Desktop UI panels + sidebar integration + dialogs
              ↓
Slice D    apply_close_out.py modifications + atomic deposit_event POST
              ↓
Slice E    PI-022 Phase 1 backfill (governance workstream's 8 conversations)
              ↓
Slice F    Docs (README, CLAUDE.md, About dialog), version bump, closeout
```

Each slice gates on the prior slice's acceptance criteria passing. Doug runs each slice via Claude Code in the dogfood crmbuilder repo; review and merge happen between slices.

---

## 2. Slice-by-slice plan

### 2.1 Slice A — Schema, migrations, vocab.py, access layer

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-A-schema-and-access.md`

**Deliverables:**

1. **One Alembic migration** (`0011_v0_7_governance_entities.py`) that:
   - Extends `refs.source_type` CHECK constraint to admit the six new entity types.
   - Extends `refs.target_type` CHECK constraint to admit the six new entity types.
   - Extends `refs.relationship_kind` CHECK constraint to admit the eight new kinds.
   - Extends `change_log.entity_type` CHECK constraint to admit the six new entity types.
   - Adds `reference_identifier` column to `refs` with `^REF-\d{4}$` GLOB CHECK; back-fills existing rows by `id` order (REF-0001, REF-0002, ...).
   - Creates the `workstreams` table per `workstream.md` section 3.2.
   - Creates the `conversations` table per `conversation.md` section 3.2.
   - Creates the `reference_books` table per `reference_book.md` sections 3.2.1–3.2.6.
   - Creates the `reference_book_versions` child table per `reference_book.md` section 3.2.7.
   - Creates the `work_tickets` table per `work_ticket.md` section 3.2.
   - Creates the `close_out_payloads` table per `close_out_payload.md` section 3.2.
   - Creates the `deposit_events` table per `deposit_event.md` section 3.2 (note: no `_updated_at`, no `_deleted_at` columns).
   - Forward and backward reversible.

2. **`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` update** (one commit):
   - `REFERENCE_RELATIONSHIPS` frozenset extended with eight entries: `conversation_belongs_to_workstream`, `workstream_planned_in_reference_book`, `conversation_records_session`, `conversation_opens_against_work_ticket`, `conversation_succeeds_conversation`, `close_out_payload_produced_by_conversation`, `deposit_event_applies_close_out_payload`, `deposit_event_wrote_record`.
   - `ENTITY_TYPES` frozenset extended with six entries: `workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, `deposit_event`.
   - `_kinds_for_pair()` function extended with source-target binding clauses per the per-entity specs' section 3.3.4 tables. Each clause grouped by source type for readability. The existing same-type `supersedes` clause automatically admits the new same-type supersession pairs without modification.
   - Module docstring updated to reference v0.7 governance entity additions.

3. **SQLAlchemy ORM models** at `crmbuilder-v2/src/crmbuilder_v2/access/models/` (or wherever existing entity models live):
   - `Workstream`, `Conversation`, `ReferenceBook`, `ReferenceBookVersion`, `WorkTicket`, `CloseOutPayload`, `DepositEvent` model classes.
   - Each model declares its columns per the per-entity spec's section 3.2 with the correct nullable, default, and CHECK constraints.
   - The `Reference` model gains the `reference_identifier` column with format validation.

4. **Repository modules** at `crmbuilder-v2/src/crmbuilder_v2/access/repositories/`:
   - `workstreams.py`, `conversations.py`, `reference_books.py`, `work_tickets.py`, `close_out_payloads.py`, `deposit_events.py`.
   - Each module exposes the standard method set per spec section 3.7 acceptance criteria.
   - Status-transition validation per each spec's section 3.4.
   - Edge-required-at-terminal rules (DEC-125 supersession, DEC-143 work_ticket consumed, DEC-149 close_out_payload applied with the v1.1 first-success-transitions semantics).
   - At-most-one rules (work_ticket single-use, close_out_payload single-producer).
   - Atomic deposit_event POST behavior at `deposit_events.py`: creates row, parent edge, wrote_record edges, transitions close_out_payload on success; lazy-creates close_out_payload record if the target identifier doesn't yet exist (per PRD section 3.5).
   - `next_*_identifier()` helper per each entity type.
   - Reference_book child versions: `list_versions(rb_id)`, `add_version(rb_id, label, date, summary)`, `version_at(rb_id, as_of)`.
   - First-success-transitions logic at `close_out_payloads.py`: the first inbound `deposit_event_applies_close_out_payload` edge from a `success` deposit_event drives the `ready → applied` transition; subsequent inbound edges (failures or repeat successes) are admitted without further state change.

5. **Unit tests** at `tests/crmbuilder_v2/access/repositories/`:
   - One test module per new repository covering happy-path CRUD, status-transition validation, edge-required rules, at-most-one rules, identifier format validation, soft-delete and restore round-trip, identifier auto-assignment.
   - One cross-entity integration test verifying the close_out_payload `ready → applied` transition fires correctly on the first inbound `success` deposit_event edge and doesn't fire on `failure` edges.
   - One cross-entity integration test verifying the work_ticket `ready → consumed` transition fires correctly on the inbound `conversation_opens_against_work_ticket` edge.
   - One vocab test verifying `_kinds_for_pair` returns the expected kind sets for the new pairs.

**Acceptance criteria for Slice A:**

- Migration applies cleanly against an existing engagement database; forward and backward reversible.
- `refs.relationship_kind` CHECK constraint admits all eight new kinds; rejects unknowns.
- `refs.source_type` and `refs.target_type` CHECK constraints admit all six new entity types; reject unknowns.
- `change_log.entity_type` CHECK constraint admits all six new entity types.
- All existing references rows have `REF-NNNN` identifiers post-migration; new POST `/references` assigns identifier server-side.
- All seven new tables exist with correct columns, types, and CHECK constraints per the per-entity specs' field tables.
- All seven new repository modules expose the expected method signatures per the per-entity specs' section 3.7 acceptance criteria.
- Status-transition validation rejects invalid transitions with HTTP 422 `{"error": "invalid_status_transition", "from": ..., "to": ...}` per each spec.
- Supersession-requires-edge rule fires correctly on all five workflow-shape entities and reference_book.
- Work_ticket consumed-requires-edge rule fires correctly.
- Close_out_payload applied-requires-edge rule fires correctly with first-success-transitions semantics.
- Work_ticket single-use rule rejects second inbound consumption edge.
- Close_out_payload single-producer rule rejects second outbound production edge.
- Atomic deposit_event POST behavior: in one transaction creates record, parent edge, wrote_record edges, and (on success vs ready) transitions close_out_payload to applied; lazy-creates close_out_payload if target identifier missing.
- All new unit tests pass; existing tests remain green; `uv run pytest tests/crmbuilder_v2/` is green.

### 2.2 Slice B — REST API endpoints

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-B-api-endpoints.md`

**Deliverables:**

1. **Router modules** at `crmbuilder-v2/src/crmbuilder_v2/api/routers/`:
   - `workstreams.py`, `conversations.py`, `reference_books.py`, `work_tickets.py`, `close_out_payloads.py`, `deposit_events.py`.
   - Each module registers the endpoints per the per-entity spec's section 3.5.
   - Standard eight-endpoint set on the first five (list, get, post, put, patch, delete, restore, next-identifier).
   - Reference_book adds three version-management sub-endpoints.
   - Deposit_event restricted to POST `/deposit-events`, GET `/deposit-events`, GET `/deposit-events/{identifier}`, GET `/deposit-events/next-identifier`. PUT, PATCH, DELETE, restore not registered (HTTP 405 default response).
   - All endpoints return the `{data, meta, errors}` envelope per existing V2 convention.

2. **Router registration** in the main API app:
   - Each new router added to the FastAPI app's router include list.
   - Router prefix and tags per V2 convention.

3. **Integration tests** at `tests/crmbuilder_v2/api/routers/`:
   - One test module per new router covering happy-path responses, validation-failure responses with envelope shape, list endpoint filters (`?include_deleted=true`, `?kind=`, `?status=`, `?outcome=`), and identifier auto-assignment.
   - One test verifying deposit_event PUT, PATCH, DELETE, restore endpoints return HTTP 405.
   - One test verifying the reference_book versions sub-endpoints (`/versions`, `/version-at?as_of=...`) return expected shapes.

**Acceptance criteria for Slice B:**

- All endpoints return correct HTTP status codes and `{data, meta, errors}` envelope shape for happy-path and validation-failure cases.
- The deposit_event router responds with HTTP 405 to PUT, PATCH, DELETE, and restore methods.
- List endpoint filters work correctly: `?include_deleted=true` shows soft-deleted; `?kind=<value>` filters reference_book and work_ticket; `?status=<value>` filters workflow-shape entities; `?outcome=<value>` filters deposit_event.
- Identifier auto-assignment helpers (`GET /{plural}/next-identifier`) return the next available value; POST without identifier assigns same; concurrent POSTs don't collide.
- Reference_book version sub-endpoints work: `GET /reference-books/{id}/versions` returns descending-by-date version list; `POST /reference-books/{id}/versions` creates new version row and recomputes parent's denormalized current pointers; `GET /reference-books/{id}/version-at?as_of=...` returns the in-force version.
- `uv run pytest tests/crmbuilder_v2/api/routers/` is green; existing API tests remain green.
- `curl -sf http://127.0.0.1:8765/health` returns HTTP 200 with the API up.

### 2.3 Slice C — Desktop UI panels

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-C-ui-panels.md`

**Deliverables:**

1. **Panel modules** at `crmbuilder-v2/src/crmbuilder_v2/ui/panels/`:
   - `workstreams_panel.py`, `conversations_panel.py`, `reference_books_panel.py`, `work_tickets_panel.py`, `close_out_payloads_panel.py`, `deposit_events_panel.py`.
   - Each panel extends `ListDetailPanel` per the user-interface version 0.4 governance-entity pattern.
   - Master/detail layout per each spec's section 3.6.
   - Reference_book panel uniquely renders the inline version-history section in the detail pane.
   - Deposit_event panel uniquely sorts identifier descending (audit-log deviation), omits Create/Edit/Delete/Restore dialogs, reduces context menu to Copy Identifier and Copy Log Path.

2. **Dialog modules** at `crmbuilder-v2/src/crmbuilder_v2/ui/dialogs/`:
   - `workstream_dialog.py`, `conversation_dialog.py`, `reference_book_dialog.py`, `work_ticket_dialog.py`, `close_out_payload_dialog.py`.
   - Each extends `EntityCrudDialog` per the user-interface version 0.3 governance-entity dialog pattern.
   - Field order per each spec's section 3.6.4–3.6.6.
   - Status combo restricts selectable values to valid transitions plus current value.
   - Required-field validation client-side; server-side errors surface inline.
   - Reference_book dialog includes the inline version-history section with Add Version sub-dialog in edit mode.
   - No deposit_event dialog (read-only audit log).

3. **Sidebar integration:**
   - Six new sidebar entries appended to the existing Governance group in workstream order: Workstreams, Conversations, Reference Books, Work Tickets, Close-Out Payloads, Deposit Events.
   - Sidebar entries are bound to their panels at app boot per the existing v0.4 sidebar pattern.
   - Sidebar icons per the existing entry icon convention (one per panel; the prompt names specific Lucide-style icons to choose from the existing icon set).

4. **References-section integration:**
   - The shared `ReferencesSection` widget (per DEC-031) is bound on each detail pane; renders inbound and outbound edges with the new relationship kinds.
   - The cascading `ReferenceCreateDialog` (per DEC-033) admits the new relationship kinds in its kind combo when the source and target types match a `_kinds_for_pair` clause; the dialog already drives off `_kinds_for_pair` so no per-entity dialog change is needed.
   - Deposit_event panel's references-section disables the Add Reference affordance (read-only).

5. **UI tests** at `tests/crmbuilder_v2/ui/panels/`:
   - One test module per new panel covering panel boot, master pane column rendering, default sort, right-click context menu items, create dialog round-trip (where applicable), edit dialog round-trip (where applicable), delete dialog confirmation (where applicable), references-section rendering.
   - One integration test verifying the deposit_event panel renders read-only with no Create/Edit/Delete dialogs.

**Acceptance criteria for Slice C:**

- The six sidebar entries appear in the Governance group in workstream order, after the existing eight entries.
- Each panel's master pane lists records with correct columns, sort order, and right-click context menu items.
- Deposit_event panel's master pane sorts identifier descending; its context menu has Copy Identifier and Copy Log Path only.
- Each panel's detail pane renders all fields including references-section integration.
- Reference_book detail pane renders the inline version-history section with Add Version affordance functional in edit mode.
- Create/edit/delete dialogs work end-to-end for the five entities that have them; deposit_event has no such dialogs.
- The cascading reference-create dialog admits the new relationship kinds when source and target match `_kinds_for_pair`.
- File-watch refresh picks up external changes (records authored via REST API outside the UI appear after the watch interval).
- `uv run pytest tests/crmbuilder_v2/ui/` is green; existing UI tests remain green.

### 2.4 Slice D — Apply script modifications + atomic deposit_event POST

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-D-apply-script-and-deposit-events.md`

**Deliverables:**

1. **Apply script modification** at `crmbuilder-v2/scripts/apply_close_out.py`:
   - **At script start (after argument parsing, before API health check):** fetch next deposit_event identifier from `GET /deposit-events/next-identifier`. Open log file at `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` for write. All subsequent stdout duplicated to the log file via a tee-style writer.
   - **During section processing:** capture per-record HTTP responses (status code, response body) into an in-memory `wrote_records` accumulator (records that returned 200/201, excluding 409 SKIPs) and a `records_summary` counter dict (keyed by section name).
   - **At apply's last step (after the section loop, before exit):** determine outcome (`failure` if any non-409 error occurred, `success` otherwise). Construct the deposit_event JSON: identity fields auto-generated from outcome and counts; classification (`_outcome`); diagnostic JSON fields (`_records_summary` from accumulator, `_error_info` from captured errors on failure / null on success, `_apply_context` capturing the script invocation context); `_log_file_path` (the path captured at start); references array (exactly one `deposit_event_applies_close_out_payload` edge to the target close_out_payload identifier — inferred from the payload file name `ses_NNN.json` → `COP-NNN` mapping, or from the payload's session-section identifier with a `SES-NNN` → `COP-NNN` mapping rule — plus zero or more `deposit_event_wrote_record` edges to each record in `wrote_records`). POST to `/deposit-events`.
   - **Identifier mapping rule for close_out_payload target:** the deposit_event's parent edge targets a `COP-NNN` identifier. The script derives this from the payload file's basename (`ses_NNN.json` → `COP-NNN`). If the target close_out_payload doesn't yet exist in the database, the access layer creates it lazily per Slice A's behavior (PRD section 3.5).
   - **Exit code unchanged** from current behavior: 0 on full success, 1 on errors, 2 on argument or payload-read errors. The deposit_event POST is the apply's last step; its success or failure feeds the exit code logic.
   - **Backward compatibility:** the modified apply script must still run cleanly against existing payload files (`close-out-payloads/ses_046.json` through `ses_055.json`), creating deposit_event records and lazy-creating close_out_payload records on the fly.

2. **Log file directory** at `PRDs/product/crmbuilder-v2/deposit-event-logs/`:
   - Directory created (initial `.gitkeep` or `README.md` for git tracking).
   - `.gitignore` not adding any pattern (log files git-tracked per DEC-164).
   - README.md or directory-level note explaining the directory's purpose, the `dep_NNN.log` naming convention, and that files are committed alongside the close-out payload commit.

3. **Tests for the apply script modification** at `tests/crmbuilder_v2/scripts/`:
   - One test running the modified script against a small fixture payload and verifying: log file is written at the expected path; deposit_event POST is invoked; records_summary matches the section counts; outcome is `success`; close_out_payload is lazy-created if missing; parent edge is created; wrote_record back-references are created.
   - One test exercising the failure path: apply script encounters a non-409 HTTP error in mid-section; outcome is `failure`; `_error_info` is populated; close_out_payload is NOT transitioned to `applied` (stays `ready`); records-written-before-failure are still back-referenced.

**Acceptance criteria for Slice D:**

- Modified apply script runs end-to-end against `close-out-payloads/ses_055.json` (this conversation's payload, when applied): writes log file at `deposit-event-logs/dep_NNN.log`, POSTs deposit_event at last step, transitions close_out_payload to `applied`, creates parent edge and wrote_record back-references.
- Re-running the apply script against the same payload creates a new deposit_event record (born-terminal append-only multi-event semantics per DEC-158); the close_out_payload stays `applied`; the new deposit_event records the re-confirmation with zero wrote_record edges (everything 409-SKIPped).
- Failure case: script encounters HTTP 422 mid-section; deposit_event POSTed with `_outcome = 'failure'`, `_error_info` populated with step name and error detail; close_out_payload stays `ready`; partial wrote_record back-references created for records written before the failure.
- `PRDs/product/crmbuilder-v2/deposit-event-logs/` exists and is git-tracked.
- `uv run pytest tests/crmbuilder_v2/scripts/` is green.

### 2.5 Slice E — PI-022 Phase 1 retroactive backfill

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-E-pi022-backfill.md`

**Deliverables:**

1. **One-off backfill script** at `crmbuilder-v2/scripts/backfill_governance_phase_1.py`:
   - Reads from the existing `PRDs/product/crmbuilder-v2/db-export/sessions.json`, `decisions.json`, `planning_items.json`, `references.json` snapshots plus the close-out payload files at `close-out-payloads/ses_047.json` through `ses_055.json` (eight files).
   - For each of the eight workstream conversations (SES-047, 048, 049, 050, 051, 052, 054, 055):
     - POSTs one `conversation` record with `_title` from the SES title, `_status = 'complete'`, `_completed_at` backfilled to the SES `session_date`, and an inbound `conversation_records_session` edge to the SES record.
     - POSTs one `conversation_belongs_to_workstream` edge to WS-001 (created in step below).
     - POSTs one `conversation_succeeds_conversation` edge to the prior conversation (sequential chain: CONV-001 → CONV-002 → CONV-003 → ... → CONV-008).
   - POSTs the one `workstream` record: WS-001 — "Governance entity schema-design workstream", `_purpose = "Close the gap between V2's governance database stated role and its actual coverage; design six new governance entity types under minimum-viable scope; deliver via v0.7 release."`, `_description` summarizing the workstream's seven design conversations and one build-planning conversation, `_status = 'complete'` at Slice E execution (assuming Slice E runs at or after v0.7 ship; if Slice E runs before v0.7 ship-tagging, status is `in_flight` with a Slice F transition step), `_started_at = '2026-05-20T22:00:00'`, `_completed_at` set to the SES-055 close timestamp.
   - POSTs the eight `work_ticket` records corresponding to the kickoff prompts: `governance-entity-schema-workstream-establishing-kickoff.md`, `schema-design-kickoff-workstream.md`, `schema-design-kickoff-conversation.md`, `schema-design-kickoff-reference-book.md`, `schema-design-kickoff-work-ticket.md`, `schema-design-kickoff-close-out-payload.md`, `schema-design-kickoff-deposit-event.md`, `governance-schema-build-planning-kickoff.md`. Each `_status = 'consumed'`, `_kind = 'kickoff_prompt'`, `_consumed_at` backfilled, with the inbound `conversation_opens_against_work_ticket` edge from its consuming conversation.
   - POSTs the eight `close_out_payload` records: COP-001 through COP-008 for `ses_047.json` through `ses_055.json`. Each `_status = 'applied'`, `_applied_at` backfilled to the corresponding SES `session_date`, with the outbound `close_out_payload_produced_by_conversation` edge to its producing conversation.
   - POSTs the eight `deposit_event` records: DEP-001 through DEP-008 for the eight applies. For SES-047 through SES-054, the apply happened pre-v0.7 with no deposit_event captured at the time; the backfill reconstructs from the payload's section counts. For SES-055 (this conversation), the apply happens during Slice E's execution and yields a real captured log. Each `_outcome = 'success'`, `_log_file_path = 'PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN-historical.log'` for backfilled records (with a one-line note explaining the log was not captured at apply time) and the real captured path for SES-055. `_apply_context.runner = "backfill_script"` for the historicals; the canonical value for the live SES-055 apply. `_records_summary` reconstructed from the corresponding payload's section counts. The parent `deposit_event_applies_close_out_payload` edge to the matching COP. Where reconstructable from the payload file, `deposit_event_wrote_record` back-references to the SES record, decision records, planning items, and references the payload created.
   - POSTs the nine `reference_book` records and the relevant `reference_book_versions` rows:
     - RB-001: `governance-schema-workstream-plan.md` (kind `workstream_master_plan`, v1.0 only) — carries inbound `workstream_planned_in_reference_book` edge from WS-001.
     - RB-002: `governance-entity-schema-spec-guide.md` (kind `methodology_guide`, v1.0 only).
     - RB-003: `governance-schema-specs/workstream.md` (kind `schema_specification`, v1.0 only).
     - RB-004: `governance-schema-specs/conversation.md` (kind `schema_specification`, v1.0 only).
     - RB-005: `governance-schema-specs/reference_book.md` (kind `schema_specification`, v1.0 and v1.1 versions).
     - RB-006: `governance-schema-specs/work_ticket.md` (kind `schema_specification`, v1.0 only).
     - RB-007: `governance-schema-specs/close_out_payload.md` (kind `schema_specification`, v1.0 and v1.1 versions).
     - RB-008: `governance-schema-specs/deposit_event.md` (kind `schema_specification`, v1.0 only).
     - RB-009: `governance-entity-PRD-v0.1.md` (kind `product_requirements_document`, v0.1 only).
     - RB-010: `governance-entity-implementation-plan.md` (kind `implementation_plan`, v0.1 only).
   - All POSTs idempotent on re-run (HTTP 409 SKIPs treated as already-present).
   - Script writes its stdout to `deposit-event-logs/backfill-phase-1.log` for forensic purposes (separate from the standard apply log, since this is a backfill not an apply).

2. **PI-022 status update reflection:**
   - The script does not modify PI-022's database row (the apply script doesn't support PATCH and PI-022 itself is not the backfill target; it tracks the backfill effort). PI-022 stays `Open` at v0.7 ship.
   - A note appended to PI-022's title or description (via a separate `UPDATE-PROMPT-PI-022-phase-1-complete.md` if signal emerges; not required at Slice E close) recording the Phase 1 completion. This is optional and deferred to operational signal.

3. **Verification queries** at script's end:
   - `GET /workstreams` returns one record (WS-001).
   - `GET /conversations` returns eight records (CONV-001 through CONV-008).
   - `GET /work-tickets` returns eight records (WT-001 through WT-008).
   - `GET /close-out-payloads` returns eight records (COP-001 through COP-008).
   - `GET /deposit-events` returns eight records (DEP-001 through DEP-008).
   - `GET /reference-books` returns ten records (RB-001 through RB-010).
   - `GET /references?relationship_kind=conversation_belongs_to_workstream` returns eight edges.
   - `GET /references?relationship_kind=conversation_succeeds_conversation` returns seven edges (chain).
   - The script prints a summary table of created record counts by entity type.

**Acceptance criteria for Slice E:**

- All ~50 records created per PI-022 Phase 1 plan: 1 workstream, 8 conversations, 8 work_tickets, 8 close_out_payloads, 8 deposit_events, 10 reference_books, plus ~14 reference_book_versions and ~70 reference edges.
- WS-001 is queryable; carries one inbound `workstream_planned_in_reference_book` edge from RB-001.
- The 8 conversation records are chained via `conversation_succeeds_conversation` edges in the correct order.
- Each conversation carries the `conversation_belongs_to_workstream` edge to WS-001 and the `conversation_records_session` edge to its SES record.
- Each work_ticket carries the inbound `conversation_opens_against_work_ticket` edge from its consuming conversation and is at status `consumed`.
- Each close_out_payload carries the outbound `close_out_payload_produced_by_conversation` edge and is at status `applied`.
- Each deposit_event carries the outbound `deposit_event_applies_close_out_payload` edge and (where reconstructable) the `deposit_event_wrote_record` back-references.
- Reference_book RB-005 and RB-007 each carry two version rows.
- Re-running the backfill script is idempotent (HTTP 409s on all records second time through).
- The desktop UI shows all new records in the new panels; navigation between panels (e.g., clicking a CONV record to see its workstream) works correctly.
- `uv run pytest tests/crmbuilder_v2/` remains green; no regressions.

### 2.6 Slice F — Documentation, version bump, build closeout

**Prompt:** `prompts/CLAUDE-CODE-PROMPT-v2-ui-v0.7-F-closeout.md`

**Deliverables:**

1. **About-dialog and version bump:**
   - `crmbuilder-v2/src/crmbuilder_v2/__init__.py`: `__version__ = "0.7.0"`.
   - About dialog content (per V2 user-interface version 0.3 About dialog) reflects the new version automatically.
   - About dialog optionally augmented with a short release-name line ("Governance entity release") in the version-info area.

2. **README.md update:**
   - Add a bullet under the v2 feature list naming "Governance entity release (v0.7): six new entity types — Workstreams, Conversations, Reference Books, Work Tickets, Close-Out Payloads, Deposit Events — close the gap between V2's governance database role and its actual coverage of the planning-and-execution machinery."

3. **`crmbuilder/CLAUDE.md` updates:**
   - Add a v0.7 subsection to the v2 release-history section summarizing the governance entity release.
   - Add the six new entity types to any entity-type catalog or list maintained in CLAUDE.md.
   - Reference the new directories: `deposit-event-logs/`.

4. **Build closeout session:**
   - At the end of v0.7 work (after Slice E executes and the new records exist in the database), one closeout session is authored via the standard close-out apply path: payload at `close-out-payloads/ses_NNN.json` plus apply prompt at `prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-NNN.md`.
   - The closeout session records: the release shipped; the v0.7 acceptance criteria all pass; PI-022 Phase 1 complete; phases 2 and beyond deferred to follow-on planning items (named at closeout); the workstream's status transitions to `complete` if Slice E created WS-001 with status `in_flight`.

5. **Follow-on planning items authored at closeout:**
   - PI-023 (anticipated identifier): PI-022 Phase 2 — backfill prior workstreams (methodology entity schema-design, user-interface v0.5 engagement management, user-interface v0.6 styling, multi-tenancy routing fix, Cleveland Business Mentors paper test).
   - PI-024 (anticipated identifier): PI-022 Phase 3 — backfill prior conversations (SES-001 through SES-045) and their kickoffs as work_tickets where reconstructable.
   - PI-025 (anticipated identifier): PI-022 Phase 4 — backfill historical applies as deposit_events for the ~38 prior close-out payload files.
   - Each new planning item references PI-022 as its parent (via `is_about` or similar generic edge).

**Acceptance criteria for Slice F:**

- `__version__` is `"0.7.0"`; About dialog reflects v0.7.
- README.md mentions the governance entity release.
- `crmbuilder/CLAUDE.md` v2 section is updated.
- `deposit-event-logs/` directory exists with at least one captured log file (the SES-055 apply log).
- Closeout session record exists; v0.7 acceptance criteria all pass; PI-022 phase 2+ planning items authored.
- All earlier slices' acceptance criteria remain passing (no regressions introduced by Slice F).

---

## 3. Cross-cutting implementation concerns

### 3.1 References-row addressing (`REF-NNNN`)

Slice A introduces a `reference_identifier` column on the `refs` table with format `^REF-\d{4}$`. The migration back-fills existing rows by `id` ascending order. New POST `/references` requests assign the identifier server-side per the standard auto-assignment pattern. This addressing scheme is necessary for the `deposit_event_wrote_record` edge to target individual references rows.

Considered alternatives:
- **Composite-key synthesis** (`"refs/{src_type}/{src_id}/{tgt_type}/{tgt_id}/{kind}"`): no schema change but complicates rendering and uniqueness guarantees; rejected.
- **Internal integer `id` exposure**: matches existing internal addressing but breaks the prefixed-identifier convention used everywhere else in V2; rejected.

The chosen approach (prefixed `REF-NNNN` identifier column) parallels every other entity type's identifier scheme and renders cleanly in the references-section widget. Format is four digits because existing references count (~234) is close to the three-digit cap; four digits gives ~9000 rows of headroom.

### 3.2 Migration sequencing within Slice A

The single migration file (`0011_v0_7_governance_entities.py`) sequences its operations as follows:

1. Extend `refs.source_type`, `refs.target_type`, `refs.relationship_kind` CHECK constraints (drop and recreate with new value set).
2. Extend `change_log.entity_type` CHECK constraint (drop and recreate).
3. Add `reference_identifier` column to `refs`; back-fill existing rows by `id` order.
4. Create `workstreams` table.
5. Create `conversations` table.
6. Create `reference_books` table.
7. Create `reference_book_versions` table (after parent table to satisfy FK).
8. Create `work_tickets` table.
9. Create `close_out_payloads` table.
10. Create `deposit_events` table.

The CHECK extensions come first so the new tables' FKs and reference-table interactions can use the extended constraints. The `reference_identifier` back-fill happens before the new entity tables so any back-fill that creates new references rows during the migration would use the new column.

### 3.3 Migration reversibility

Each operation has a reverse counterpart:

- CHECK extensions: revert by dropping and recreating with the prior value set.
- Column add: drop the column.
- Table creation: drop the tables in reverse order (deposit_events first, then close_out_payloads, work_tickets, reference_book_versions, reference_books, conversations, workstreams).

The `reference_identifier` back-fill is reversible by dropping the column (which removes the back-fill data automatically).

### 3.4 Testing strategy

- **Unit tests** (Slice A): per-repository CRUD, transition validation, edge rules.
- **Integration tests** (Slice B): per-router endpoint behavior, envelope shape, filter parameters.
- **UI tests** (Slice C): per-panel behavior, master/detail rendering, dialog round-trips.
- **End-to-end tests** (Slice D): apply script's deposit_event POST integration, atomic close_out_payload transition.
- **Backfill verification tests** (Slice E): record counts and edge counts match the Phase 1 plan.

### 3.5 Rollback strategy

Each slice's commit is independently revertable. If Slice C fails to ship cleanly, Slice A and B are still useful (the API works without the UI); the UI can be reverted to v0.6 sidebar. If Slice D fails, the apply script can be reverted to its current v0.6 form (the new endpoints stand but no apply integration). If Slice E fails, the backfill records can be soft-deleted via the standard endpoints (per spec section 3.4.5 for each entity type).

The full release can be rolled back by reverting all six slice commits in reverse order and running the migration's `downgrade()` to drop the seven new tables and reverse the CHECK constraint extensions.

---

## 4. Acceptance criteria summary

Aggregated across the six slices, the release accepts when:

- **All 7 new tables exist** (workstreams, conversations, reference_books, reference_book_versions, work_tickets, close_out_payloads, deposit_events) per per-entity spec §3.2 column definitions.
- **All 8 new relationship kinds** registered in `vocab.py` REFERENCE_RELATIONSHIPS and bound to source-target pairs in `_kinds_for_pair`.
- **All 6 new entity types** registered in `vocab.py` ENTITY_TYPES; the `refs.source_type`, `refs.target_type`, and `change_log.entity_type` CHECK constraints admit them.
- **References-row addressing scheme** in place via `reference_identifier` column on `refs` table with `REF-NNNN` format.
- **All 7 new repository modules** expose expected method signatures with edge-rule and transition-validation enforcement.
- **All 6 new REST router modules** expose endpoints per the per-entity specs' API surface tables; deposit_event reduced to POST + GET only.
- **All 6 new desktop UI panels** appear in the Governance sidebar in workstream order; master/detail rendering correct; dialogs functional (deposit_event read-only).
- **Apply script modification** writes log files, POSTs deposit_event records, transitions close_out_payload atomically.
- **PI-022 Phase 1 backfill** complete: ~50 records, ~70 reference edges, ~14 version rows.
- **Documentation updated**: README, CLAUDE.md, About dialog all reflect v0.7.
- **Build closeout session** authored; v0.7 ships; PI-022 phases 2+ planning items recorded.
- **`uv run pytest tests/crmbuilder_v2/` is green** across all slices.

---

*End of document.*
