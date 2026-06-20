# Governance Entity Schema Spec — `deposit_event`

**Last Updated:** 05-22-26 17:00
**Status:** Draft v1.0 — produced by schema-design conversation
**Position in workstream:** **Sixth and last** of six governance-entity schema specs (`workstream` → `conversation` → `reference_book` → `work_ticket` → `close_out_payload` → `deposit_event`)
**Predecessor conversation:** SES-052 (`close_out_payload` schema-design conversation)
**Successor conversation:** Build-planning conversation — kickoff at `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md`

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 1.0 | 05-22-26 17:00 | Doug Bower / Claude | Initial draft. Produced by the sixth and final schema-design conversation in the governance-entity schema-design workstream. Adopts the six cross-spec precedents in force after SES-052: references-edge over foreign-key for parent-child governance relationships (DEC-124), per-status lifecycle timestamps for workflow-shaped lifecycles (DEC-126), truly-terminal terminals (DEC-125), typed sequencing edges introduced when entity-family frequency justifies (DEC-133), documentary-vs-workflow distinction (DEC-137), and terminal-state consumption requires the inbound consumption edge (DEC-143). **Establishes two new cross-spec precedents:** (1) **born-terminal append-only with creation as the event-recording moment** — the record's POST IS the event being recorded; no `running` intermediate; no PUT, no PATCH, no DELETE; one timestamp (`deposit_event_created_at`); the entity's `_outcome` field carries a permanent fact rather than a workflow state; (2) **born-terminal append-only entities admit multi-event-per-target-record** — multiple `deposit_event_applies_close_out_payload` edges may target a single close_out_payload, one per apply attempt; relaxes the close_out_payload spec's at-most-one default, which that spec explicitly deferred to this conversation. Adopts a born-terminal append-only synthesis with diagnostic log capture (`deposit_event_log_file_path` field per the file-pointer precedent locked by DEC-139 and DEC-145, repurposed here for apply-attempt stdout capture under `PRDs/product/crmbuilder-v2/deposit-event-logs/`). Introduces one new relationship-kind vocabulary entry, `deposit_event_wrote_record`, a generic-verb cross-cutting kind spanning four target types (session, decision, planning_item, reference), with single-kind variant chosen over per-target-type variants on the strength of established generic-verb naming in the existing vocabulary (`references`, `is_about`, `supersedes`, `decided_in`). The inbound parent linkage uses the new kind `deposit_event_applies_close_out_payload` (registered here, named informationally in `close_out_payload.md` section 3.3.2). Field inventory: identity (identifier, title), content (description), classification (outcome — `success` \| `failure`), three diagnostic JSON fields (records_summary, error_info, apply_context), one file pointer (log_file_path), single timestamp (created_at). Deviation from base timestamps: no `updated_at` (record is immutable), no `deleted_at` (no soft-delete; full append-only). API surface reduced to POST + GET only — no PUT, no PATCH, no DELETE, no /restore — the smallest possible write API in V2. UI is a read-only audit log with no Create/Edit/Delete dialogs, Outcome filter combo in master-pane toolbar, descending sort by identifier (audit-log deviation from V2's default ascending), plain-text log_file_path with no in-app viewer. Fifteen acceptance criteria captured. Six decisions and zero planning items authored at conversation close; PI-022 continues to cover retroactive backfill for deposit_event records alongside the other governance entity types. Surfaces one cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation: the close_out_payload spec's at-most-one inbound `deposit_event_applies_close_out_payload` edge default needs to be relaxed to zero-or-more, per the close_out_payload spec section 3.8.3 invitation. |

---

## Change Log

**Version 1.0 (05-22-26 17:00):** Initial creation. Defines `deposit_event` as the V2 governance entity type that hosts the apply-event-record concept per DEC-118's two-entity deposit-bucket family — the durable record of a close_out_payload being applied to the governance database. Establishes seven fields plus one timestamp: identity (`deposit_event_identifier`, `deposit_event_title`), content (`deposit_event_description`), classification (`deposit_event_outcome` ∈ `{success, failure}`), three diagnostic JSON fields (`deposit_event_records_summary`, `deposit_event_error_info`, `deposit_event_apply_context`), one file pointer (`deposit_event_log_file_path`), and one timestamp (`deposit_event_created_at` — the apply-completion moment). Adopts the born-terminal append-only lifecycle: the record is created by the apply script as its last step, with outcome and all diagnostic fields populated; no intermediate `running` state; no updates, no deletes, no soft-delete. Establishes two new cross-spec precedents (born-terminal append-only with creation as the event moment; multi-event-per-target-record under born-terminal append-only). Introduces two new relationship-kind vocabulary entries, `deposit_event_wrote_record` (cross-cutting generic-verb kind, source `deposit_event`, target one of `session` / `decision` / `planning_item` / `reference`, semantics "this apply created this record") and `deposit_event_applies_close_out_payload` (parent linkage to the apply target). Both registered in this spec; the close_out_payload spec named the second informationally only. Adopts repo-relative file_path semantics from `reference_book.md` and `work_ticket.md` verbatim for `deposit_event_log_file_path`; canonical path pattern `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (parallel to `close-out-payloads/ses_NNN.json`). Declines `deposit_event_status` enum in favour of `_outcome` (semantic precision — the field is a permanent fact about an event, not a workflow state); declines `deposit_event_started_at` / `_completed_at` (collapsed into `_created_at`); declines `deposit_event_total_records_written` denormalized count (derivable from `records_summary` sum or `deposit_event_wrote_record` edge count); declines `deposit_event_notes` consultant scratchpad (incompatible with immutable record); declines base-schema `updated_at` and `deleted_at` (born-terminal append-only deviation). Reduced API surface: POST + GET only. POST is the only write operation; atomically creates the record plus its outbound references in one transaction; access layer enforces the outbound `deposit_event_applies_close_out_payload` edge required at all records and validates the conditional `error_info` null-when-success / non-null-when-failure rule. On `outcome = 'success'` POST against a `ready` close_out_payload, the access layer atomically transitions the close_out_payload to `applied`. On subsequent `outcome = 'success'` POST against an already-`applied` close_out_payload, no close_out_payload transition occurs (multi-event semantics — re-confirmation captured but doesn't move the terminal close_out_payload). UI is a read-only audit log: ListDetailPanel-backed master pane with columns identifier, title, outcome, created_at and Outcome filter combo "All / Success / Failure"; detail pane renders all fields read-only with no Create/Edit/Delete/Restore dialogs; right-click context menu reduced to "Copy identifier" / "Copy log path" lightweight read affordances; master pane sorts identifier descending (audit-log deviation, documented). Fifteen acceptance criteria captured. Six decisions (DEC-155 through DEC-160) and zero planning items authored at conversation close. Surfaces cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation: close_out_payload spec at-most-one inbound edge default relaxes to zero-or-more.

---

## 1. Purpose and Position

This document specifies the `deposit_event` entity type for V2's storage layer. It is the **sixth and final** schema spec produced by the governance-entity schema-design workstream — designed after `workstream.md`, `conversation.md`, `reference_book.md`, `work_ticket.md`, and `close_out_payload.md`, so that every prior spec is a settled referent and every cross-spec precedent in force after SES-052 is available to apply.

The workstream is governed by `governance-schema-workstream-plan.md`. Each schema spec conforms to the template in `governance-entity-schema-spec-guide.md`. Six specs total are produced — `workstream`, `conversation`, `reference_book`, `work_ticket`, `close_out_payload`, then this one — feeding a seventh build-planning conversation that integrates them into a coherent release. The build-planning conversation's kickoff is committed alongside this spec at `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md`.

`deposit_event`'s primary scope in this release is to host the apply-event-record concept per DEC-118's two-entity deposit-bucket family — the durable governance record of a close_out_payload being applied to the database. Where `close_out_payload` (the family-3 entity established in SES-052) carries the slip declaring what records should be written, `deposit_event` carries the record of when that apply happened, what its outcome was, what records it actually wrote, and (on failure) what went wrong. The pair implements DEC-118's two-entity split: the payload's lifecycle ends at production (and its `applied` transition is triggered externally); the deposit event's lifecycle is the apply moment itself, captured as a born-terminal append-only fact.

This spec is intentionally minimum-viable. A workflow-staged lifecycle (with `running` / `success` / `failure` / `aborted` states), per-target-type back-reference kinds, in-app log viewer affordance, and a UI Create dialog for backfill authoring are all deliberately out of scope; each is either rejected as architecturally incompatible with the born-terminal-append-only posture or deferred to a future release pending real-use signal.

This conversation **inherits six cross-spec precedents** in force after SES-052 and applies them throughout, and **establishes two new cross-spec precedents of its own**.

**Inherited precedents (six):**

- **References-edge over foreign-key for parent-child governance relationships** (DEC-124, SES-048). The deposit_event-to-close_out_payload relationship lives in `refs` with the new kind `deposit_event_applies_close_out_payload`, never as a foreign-key column. No `close_out_payload_id` column on the deposit_events table.
- **Truly-terminal terminal states** (DEC-125, SES-048). Deposit_event has no formal terminal states (the entity is born terminal in the practical sense), but the inherited principle informs the no-update / no-delete posture: once recorded, a fact cannot be retroactively altered.
- **Per-status lifecycle timestamps for workflow-shaped lifecycles** (DEC-126, SES-048). Applied on its own facts: deposit_event is **not** workflow-shaped — it is born-terminal append-only. The precedent therefore yields no per-status timestamps; only `_created_at` is meaningful. See Decision 5 in section 3.9.1.
- **Typed sequencing edges introduced when entity-family frequency justifies** (DEC-133, SES-049). Applied on its own facts: deposit_event back-references span four target types. The frequency-justified test points at "generic" (one cross-cutting kind) for this entity, not at four typed variants — see Decision 3 in section 3.9.1.
- **Documentary-vs-workflow distinction** (DEC-137, SES-050). Applied on its own facts: deposit_event is neither documentary nor workflow-shaped — it is born-terminal append-only, a third category this conversation establishes. The distinction informs the no-per-status-timestamp consequence.
- **Terminal-state consumption requires the inbound consumption edge** (DEC-143, SES-051). Realized on the close_out_payload side as the `applied`-requires-edge rule per SES-052's DEC-149; this spec is the counterpart that authors the inbound edge.

**New cross-spec precedents established by this conversation (two):**

- **Born-terminal append-only with creation as the event-recording moment.** A new lifecycle category alongside workflow-shaped (workstream, conversation, close_out_payload) and documentary (reference_book). Records of this category are POSTed at the moment the event being recorded completes; they carry one timestamp; they have no transitions, no PUT, no PATCH, no DELETE; their classification field carries a permanent fact (`_outcome` semantics) rather than a workflow state (`_status` semantics).
- **Born-terminal append-only entities admit multi-event-per-target-record.** Where a born-terminal append-only entity references another entity as its target-of-event (here, the close_out_payload being applied), the target may carry multiple inbound edges from multiple born-terminal records, one per occurrence of the event. The close_out_payload spec's safe-default at-most-one rule is relaxed to zero-or-more under this precedent. The cross-spec consistency finding for the build-planning conversation realizes this.

---

## 2. Summary

A `deposit_event` record in V2 represents one apply attempt against a close_out_payload — the durable governance record of when a payload was applied, whether the apply succeeded or failed, what records the apply created, what command line was invoked, and (on failure) what error stopped the work. Real examples already implicit in the project's history include the apply of COP-046 (SES-046's governance scoping payload, applied 05-20-26 at 21:51, outcome success, 15 records written — would be `DEP-046` or similar under backfill), the apply of COP-051 (SES-051's work_ticket schema close-out, applied 05-21-26, outcome success), and the apply of COP-052 (SES-052's close_out_payload schema close-out, applied 05-22-26, outcome success); thirty-plus earlier applies from the apply_close_out era follow the same structural shape. Each is an apply event with a definite outcome at a definite moment — but before this entity type lands, each exists only as a transient terminal output stream and (in the case of successful applies) as a transition of the close_out_payload's `status` to `applied`. The `deposit_event` entity makes apply attempts queryable as governance objects and gives failed attempts a durable record they currently lack.

The schema in this release is the thinnest shape that captures the apply-event-record concept faithfully: a human-readable title, a one-sentence description, a binary outcome enum (`success` \| `failure`), three structured JSON diagnostic fields (records-written counts by kind, structured error info on failure, apply-script invocation context), a repo-relative file_path pointing at the captured apply stdout, a single timestamp at the apply-completion moment, mandatory parent linkage via the inbound `deposit_event_applies_close_out_payload` edge to the close_out_payload the apply targeted, and many outbound `deposit_event_wrote_record` edges to each record the apply actually created. The schema deliberately omits a workflow status field (the record is born terminal — there is no transition between `running` and `success`), a denormalized total-records-written count (derivable from records_summary or the wrote_record edge count), a consultant scratchpad notes field (incompatible with immutable records), and the base-schema `updated_at` and `deleted_at` columns (full append-only). The API surface is reduced accordingly to POST + GET only — the smallest possible write API in V2. The UI is a read-only audit log with no Create/Edit/Delete dialogs.

This spec also surfaces one cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation: the close_out_payload spec's `at-most-one` inbound `deposit_event_applies_close_out_payload` edge default needs to relax to `zero-or-more` to admit multi-event-per-payload re-apply semantics. The close_out_payload spec section 3.8.3 explicitly invited that relaxation to be settled here; this conversation settles it.

---

## 3. Schema Specification

### 3.1 Identity

| Field | Value |
|-------|-------|
| Entity type name (storage) | `deposit_event` |
| Display name (singular) | Deposit Event |
| Display name (plural) | Deposit Events |
| Identifier prefix | `DEP` |
| Identifier format | `DEP-NNN`, zero-padded to 3 digits (e.g., `DEP-001`, `DEP-054`) |
| Identifier auto-assignment | Server-side on POST omission; helper at `GET /deposit-events/next-identifier` |

**Identifier-prefix posture.** `DEP` is three letters, matching the dominant three-letter precedent (DEC, SES, REF, COP, plus the two-letter exceptions WS, WT, RB and the four-letter PROC). Pairs naturally with `COP` (its family-3 counterpart) for the deposit-bucket reading: a `COP-NNN` payload is applied by `DEP-NNN-or-other` events. The two-letter form `DP` was not seriously considered (too short; reads as initials). Four- and five-letter alternatives `DEPT`, `DEPOS`, `EVT`, `APPLY` were rejected: `DEPT` visually collides with "Department" in unrelated contexts, `DEPOS` adds length without disambiguation, `EVT` reads as generic "event" losing the deposit-bucket pairing, and `APPLY` reads as a verb. `DEP` survives the collision check against the current prefix list (DEC, SES, RSK, PI, TOP, REF, CHR, STA, DOM, ENT, PROC, CRMC, ENG, WS, CONV, RB, WT, COP). Per DEC-123's affirmation that each downstream conversation makes its own prefix-length call within the 2-to-5 letter range, three letters is appropriate here.

### 3.2 Fields

Field naming follows the parent-prefix convention per DEC-046: all fields including identifier, file pointer, and timestamps are prefixed `deposit_event_`.

#### 3.2.1 Identity fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_identifier` | TEXT | yes | server-assigned | `^DEP-\d{3}$`, unique | The deposit event identifier in `DEP-NNN` format. Server-assigned when omitted from POST body; helper endpoint `GET /deposit-events/next-identifier` returns the next available value. |
| `deposit_event_title` | TEXT | yes | — | non-empty trimmed | Human-readable handle for the deposit event. Auto-generated by the apply script at POST time; format `"Apply of <COP_identifier>, <ISO 8601 UTC timestamp>"` (e.g., `"Apply of COP-046, 2026-05-20 21:51 UTC"`). Stored as text rather than computed at render time so master-pane list rendering doesn't require runtime joining against the parent close_out_payload. |

#### 3.2.2 Content fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_description` | TEXT | yes | — | non-empty trimmed | One-paragraph description of the apply attempt. Auto-generated by the apply script at POST time from the other fields (target COP, outcome, records-written summary, error summary on failure). Example: `"Applied COP-046 to CRMBUILDER engagement. Outcome: success. Records written: 1 session, 6 decisions, 1 planning item, 7 references."` On failure: `"Applied COP-046 to CRMBUILDER engagement. Outcome: failure at step decisions (HTTP 422 on DEC-117 — validation error). Records written before failure: 1 session."` Plain text in this release. |

**No `deposit_event_notes` field.** Predecessor entities (workstream, conversation, reference_book, work_ticket, close_out_payload) carry a consultant scratchpad `_notes` field for content the consultant authors after the record is created. Deposit_event records are immutable after creation — there is no opportunity for the consultant to subsequently author notes. The field is omitted from this entity in this release.

#### 3.2.3 Classification fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_outcome` | TEXT | yes | — | enum: `success` \| `failure` | Permanent fact about the apply event. Born-terminal: the value is set at record creation (by the apply script) and never changes. Both values are terminal; there is no transition between them. See section 3.4 for the full discussion of the born-terminal append-only lifecycle category this spec establishes. |

**Field name `_outcome` rather than `_status`.** Workstream, conversation, reference_book, work_ticket, and close_out_payload all carry a `_status` field representing a workflow state with valid transitions. Deposit_event's classification field carries a permanent fact about a completed event, not a workflow state. The naming distinction is intentional — `_outcome` reads as "the result of an event that happened"; `_status` reads as "the current position in a workflow that may move." Adopting `_outcome` here is a documented departure from the cross-spec naming convention, justified by the semantic shape (born-terminal append-only) this conversation establishes as a new precedent. See Decision 4 in section 3.9.1.

#### 3.2.4 Relationship fields

None. Both the parent linkage to the close_out_payload being applied and the back-references to records the apply created live in the universal `refs` table per the inherited references-edge precedent (DEC-124, SES-048). See section 3.3 for the full relationship vocabulary.

#### 3.2.5 File pointer field

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_log_file_path` | TEXT | yes | — | non-empty trimmed; must be a repo-relative path (no leading slash, no `..` segments, no scheme prefix); unique within the engagement | Repo-relative path to the captured apply stdout log file (e.g., `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_054.log`). The apply script writes its full stdout to this file as the apply runs; the file is committed alongside the deposit_event POST. Resolution at use time is performed against the consuming repository's root — typically the crmbuilder repo for dogfood deposit events and the client repo for engagement-specific records. The path is not validated for existence at write time. The historical convention is `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` where `NNN` is the deposit event identifier number (matching the convention `close-out-payloads/ses_NNN.json` for close_out_payload file_paths); the schema does not enforce this convention at the validation layer. The same `file_path` value may legally coexist as a `work_ticket_file_path`, `reference_book_file_path`, or `close_out_payload_file_path` value on a parallel record per the section-2 boundary discipline; uniqueness is within the deposit_events table only, not across the union of file paths. |

**Path-semantics parity with predecessor specs.** The `deposit_event_log_file_path` column follows the same repo-relative semantics as `reference_book_file_path`, `work_ticket_file_path`, and `close_out_payload_file_path`. The four columns are independent; the cross-table coexistence rule is structural admission, not an expected pattern.

**No `payload_content` analog.** Unlike close_out_payload whose `_file_path` points at the canonical JSON file with the entity's authoritative content, deposit_event's `_log_file_path` points at a captured stdout transcript — diagnostic detail, not authoritative content. The authoritative content of a deposit event lives in the record's own fields (outcome, records_summary, error_info, apply_context). The log file is an artifact of the apply run, captured for forensic value. This distinction informs the field's role (diagnostic supplement) rather than its semantics (path-shape is identical).

#### 3.2.6 Diagnostic JSON fields

Three JSON columns carry the structured diagnostic content of the apply attempt. JSON shape is documented here and shared by the apply script and the access-layer validators (typically via a Python helper module); the database column stores JSON as text without SQL-level shape enforcement.

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_records_summary` | TEXT (JSON) | yes | — | valid JSON object; keys are entity-type plurals (`sessions`, `decisions`, `planning_items`, `references`); values are non-negative integers; sum must equal the count of outbound `deposit_event_wrote_record` edges from the same record (access-layer cross-check) | Counts of records created by this apply attempt, grouped by target entity type. Example for a successful SES-046-style apply: `{"sessions": 1, "decisions": 6, "planning_items": 1, "references": 7}`. Example for a re-apply where everything was already present (all 409-SKIPped): `{"sessions": 0, "decisions": 0, "planning_items": 0, "references": 0}`. Example for a failed apply at step `decisions`: `{"sessions": 1, "decisions": 0, "planning_items": 0, "references": 0}`. The summary is derivable from the wrote_record edge count, but storing it denormalized avoids a count-by-target-type query on every list/detail render. |
| `deposit_event_error_info` | TEXT (JSON) | conditional | null | when `_outcome = 'success'`: must be null; when `_outcome = 'failure'`: must be a valid JSON object containing required `kind`, `message`, `step`, with optional `http_status` and `traceback` | Structured error info, populated only when `_outcome = 'failure'`. Shape: `{"kind": "<http_error|validation_error|connection_failure|unknown>", "message": "<single-line error summary>", "step": "<section name from apply script: session\|decisions\|planning_items\|references\|deposit_event>", "http_status": <int when http_error>, "traceback": "<python traceback when available>"}`. Example: `{"kind": "http_error", "message": "Validation failed on DEC-117 — field 'rationale' required", "step": "decisions", "http_status": 422}`. |
| `deposit_event_apply_context` | TEXT (JSON) | yes | — | valid JSON object with required `apply_script_version`, `invocation`, `runner` | Apply invocation context. Shape: `{"apply_script_version": "<crmbuilder-v2 version string>", "invocation": "<full command line>", "runner": "<claude_code\|manual_curl\|backfill_script\|ui>"}`. Example: `{"apply_script_version": "0.1.0", "invocation": "uv run python scripts/apply_close_out.py ../PRDs/product/crmbuilder-v2/close-out-payloads/ses_046.json", "runner": "claude_code"}`. Captures the apply's provenance for forensic and reproducibility purposes. |

**No SQL-level JSON shape enforcement.** Validation of these shapes is the access layer's responsibility, not the database's. SQLite's JSON1 extension supports shape checks but introduces engine-specific SQL that complicates portability. The Python validator pattern (used elsewhere in V2 for similar JSON content) is the canonical enforcement. Future shape evolution is non-breaking — additive keys are admitted without migration.

#### 3.2.7 Timestamp fields

| Field name | Type | Required | Default | Validation | Description |
|------------|------|----------|---------|------------|-------------|
| `deposit_event_created_at` | DATETIME | yes | server-set on insert | ISO 8601 UTC | THE event moment — the timestamp at which the apply completed (success or failure) and the deposit_event record was POSTed. The apply script captures this server-side at POST time; not user-editable. |

**Deviation from base-schema timestamps.** Predecessor entities inherit base `created_at`, `updated_at`, `deleted_at` per the spec guide section 3.2.5. Deposit_event deviates: `_updated_at` is not present (the record is born terminal and never updated), and `_deleted_at` is not present (no soft-delete under full append-only — see section 3.4). Implementation choice between "omit the columns from the table entirely" and "include them in the base schema but lock them to null/equal-to-created" is a build-planning detail. The spec declares the conceptual behavior: this entity has no `updated_at` semantics (never updated) and no `deleted_at` semantics (never deleted). The deviation is the precedent being established — born-terminal append-only entities omit update and delete semantics.

**No per-status lifecycle timestamps.** Predecessor workflow-shaped entities (workstream, conversation, close_out_payload, work_ticket) carry per-status timestamps (`_ready_at`, `_applied_at`, `_completed_at`, etc.) per DEC-126. Deposit_event has no workflow states, so no per-status timestamps apply. The single `_created_at` timestamp IS the event moment under the born-terminal precedent.

**No storage-level length caps** on text or JSON fields, matching the precedents from the predecessor specs. UI placeholder text provides soft guidance where applicable.

### 3.3 Relationships

#### 3.3.1 Outgoing relationships

Two outgoing reference kinds introduced by this spec, both modelled as references-table edges per the inherited DEC-124 references-edge precedent. The deposit_event entity introduces no foreign-key columns and no hierarchy.

**Parent linkage (apply target).** Every deposit_event record must have exactly one outbound reference edge identifying the close_out_payload the apply targeted. The relationship is required at every record — a deposit_event with no target close_out_payload is malformed by family-3 definition (per DEC-118, a deposit_event records "a close_out_payload being applied"; the close_out_payload being applied is part of the deposit_event's identity).

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `deposit_event_applies_close_out_payload` | `deposit_event` | `close_out_payload` | This deposit_event records the application of the target close_out_payload. Cardinality from this side: a deposit_event has exactly one outbound edge of this kind (enforced at the access layer). Cardinality from the target side: a close_out_payload may carry zero or more inbound edges of this kind (one per apply attempt) — see section 3.4.4 for the multi-event-per-payload precedent. The edge is required at every deposit_event record. |

**Back-references to records written.** Every record the apply actually created (HTTP 200 or 201 from the API; not HTTP 409 SKIP responses) is back-referenced via an outbound edge of kind `deposit_event_wrote_record` from this deposit_event to the target record. The relationship realizes Decision 3: the cross-cutting generic-verb kind spans four target entity types in a single vocabulary entry.

| relationship_kind | source entity type | target entity type | semantics |
|-------------------|--------------------|--------------------|-----------|
| `deposit_event_wrote_record` | `deposit_event` | `session` \| `decision` \| `planning_item` \| `reference` | This deposit_event's apply attempt created the target record (HTTP 200/201 response). Cardinality from this side: a deposit_event has zero or more outbound edges of this kind (zero when the apply 409-SKIPped everything — a re-confirmation; many in the typical first-apply case). Cardinality from the target side: each target record has zero or one inbound edge of this kind (zero when the record was created outside the apply path — e.g., via the desktop UI or a one-off backfill script that doesn't author the back-edge; exactly one when created via apply). |

**Single generic kind over per-target-type variants.** The Decision 3 sub-question on this conversation considered four variants: a single generic `deposit_event_wrote_record` kind, four per-target-type kinds (`deposit_event_wrote_session`, etc.), a JSON column on the deposit_events table, and a dedicated back-reference table. The single generic kind was chosen on the strength of (1) cross-cutting nature — the relationship intentionally spans multiple target types and a single conceptual kind captures that intent, (2) established naming precedent in the existing vocabulary (`references`, `is_about`, `supersedes`, `decided_in` all use generic-verb naming without target-type binding), and (3) minimum-viable schema growth (one vocab entry plus one `_kinds_for_pair` clause covering four pairs).

**Supersession.** Not applicable. Deposit_event records cannot be superseded — a born-terminal append-only fact cannot be replaced. A re-apply of the same close_out_payload produces a new deposit_event record; the prior record stands unchanged. The supersession-requires-edge pattern that all predecessor specs adopt is inapplicable here.

#### 3.3.2 Incoming relationships

Deposit_event is the target of zero incoming new reference kinds in this release. Generic `references` and `is_about` kinds admit citation from any other governance entity by the existing default `_kinds_for_pair` rules; no per-pair registration is required.

#### 3.3.3 Hierarchy

Deposit_event does not use the self-referential parent-child hierarchy pattern. Apply events are flat; there is no intra-type relationship between deposit_event records. Consistent with workstream, conversation, reference_book, work_ticket, and close_out_payload — none adopted hierarchy.

#### 3.3.4 New reference vocabulary additions this spec requires

The following additions are named here and aggregated by the build-planning conversation into one consolidated `vocab.py` update plus one Alembic migration on the `refs.relationship_kind` CHECK constraint, alongside the additions named by the other governance schema specs.

| Add to | Value | Rationale |
|--------|-------|-----------|
| `REFERENCE_RELATIONSHIPS` | `deposit_event_applies_close_out_payload` | Outbound parent linkage from a deposit_event to the close_out_payload it applied. Required at all records; exactly one outbound edge per deposit_event. |
| `REFERENCE_RELATIONSHIPS` | `deposit_event_wrote_record` | Outbound back-reference from a deposit_event to a record the apply created. Cross-cutting generic-verb kind; zero or more per deposit_event. |
| `ENTITY_TYPES` | `deposit_event` | This entity type. |
| `_kinds_for_pair` | `if source_type == 'deposit_event' and target_type == 'close_out_payload': kinds.add('deposit_event_applies_close_out_payload')` | Source-target constraint binding the parent-linkage kind to the matching pair only. |
| `_kinds_for_pair` | `if source_type == 'deposit_event' and target_type in ('session', 'decision', 'planning_item', 'reference'): kinds.add('deposit_event_wrote_record')` | Source-target constraint binding the back-reference kind to its four valid target types in a single clause. |

The existing `references` and `is_about` kinds admit generic citations to and from deposit_event without additional clauses.

### 3.4 Lifecycle

#### 3.4.1 Lifecycle category — born-terminal append-only (new cross-spec precedent)

Deposit_event establishes a new lifecycle category — **born-terminal append-only** — alongside the existing workflow-shaped category (workstream, conversation, close_out_payload, work_ticket) and the documentary category (reference_book). The category's defining properties:

- **Born-terminal.** The record's classification field carries a permanent fact about an event, not a workflow state. The fact (`_outcome` value) is set at record creation by the authoring process (the apply script) and never changes. There are no transitions between values, no `running` or `in-flight` intermediate state, and no terminal-state-required-edge rules to enforce.
- **Append-only.** Once created, the record is never updated (no PUT, no PATCH) and never deleted (no DELETE, no soft-delete, no `_deleted_at`). The API surface admits POST and GET only. The record is immutable.
- **Creation IS the event-recording moment.** The record's `_created_at` timestamp is the timestamp of the event being recorded. There is no separate "started at" / "completed at" semantics — the event happens, the record is POSTed as the event's last step (carrying all final-state fields), and the moment of POST is the moment of the event.

This category differs from workflow-shaped in three ways: no `_status` field with transitions (replaced by `_outcome` as a permanent fact), no per-status timestamps (a single `_created_at` is sufficient because there is only one moment), no edge-required-at-terminal rules (the record is immutable from creation). It differs from documentary in two ways: no version history (the record is never revised), no "in force at" semantics (the record is a fact about a moment, not a long-lived reference).

**Why the precedent is needed.** Deposit_event records the apply attempts of close_out_payloads. An apply attempt is a definite event with a definite outcome at a definite moment — not a workflow that progresses through states, not a document that gets revised over time. The born-terminal append-only category fits this shape natively; forcing it into a workflow-shaped lifecycle (`running` → `success` / `failure` / `aborted`) would introduce a `running` state that exists for ~3 seconds during apply and is essentially never observed in operation, while complicating the API with PUT/PATCH endpoints and the UI with editable dialogs. Forcing it into a documentary lifecycle would introduce version-history machinery that has no operational meaning for a fact-about-an-event.

#### 3.4.2 Outcome values

| Outcome value | Description |
|---------------|-------------|
| `success` | The apply attempt completed without error. Every record in the payload was POSTed and either created (HTTP 200/201) or already-present (HTTP 409 SKIP). The `error_info` field is null. The `records_summary` may be all-zero (re-confirmation case — every record was already present) or non-zero (first apply case — new records were created). |
| `failure` | The apply attempt stopped before completing every record. The `error_info` field is non-null and contains the structured error detail. The `records_summary` reflects records created before the failure (often partial). |

Both values are terminal/born-state; no transition between them is admitted. A failed apply followed by a successful re-apply creates a NEW deposit_event record with `outcome = 'success'`; the prior failure record stands unchanged.

#### 3.4.3 The applied-requires-edge rule realized

The close_out_payload spec's section 3.4.3 established the applied-requires-edge rule: a close_out_payload's transition to `applied` requires an inbound `deposit_event_applies_close_out_payload` edge from a deposit_event record with `outcome = 'success'`. This spec is the counterpart that authors that inbound edge. The atomicity is preserved by the access layer: on a successful deposit_event POST whose target close_out_payload is at status `ready`, the access layer atomically (a) creates the deposit_event record, (b) creates the outbound `deposit_event_applies_close_out_payload` edge, (c) creates the outbound `deposit_event_wrote_record` edges for each created record, and (d) transitions the close_out_payload's status to `applied`.

Sequence on POST `/deposit-events` with `outcome = 'success'`:

1. Access layer validates the request body shape (required fields, `error_info` null, conditional checks).
2. Access layer resolves the target close_out_payload's current status.
3. If COP is at `ready`: access layer enters a single transaction that creates the deposit_event row, all reference edges, and updates the close_out_payload's status to `applied` plus its `close_out_payload_applied_at` timestamp.
4. If COP is at `applied` (multi-event-per-payload re-confirmation case per section 3.4.4): access layer enters a transaction that creates the deposit_event row and all reference edges; the close_out_payload's row is not touched (already terminal).
5. If COP is at `drafted`, `cancelled`, or `superseded`: HTTP 422 with `{"error": "deposit_event_target_close_out_payload_not_ready_or_applied"}` — the apply path requires the target to have reached `ready` first, and terminal-but-not-`applied` close_out_payloads are not valid apply targets.

Sequence on POST with `outcome = 'failure'`:

1. Access layer validates body, including the conditional `error_info` non-null rule.
2. Access layer resolves target close_out_payload (any status admitted — failed apply against any pre-state is a recordable fact).
3. Access layer enters a transaction that creates the deposit_event row and the parent-linkage edge. No `deposit_event_wrote_record` edges typical here (the failure may have produced zero records, or some partial set authored before the failure point — the apply script populates accordingly). The close_out_payload's row is not touched.

#### 3.4.4 Multi-event-per-payload precedent

Per Decision 2, a close_out_payload may be the target of zero or more inbound `deposit_event_applies_close_out_payload` edges — one per apply attempt. The cross-spec consequence:

- **Close_out_payload spec section 3.3.2 and section 3.4.3** carry at-most-one-inbound-edge language that this conversation supersedes. The relaxation was explicitly invited by close_out_payload section 3.8.3 ("the deposit_event-side spec may pre-emptively support it from inception. The decision belongs to deposit_event.md's conversation"). This conversation settles the question at zero-or-more.
- **No close_out_payload spec amendment is performed inline by this conversation** per the kickoff's "do not amend inline here" rule. The relaxation surfaces as a cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation, which is the gate that resolves such inter-spec inconsistencies.

**Operational semantics under multi-event-per-payload.**

- First apply: creates DEP-N with `outcome = 'success'` and edges to created records; transitions COP from `ready` to `applied`.
- Subsequent re-apply (verification, redeploy, debugging): creates DEP-N+M with `outcome = 'success'`, typically zero outbound `deposit_event_wrote_record` edges (everything already present 409-SKIPs); COP stays at `applied`. The records_summary will be `{"sessions": 0, ...}`.
- Failed apply between first and re-confirmation: creates DEP-N+K with `outcome = 'failure'` and structured error info; COP transitions to `applied` was already triggered by the first DEP and is not affected.
- Apply attempts against a never-applied COP: each failure creates a deposit_event record with `outcome = 'failure'`; the COP stays at `ready` until a successful apply triggers the transition.

#### 3.4.5 Soft-delete semantics

**None.** Deposit_event is fully append-only — no soft-delete, no `_deleted_at` field, no `/restore` endpoint, no DELETE on the API. This is the strongest possible append-only posture in V2, stronger than work_ticket and close_out_payload (which adopt soft-delete distinct from their `cancelled` lifecycle status).

**Why no soft-delete.** A deposit_event records a fact about an event that happened. The act of "removing the record from default views" — soft-delete's purpose elsewhere — is incompatible with the auditing intent of this entity type. Erroneous records (e.g., a deposit_event created by an accidentally-triggered apply script run) are exceptionally rare in practice (the apply script runs only when a consultant invokes it); when they do occur, the appropriate response is to leave the record visible with a `notes`-equivalent annotation. But deposit_event also has no `_notes` field (see section 3.2.2 rationale), so the annotation path is itself unavailable. The full-append-only posture is intentional: it makes the deposit_events table the most trustworthy possible source of "what apply attempts have run against this engagement's governance database."

**Erroneous-record remediation.** In the rare case where a deposit_event record is created in error (e.g., a test invocation of the apply script that should not have produced a governance record), the available remediations are: (a) accept the record as a fact and proceed — the record's `apply_context.runner` field captures the provenance, which serves as the audit trail of the error; (b) for a development/test engagement, drop the database and reinitialize; (c) if a real need for record removal emerges in production engagements, address it as a future-release schema change with explicit migration semantics. None of these are admitted in v1 of this entity.

### 3.5 API Surface

#### 3.5.1 Endpoints

Reduced API surface — POST and GET only. The smallest possible write API in V2.

| Method | Path | Body | Notes |
|--------|------|------|-------|
| GET | `/deposit-events` | — | List. Supports `?outcome=success` or `?outcome=failure` query filter (single value or comma-separated list). No `?include_deleted` flag (no soft-delete exists). |
| GET | `/deposit-events/{identifier}` | — | Single fetch. Returns 404 if not found. |
| POST | `/deposit-events` | full deposit_event JSON; identifier optional; may include `references` array | Create. The only write operation. Identifier server-assigned when omitted. Required body fields: `_title`, `_description`, `_outcome`, `_records_summary`, `_apply_context`, `_log_file_path`. Conditional: `_error_info` (required when `_outcome = 'failure'`; must be null when `_outcome = 'success'`). The body must include a `references` array containing exactly one outbound `deposit_event_applies_close_out_payload` edge (target close_out_payload identifier required), plus zero or more outbound `deposit_event_wrote_record` edges. Access layer validates the body, the conditional `_error_info` rule, the exactly-one parent-edge requirement, the target close_out_payload's existence and status (per section 3.4.3), and the sum-of-records_summary-equals-count-of-wrote_record-edges cross-check. On `outcome = 'success'` against a `ready` close_out_payload: atomically creates the record, the edges, and transitions the close_out_payload to `applied`. On `outcome = 'success'` against an `applied` close_out_payload: creates the record and edges; close_out_payload untouched. On `outcome = 'failure'`: creates the record and parent edge; close_out_payload untouched regardless of pre-state. |
| GET | `/deposit-events/next-identifier` | — | Returns `{"next": "DEP-NNN"}` for the next available identifier. |

**Endpoints NOT exposed.** PUT, PATCH, DELETE, and POST `/restore` are absent from the route table entirely. Calls to these paths return HTTP 405 (or HTTP 404 if the framework's missing-route handling resolves that way; implementation choice for build-planning). Documentation must be explicit that these methods are intentionally absent, not accidentally omitted.

All responses use the `{data, meta, errors}` envelope per existing V2 convention.

#### 3.5.2 Identifier auto-assignment

Default V2 server-side auto-assignment on POST omission. The helper endpoint `GET /deposit-events/next-identifier` exposes the same computation for clients that need the identifier before submitting.

The apply script's modification (per Decision 2's Option C) is the canonical writer: at the apply's last step, the script computes the records_summary from the per-record HTTP responses captured during apply, populates `apply_context` from its own invocation context, sets `outcome` and `error_info` from the apply's overall result, captures the log file path (already being written to during apply), constructs the references array (one parent edge + N wrote_record edges), and POSTs to `/deposit-events`. The identifier comes back in the response; the script logs it and exits.

### 3.6 User Interface Considerations

Read-only audit log shape. The default UI layout per spec guide section 3.6 is followed for sidebar position, master pane mechanics, and reference rendering; the read-only-and-no-Create-dialog posture is the deviation, justified by the born-terminal append-only entity nature.

#### 3.6.1 Sidebar

The Deposit Events panel goes in the Governance sidebar group, after the Close-Out Payloads panel (the family-3 counterpart). Position within the group follows workstream order (workstream, conversation, reference book, work ticket, close-out payload, deposit event) at the end of the existing Governance group. The build-planning conversation may introduce a sub-grouping if the resulting Governance group becomes hard to scan.

#### 3.6.2 Master pane

`ListDetailPanel`-backed list with columns:

| Column | Header | Width | Notes |
|--------|--------|-------|-------|
| `deposit_event_identifier` | Identifier | narrow | Sortable; default sort (descending — see deviation note below). |
| `deposit_event_title` | Title | wide | Human-readable handle (e.g., `"Apply of COP-046, 2026-05-20 21:51 UTC"`). |
| `deposit_event_outcome` | Outcome | narrow | Badge styling — green for `success`, red for `failure`. |
| `deposit_event_created_at` | Created | narrow | Localized date/time. |

**Default sort: identifier descending (deviation from V2 convention).** All other entity panels in V2 sort by identifier ascending. Deposit events are an audit log; the natural read pattern is newest-first (most recent apply at top). The descending sort is documented in this spec as a deliberate deviation tied to the audit-log entity nature; the deviation is itself a recognizable signal to the consultant that "this is a log, not a workspace."

**Outcome filter combo in the master-pane toolbar.** A single-select combo offering "All / Success / Failure" lets the consultant scope the visible list. Parallel to the Status filter combo on the close_out_payload panel; operationally meaningful for "show me only the failed applies" queries.

**Right-click context menu.** Reduced from the default New / Edit / Delete / Restore set to lightweight read affordances only:

- **Copy identifier** — copies the deposit_event identifier to clipboard
- **Copy log path** — copies `deposit_event_log_file_path` to clipboard for terminal/editor use

No New, Edit, Delete, or Restore actions (born-terminal append-only — no UI authoring path).

#### 3.6.3 Detail pane

Vertical read-only layout, fields in section-3.2 order:

1. `deposit_event_identifier` — read-only label.
2. `deposit_event_title` — read-only label.
3. `deposit_event_outcome` — read-only badge (green/red styling).
4. `deposit_event_created_at` — read-only label, localized date/time.
5. `deposit_event_description` — read-only multi-line label.
6. `deposit_event_records_summary` — rendered as a small key-value table (entity-type plural → count). Visible regardless of outcome.
7. `deposit_event_log_file_path` — read-only plain-text label showing the repo-relative path. No in-app viewer affordance in this release (see section 3.8.3 for the deferred future-add).
8. `deposit_event_apply_context` — read-only display with `apply_script_version`, `invocation`, `runner` shown as labeled fields. The `invocation` field's long command-line value is wrapped or scrollable.
9. `deposit_event_error_info` — read-only display rendered only when `_outcome = 'failure'`. Sub-fields (`kind`, `message`, `step`, `http_status`, `traceback`) shown as labeled fields with the traceback in a scrollable/expandable region.
10. `ReferencesSection` widget — renders the outbound `deposit_event_applies_close_out_payload` edge prominently at top because it is the family-defining parent linkage. Below it: outbound `deposit_event_wrote_record` edges grouped by `target_type`, each group with a count badge (e.g., "Sessions (1)", "Decisions (6)", "Planning Items (1)", "References (7)"), and within each group a clickable list of target identifiers. The "Add reference" affordance from the user-interface version 0.3 references-create dialog is **disabled** on this panel — all reference creation flows through the apply script's POST. Generic `references` and `is_about` edges (inbound or outbound from other governance entities) render below in the standard ReferencesSection pattern.

#### 3.6.4 Create / Edit / Delete dialogs

**None.** Deposit_event has no Create dialog, no Edit dialog, no Delete dialog, no Restore action. The strict no-Create-dialog posture is a deliberate deviation from predecessor entity UIs, justified by:

- Born-terminal append-only — the record is created exclusively by the apply script at apply completion.
- No update path — no Edit dialog is meaningful.
- No soft-delete — no Delete or Restore dialog is meaningful.
- Backfill authoring (PI-022 scope) is handled via a one-off script, not via a UI dialog — see section 3.8.2.

**Deviation rationale documented.** The spec guide's default layout (section 3.6) names Create / Edit / Delete dialogs as standard. Omitting all three is the deviation; the rationale above is the documented justification.

### 3.7 Acceptance Criteria

The entity type is correctly implemented in the eventual build when all of the following are testably true:

1. **Schema migration applies cleanly.** The `deposit_events` table is created with all documented columns (`_identifier`, `_title`, `_description`, `_outcome`, `_records_summary`, `_error_info`, `_apply_context`, `_log_file_path`, `_created_at`). No `_updated_at`, `_deleted_at`, or per-status timestamp columns are present.

2. **Vocabulary additions land.** `deposit_event` is added to `ENTITY_TYPES`; `deposit_event_applies_close_out_payload` and `deposit_event_wrote_record` are added to `REFERENCE_RELATIONSHIPS`; `_kinds_for_pair` rules cover (deposit_event, close_out_payload) for the parent-linkage kind and (deposit_event, session/decision/planning_item/reference) for the back-reference kind. The Alembic migration on `refs.relationship_kind`'s CHECK constraint admits both new kinds.

3. **POST `/deposit-events` creates a record with all required fields populated.** Identifier server-assigned when omitted; `_outcome` enum validation rejects values other than `success` or `failure`.

4. **Conditional `error_info` rule enforced.** POST with `_outcome = 'success'` and non-null `_error_info` returns HTTP 422 `{"error": "deposit_event_error_info_must_be_null_when_outcome_is_success"}`. POST with `_outcome = 'failure'` and null `_error_info` returns HTTP 422 `{"error": "deposit_event_error_info_required_when_outcome_is_failure"}`.

5. **Parent-linkage edge required.** POST missing the outbound `deposit_event_applies_close_out_payload` edge returns HTTP 422 `{"error": "deposit_event_requires_applies_close_out_payload_edge"}`. POST with multiple outbound edges of this kind returns HTTP 422 `{"error": "deposit_event_single_parent_violation"}`.

6. **References array atomically processed.** POST with a `references` array containing the parent edge plus N `deposit_event_wrote_record` edges atomically creates the deposit_event record and all N+1 edges in a single transaction.

7. **Successful apply against ready COP transitions COP atomically.** POST with `_outcome = 'success'` and parent edge targeting a `ready` close_out_payload atomically creates the deposit_event, creates the edges, and transitions the close_out_payload to `applied` (setting `close_out_payload_applied_at` server-side).

8. **Successful apply against already-applied COP succeeds (multi-event).** POST with `_outcome = 'success'` and parent edge targeting an `applied` close_out_payload succeeds; a second (or third, etc.) deposit_event record is created with its own edges; the target close_out_payload remains at `applied` without any timestamp or status change.

9. **Failed apply leaves COP unchanged.** POST with `_outcome = 'failure'` and parent edge targeting any close_out_payload status leaves the close_out_payload's `_status` and lifecycle timestamps unchanged.

10. **Records-summary cross-check enforced.** POST where the sum of values in `_records_summary` does not equal the count of outbound `deposit_event_wrote_record` edges returns HTTP 422 `{"error": "deposit_event_records_summary_mismatch_with_wrote_record_edges"}`.

11. **PUT / PATCH / DELETE / restore return HTTP 405 (or 404).** No edit, soft-delete, or restore path exists. The route table does not register handlers for these methods.

12. **GET endpoints honor envelope and filter.** `GET /deposit-events` returns the `{data, meta, errors}` envelope with a list; `?outcome=success` and `?outcome=failure` filters apply correctly. `GET /deposit-events/{identifier}` returns single-record envelope; 404 on not-found. `GET /deposit-events/next-identifier` returns `{"next": "DEP-NNN"}`.

13. **UI panel appears in the correct sidebar position.** Deposit Events panel renders in the Governance sidebar group after Close-Out Payloads. Master pane lists records with the documented four columns; default sort is identifier descending; Outcome filter combo works for All / Success / Failure scoping.

14. **UI detail pane renders all fields read-only.** No Create, Edit, Delete, or Restore dialogs are wired. Right-click context menu offers "Copy identifier" and "Copy log path" only. Reference section renders the parent-linkage edge prominently at top and groups `deposit_event_wrote_record` edges by target type with count badges. "Add reference" is disabled.

15. **Apply script captures stdout to log file and POSTs deposit_event at end.** The modified `apply_close_out.py` (per the build-planning conversation's slice) writes its full stdout to `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` as the apply runs, computes `_records_summary` from the per-record HTTP responses, populates `_apply_context` from invocation, sets `_outcome` and `_error_info` from the overall apply result, and POSTs the deposit_event record at end with the references array including parent edge and wrote_record edges. The log file is committed alongside the deposit_event POST.

### 3.8 Open Questions and Deferred Decisions

#### 3.8.1 For the build-planning conversation to settle

**[build-planning] Cross-spec consistency reconciliation: close_out_payload at-most-one inbound edge relaxation.** Decision 2 of this conversation (multi-event-per-payload) supersedes the close_out_payload spec's at-most-one default. The close_out_payload spec section 3.3.2 and section 3.4.3 carry language that needs revision. Per the kickoff's no-inline-amendment rule, this conversation surfaces the inconsistency rather than editing the close_out_payload spec directly. The build-planning conversation's section 7.2 cross-spec consistency check is the proper gate to reconcile; the resolution is to revise the close_out_payload spec text to admit zero-or-more inbound edges of kind `deposit_event_applies_close_out_payload`, with the `applied` transition fired on the first such edge with `outcome = 'success'` from a deposit_event record and subsequent edges admitted without further close_out_payload state change.

**[build-planning] Apply script modification slice.** The apply script (`crmbuilder-v2/scripts/apply_close_out.py`) needs to be modified to (a) write its stdout to the deposit-event-logs/dep_NNN.log file as apply runs, (b) capture per-record HTTP responses (200/201/409) for the records_summary computation, (c) determine the next DEP identifier via `GET /deposit-events/next-identifier`, (d) POST the deposit_event record at the apply's last step with all fields populated and the references array fully assembled. This is a Claude Code slice; design and execution belong to build-planning.

**[build-planning] `deposit-event-logs/` directory tracking.** Whether the captured log files are git-tracked (committed alongside the payload commit) or gitignored (treated as ephemeral local artifacts with the repo-relative path recorded but the file not committed) is a build-planning policy call. Tracking captures the diagnostic detail durably; ignoring keeps the repo lean. Recommendation in this spec's section 2 framing (file path stored for forensic value) leans toward tracking, but the policy is build-planning's to set.

**[build-planning] Sidebar sub-grouping if Governance group becomes unwieldy.** The Governance group will grow by six entries from this workstream. If the resulting group becomes hard to scan, a "Governance — workflow" sub-grouping for the new six is one option. Per the workstream plan section 5.4, this is a build-planning concern.

**[build-planning] Atomic-transaction implementation details.** The access-layer transactions described in section 3.4.3 (deposit_event creation plus references plus close_out_payload status transition, all in one transaction) are implementation choices. SQLite's transaction semantics, the access layer's session management pattern, and the V2 API envelope's behavior under partial failure are all build-planning concerns.

#### 3.8.2 For retroactive backfill to surface

**[backfill] Historical apply records reconstruction.** PI-022 (authored by SES-046) covers retroactive backfill of governance entity records. For deposit_event specifically, backfill means reconstructing the ~30 historical applies that ran via `apply_close_out.py` before this entity existed. The reconstruction strategy depends on what artifacts of those historical applies survive: the close-out payload JSON files (yes, preserved at `close-out-payloads/`); the apply stdout logs (no, not preserved — historical applies didn't write log files); the timestamps (yes, derivable from the `created_at` of the records the apply created — typically the session created at apply completion). The build-planning conversation refines the backfill plan, including the apply_context_runner value for backfilled records (working assumption: `"backfill_script"`) and whether log_file_path is required (likely null/placeholder for historical records where no log exists, with a future-version migration if needed).

**[backfill] Per-apply records_summary reconstruction.** For each historical apply, the records_summary can be reconstructed by reading the close_out_payload JSON file and counting its sections — for a payload with 1 session, 6 decisions, 1 planning_item, 7 references, the records_summary is `{"sessions": 1, "decisions": 6, "planning_items": 1, "references": 7}`. The reconstruction is mechanical; the backfill script's logic is straightforward.

**[backfill] Single-event-per-historical-payload approximation.** Historical applies were run with idempotency on re-run (HTTP 409 SKIPs); no operational record exists of which payloads were re-applied. For backfill purposes, the conservative approximation is one deposit_event record per historical close_out_payload, with `outcome = 'success'` and `created_at` set to the moment the close_out_payload's records appear in the database. Multi-event-per-payload re-applies are not retroactively reconstructed. This is a backfill-policy choice, not a schema constraint.

#### 3.8.3 For a future release

**[future] In-app log viewer affordance.** Not introduced in this release. If real friction emerges around opening log files from the consultant's filesystem, a "View log" button in the detail pane that opens the file in the platform's default text viewer (or in an in-app log viewer pane) is a natural addition. Non-breaking; no schema change.

**[future] Erroneous-record remediation path.** Not introduced in this release per section 3.4.5. If a real need surfaces (e.g., a development engagement accumulates spurious records that block legitimate audit queries), the natural addition is either (a) a hard-delete admin endpoint with audit logging, or (b) a soft-delete column with `_deleted_at` admitting per-record hiding while preserving the row. Either change is a schema migration plus access-layer rule update; both are admitted as additive future changes.

**[future] Apply-attempt provenance fields beyond `apply_context`.** Not introduced in this release. If real query needs emerge for "which engagement was this apply targeting" or "what release version of the apply script ran this", additional fields can be added to `apply_context` (additive JSON shape change, no migration) or as first-class columns (additive migration). The current `apply_context` shape suffices for the foreseeable governance queries.

**[future] Per-target-type back-reference kind expansion.** Not introduced in this release. The single generic `deposit_event_wrote_record` kind per Decision 3 covers all four current target types in one vocabulary entry. If future workstreams introduce additional governance entity types that close-out payloads can include records of (e.g., the six governance entity types from this workstream, once they ship), the `_kinds_for_pair` clause is extended to admit those target types. Schema-wise no change; one line added to `_kinds_for_pair`.

**[future] Re-apply policy enforcement.** Not introduced in this release. Multi-event-per-payload is admitted unconditionally under Decision 2. If real operational policy needs emerge (e.g., "limit re-applies to N per close_out_payload" or "require justification fields on re-apply"), policy enforcement can be added at the access layer without schema change. The current spec's posture is "facts are facts; record them all."

### 3.9 Cross-References

#### 3.9.1 Decisions cited by this spec

The following six decisions are authored by running `crmbuilder-v2/scripts/apply_close_out.py` against `PRDs/product/crmbuilder-v2/close-out-payloads/ses_054.json` at conversation close. Each is linked to SES-054 via a `decided_in` reference recorded in the same payload. Decision identifiers (anticipated DEC-155 through DEC-160) are assigned by the apply script at write time and may shift if other conversations close before this one applies.

- **DEC-155 — `deposit_event` identifier prefix and format.** Adopts `DEP` as the prefix and `DEP-NNN` zero-padded to three digits as the format. Three-letter form chosen on the strength of the existing three-letter precedent (DEC, REF, COP plus shorter and longer exceptions) and the natural pairing with `COP` for the family-3 deposit-bucket reading. Alternatives `DEPT`, `DEPOS`, `EVT`, `APPLY` rejected for disambiguation, length, or semantic mismatch. Per DEC-123's affirmation that each downstream conversation makes its own prefix-length call within the 2-to-5 letter range.

- **DEC-156 — `deposit_event` lifecycle shape: born-terminal append-only with diagnostic log capture (new cross-spec precedent).** Adopts a born-terminal append-only lifecycle (the record is POSTed at apply completion with outcome and all diagnostic fields populated; no intermediate `running` state; no PUT, no PATCH, no DELETE) plus diagnostic log capture via the `_log_file_path` field pointing at a stdout transcript written under `PRDs/product/crmbuilder-v2/deposit-event-logs/`. Establishes the new cross-spec precedent **born-terminal append-only with creation as the event-recording moment** — a new lifecycle category alongside workflow-shaped and documentary. Rejects the workflow-staged alternative (`running` → `success` / `failure` / `aborted`) on the grounds that the `running` intermediate state has no operational meaning for a 3-second apply and would introduce edit machinery incompatible with the fact-recording intent of the entity.

- **DEC-157 — `deposit_event` back-reference mechanism: references-table edges with one new generic-verb kind `deposit_event_wrote_record`.** Adopts references-table edges with a single cross-cutting kind `deposit_event_wrote_record` spanning four target types (session, decision, planning_item, reference) in one vocabulary entry and one `_kinds_for_pair` clause. Rejects per-target-type variants (four kinds, four pair clauses) on the strength of (a) cross-cutting nature, (b) established generic-verb naming precedent in the existing vocabulary, (c) minimum-viable schema growth. Rejects JSON-column-on-the-deposit-event-row and dedicated-back-reference-table alternatives on cross-spec precedent and discipline grounds (references-edge over alternative mechanisms per DEC-124). Rejects target-side `written_by_deposit_event_id` columns as inverting the references-edge precedent. Establishes cardinality (one DEP → many records; one record → zero-or-one DEP), 409-SKIP semantics (skipped records are not back-referenced), and scope (back-references span the substantive content layer, not back-references themselves).

- **DEC-158 — `deposit_event` re-apply semantics: multi-event-per-payload (new cross-spec precedent).** Adopts multi-event-per-payload — a close_out_payload may carry zero or more inbound `deposit_event_applies_close_out_payload` edges, one per apply attempt. Born-terminal append-only entities admit multi-event-per-target-record under this precedent. Relaxes the close_out_payload spec's at-most-one-inbound-edge default (which that spec section 3.8.3 explicitly deferred to this conversation). Specifies that the close_out_payload's `ready` → `applied` transition fires on the first inbound DEP with `outcome = 'success'`; subsequent DEPs (failures or re-confirmations) don't move the close_out_payload's status. Surfaces a cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation: the close_out_payload spec's at-most-one language needs revision to zero-or-more.

- **DEC-159 — `deposit_event` field inventory: identity + content + outcome + three diagnostic JSON + log_file_path + single timestamp; field-name `_outcome` over `_status`; declines `_notes`, `_updated_at`, `_deleted_at`, denormalized total count.** Captures the eight-column shape: `_identifier`, `_title`, `_description`, `_outcome`, `_records_summary`, `_error_info`, `_apply_context`, `_log_file_path`, `_created_at` (the timestamp counts as the ninth). Adopts `_outcome` over `_status` for semantic precision (born-terminal fact vs. workflow state). Declines `_notes` (consultant scratchpad incompatible with immutable record), `_updated_at` and `_deleted_at` (born-terminal append-only deviation from base-schema timestamps), denormalized total-records-written count (derivable from `_records_summary` or wrote_record edge count). JSON shape for `_records_summary`, `_error_info`, `_apply_context` documented in the spec but not SQL-enforced; Python helper module shares the shape between apply script and access layer.

- **DEC-160 — `deposit_event` API surface, UI, soft-delete posture, fifteen acceptance criteria.** Reduced API surface: POST + GET only (no PUT, no PATCH, no DELETE, no /restore — born-terminal append-only). Read-only UI audit log: no Create/Edit/Delete dialogs, Outcome filter combo in master-pane toolbar, master pane sorts identifier descending (audit-log deviation from V2's default ascending), right-click context menu reduced to "Copy identifier" / "Copy log path" lightweight read affordances, references section's "Add reference" affordance disabled. Plain-text `_log_file_path` display with no in-app viewer in this release. Strict no-Create-dialog posture: backfill via PI-022 implementation script, not via UI. Fifteen acceptance criteria captured covering schema migration, vocabulary additions, POST validation, conditional `_error_info` rule, parent-linkage and back-reference edge handling, atomic close_out_payload transition on success, multi-event-per-payload semantics, records-summary cross-check, method-not-allowed responses, GET envelope and filter, UI panel placement and behavior, apply script modification.

#### 3.9.2 External references

- `crmbuilder/CLAUDE.md` — universal session-startup entry.
- `PRDs/product/crmbuilder-v2/governance-schema-workstream-plan.md` — workstream master plan governing this and the prior five schema-design conversations.
- `PRDs/product/crmbuilder-v2/governance-entity-schema-spec-guide.md` — schema spec template this document follows.
- `PRDs/product/crmbuilder-v2/schema-design-kickoff-deposit-event.md` — this conversation's seed prompt.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/workstream.md` — first schema spec; locked the three foundational cross-spec precedents this spec inherits.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/conversation.md` — second schema spec; established the typed-sequencing-frequency-justified precedent this spec applies on its own facts.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/reference_book.md` — third schema spec; established the documentary-vs-workflow distinction this spec applies on its own facts (deposit_event is neither, establishing the third category).
- `PRDs/product/crmbuilder-v2/governance-schema-specs/work_ticket.md` — fourth schema spec; established the consumed-requires-edge precedent realized by SES-052 on the close_out_payload side as the applied-requires-edge rule that this spec is the counterpart to.
- `PRDs/product/crmbuilder-v2/governance-schema-specs/close_out_payload.md` — fifth schema spec; this spec's parent-linkage target. Cross-spec consistency finding surfaced for section 7.2 reconciliation: at-most-one inbound edge default relaxes to zero-or-more per Decision 2 of this conversation.
- `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md` — kickoff for the workstream's seventh and integrating conversation; consumes all six schema specs as input.
- `PRDs/product/crmbuilder-v2/multi-engagement-architecture.md` — per-engagement isolation; `deposit_event` records live in the per-engagement database.
- `crmbuilder-v2/src/crmbuilder_v2/access/vocab.py` — controlled vocabulary the new entity type and two relationship kinds register against.
- `crmbuilder-v2/scripts/apply_close_out.py` — the apply script that becomes the canonical writer of deposit_event records once the build-planning slice modifies it per section 3.8.1.
- `PRDs/product/crmbuilder-v2/close-out-payloads/` — historical home for close_out_payload files; the apply targets that deposit_event records reference.
- `PRDs/product/crmbuilder-v2/prompts/CLAUDE-CODE-PROMPT-apply-close-out-ses-025.md` — canonical envelope-discipline apply prompt; the apply path that consumes payload files today and produces deposit_event records once the build-planning slice modifies it.

#### 3.9.3 Foundation decisions this spec extends

- **DEC-117** — Track workflow files as three purpose-built entity-type families. `deposit_event` is the second entity in family 3 (deposit bucket), paired one-to-many with `close_out_payload`. **Most directly extended.**
- **DEC-118** — Two entities within the deposit bucket family. This spec realizes the deposit-event half of the pair. The family's two-entity split — payload produced at conversation close, event recorded at apply — is fully realized when this spec ships. **Most directly extended.**
- **DEC-119** — Add a conversation entity. Indirectly extended; deposit_event records cite back to close_out_payload records, which cite back to conversation records, which cite back to workstream records.
- **DEC-120** — Add a workstream entity. Indirectly extended via the conversation-to-workstream chain.
- **DEC-121** — Single-source-of-truth coverage extension. `deposit_event` is the sixth and final new entity type closing the coverage gap.
- **DEC-122** — The governance workstream opens immediately, in parallel to other in-flight work. This spec operates against the CRMBuilder dogfood engagement only.

#### 3.9.4 Related prior decisions informing this spec

- **DEC-013** — Decisions and sessions are append-only and immutable. Informs section 3.4.5's full-append-only posture for `deposit_event`: this entity is the strongest append-only entity in V2 (no soft-delete, unlike sessions and decisions which retain a `_deleted_at` for record management). Born-terminal append-only is the principle of DEC-013 applied to a fact-about-an-event entity.
- **DEC-025** — Per-conversation transcript capture infeasible. Informs section 3.6.4's reliance on the apply script and the deposit_event record itself as the durable artifacts of each apply attempt.
- **DEC-031** — Reference rendering generalized via shared `ReferencesSection` widget. Directly informs the detail-pane reference rendering in section 3.6.3, including the prominent parent-linkage edge display and the grouped wrote_record edge rendering with count badges.
- **DEC-035** — `ListDetailPanel` master-widget plus context-menu factory refactor. Informs master-pane patterns in section 3.6.2 including the Outcome filter combo and the reduced context-menu shape.
- **DEC-036** — Right-click context menus uniform across all entity rows. Informs context-menu behavior in section 3.6.2; the deviation (reduced to two read-only items rather than the standard four CRUD items) is documented as a deliberate consequence of the read-only audit-log entity nature.
- **DEC-046** — Parent-prefix field-naming convention. Inherited and applied throughout (all fields are prefixed `deposit_event_`).
- **DEC-048** — Source-first `{source}_{verb}_{target}` relationship-kind naming. Inherited; `deposit_event_applies_close_out_payload` follows the pattern explicitly; `deposit_event_wrote_record` follows the generic-verb sub-pattern used by `references`, `is_about`, `supersedes`, and `decided_in`.
- **DEC-115 / DEC-116** — Per-engagement isolation architecture. `deposit_event` records live in the per-engagement SQLite file; the CRMBuilder dogfood engagement is where this entity type's first records land.
- **DEC-123 through DEC-128** — All six decisions from SES-048 (the workstream schema-design conversation). DEC-123 affirms three-letter `DEP` is acceptable. DEC-124's references-edge cross-spec precedent applies to this spec's parent linkage and back-references. DEC-125's truly-terminal principle is inherited; this spec extends it with born-terminal append-only (records are not just terminal-on-arrival-at-terminal-state, they are terminal from the moment of creation). DEC-126's per-status timestamps precedent is applied on this spec's facts and yields no per-status timestamps (deposit_event has no workflow states). DEC-127 (flat catalog posture) is structurally analogous. DEC-128's standard-defaults posture is what this spec uses for collision check and identifier auto-assignment helper.
- **DEC-129 through DEC-134** — All six decisions from SES-049 (the conversation schema-design conversation). DEC-130's references-edge precedent for parent-child relationships applies. DEC-133's typed-sequencing-frequency-justified precedent is applied here to choose the single generic `deposit_event_wrote_record` kind over per-target-type variants.
- **DEC-135 through DEC-140** — All six decisions from SES-050 (the reference_book schema-design conversation). DEC-137's documentary-vs-workflow distinction is applied here on this spec's facts — deposit_event is neither documentary nor workflow-shaped, establishing the third lifecycle category (born-terminal append-only). DEC-139's repo-relative file path semantics are inherited verbatim for the `_log_file_path` column.
- **DEC-141 through DEC-146** — All six decisions from SES-051 (the work_ticket schema-design conversation). DEC-143's consumed-requires-edge precedent is realized on the close_out_payload side as DEC-149's applied-requires-edge rule; this spec is the counterpart that authors that inbound edge. DEC-144's single-use enforcement parallels this spec's single-parent-linkage rule. DEC-145's field-inventory pattern (identity / content / classification / file-pointer / timestamps) is followed and extended (adding three diagnostic JSON fields between file-pointer and timestamps).
- **DEC-147 through DEC-152** — All six decisions from SES-052 (the close_out_payload schema-design conversation). DEC-149's applied-requires-edge rule is the rule this spec is the counterpart to; the inbound `deposit_event_applies_close_out_payload` edge that triggers the close_out_payload's `applied` transition is the edge this spec authors. DEC-150's production-linkage-via-references-edge pattern parallels this spec's parent-linkage-via-references-edge. DEC-152's standard-API-with-Status-filter-combo UI posture is partially inherited (the Outcome filter combo follows the same pattern), partially deviated (the API is reduced to POST + GET, the UI omits Create/Edit/Delete dialogs entirely).

#### 3.9.5 Predecessor and successor conversations

- **Predecessor:** SES-052 — `close_out_payload` schema-design conversation. Established the applied-requires-edge rule that this spec is the counterpart to (the close_out_payload's `applied` transition requires the inbound `deposit_event_applies_close_out_payload` edge that this spec authors). Established the file_path semantics that this spec inherits for `_log_file_path`. Cross-spec consistency finding for the build-planning conversation's section 7.2 reconciliation: that spec's at-most-one inbound edge default needs revision to zero-or-more per Decision 2 of this conversation.

- **Successor:** Build-planning conversation. Kickoff at `PRDs/product/crmbuilder-v2/governance-schema-build-planning-kickoff.md` (drafted alongside this spec at conversation close). Consumes all six schema specs (workstream, conversation, reference_book, work_ticket, close_out_payload, deposit_event) as inputs and produces the integrating Product Requirements Document, implementation plan, per-slice build prompts, and refinement of PI-022's retroactive backfill scope. The build-planning conversation's section 7.2 cross-spec consistency check is the proper gate to reconcile this spec's surfaced finding (close_out_payload at-most-one relaxation). The build-planning conversation also sets the target user-interface version (open at this writing — to be coordinated with the active version sequence at that time).

This concludes the sixth and final schema-design conversation in the governance entity schema-design workstream. The next workstream activity is the build-planning conversation; after that, Claude Code execution of the build slice prompts; after that, a build-closeout session written through the standard apply-close-out path.

---

*End of document.*
