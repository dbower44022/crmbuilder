# Governance Entity Schema Spec — `task_transition` (append-only)

> **Status:** storage-area implementation + testable spec. Authored by WTK-213
> (Phase 6a — append-only task_transition record + scheduler stamping,
> workstream WSK-169) against the Agent System Redesign. The Develop task for
> the storage area builds to this spec; the Test task verifies against §3.7
> blind to the implementation.

## Revision Control

| Field | Value |
|---|---|
| Spec | `task_transition` storage schema |
| Version | 0.1 (design) |
| Governing decision | DEC-692 — *Observability derived from task records via an append-only task-transition log* |
| Realizes | REQ-335 (observability delta), REQ-277 (single durable account), REQ-263 (preserved failed-run history), REQ-264 (cleanup never destroys the record) |
| Extends | PI-236 — the uniform task contract (REQ-284) |
| Closest precedent | `deposit_event` (born-terminal append-only) — `governance-schema-specs/deposit-path-provenance-and-schema.md`, `access/models.py:DepositEvent` |

## Change Log

| Date | Change |
|---|---|
| 2026-06-24 | 0.1 — initial design: append-only `task_transition` child record, field set, immutability constraints, per-task ordering/identity, terminal agent report, verification criteria. |

## 1. Purpose and Position

DEC-692 decides that **observability derives from the task records, not a
separate telemetry store.** The uniform task contract (PI-236 / REQ-284) gives
every step a `status` from the fixed vocabulary
`not_started → in_progress → succeeded | needs_human | failed`, but the **task
row holds only its *current* status** — it does not retain *how* the task moved
through that vocabulary, *why* each move happened, or *what the Agent reported*
at the end.

This spec adds the missing piece: a dedicated **append-only child record, one
row per status change**, owned by a parent task. It is the **semantic lifecycle
account** of a task. Three downstream capabilities depend on it and could not
exist without it:

- **REQ-277 — one single durable account.** A run-level rollup view assembles
  *release → tasks → transition logs → halt point → gate verdicts* from these
  rows. This is the literal single-source-of-truth account that replaces
  scattered DB statuses, vanishing console output, and per-agent transcript
  files.
- **REQ-263 — preserved history of a failed run.** Because every transition is
  retained, a failed run's path to its halt point (the task that went
  `needs_human`/`failed`) and the Agent's terminal report on the cause survive
  intact for post-mortem.
- **REQ-264 — cleanup never destroys the record.** Cleanup is
  **retain-not-delete**: a closed/failed run is *retired* (marked), never
  hard-deleted, so its tasks and their transition logs survive. Append-only
  construction structurally guarantees this — there is no mutate or delete path
  to begin with.

**What this is not.** It is not a replacement for the generic `change_log`
(which remains for generic field-level audit) and it is not a parallel event
log that re-creates the scatter REQ-277 set out to remove. Per DEC-692, a
parallel telemetry log was rejected precisely because it is a second source of
truth that can drift; the transition record is a **child of the task it
describes**, so the task records remain the single source of truth.

## 2. Summary

A `task_transition` row is created on **every** status change of a parent task,
recording `from_status`, `to_status`, the `at` timestamp, and a human-readable
`reason`. When the transition moves the task **into a terminal status**
(`succeeded`, `needs_human`, or `failed`), the row additionally carries the
**Agent's terminal report**: `outcome`, a `reasoning_summary`, and an
`escalation` payload. Rows are **born terminal and immutable** — created
exclusively via POST, never updated, never deleted (mirroring `deposit_event`).
The complete, ordered lifecycle of any task is reconstructable by selecting all
its transition rows ordered by sequence.

## 3. Schema Specification

### 3.1 Identity

- **Table:** `task_transitions`.
- **Identifier:** `TXN-NNN` (prefix `TXN`), `String(32)` primary key, format
  `^TXN-\d{3,}$`, enforced by an `_IdentifierFormatCheck("task_transition_identifier", ["TXN"])`
  CHECK constraint — identical pattern to `deposit_event` / `commit`.
- **Auto-assignment:** identifier is server-assigned on POST when omitted
  (`identifier: null` or key absent), per the project-wide optional-identifier
  rule (PI-002); an explicit well-formed, non-colliding value is also accepted
  (collision → 409, malformed → 422).
- **Engagement scope:** `engagement_id` via `EngagementScopedPKMixin` (the same
  mixin `DepositEvent` uses), row-scoped and stamped from the `X-Engagement`
  header.

### 3.2 Fields

#### 3.2.1 Identity fields

| Field | Type | Null | Notes |
|---|---|---|---|
| `task_transition_identifier` | `String(32)` PK | no | `TXN-NNN`, format-checked. |
| `engagement_id` | scope | no | from `EngagementScopedPKMixin`. |

#### 3.2.2 Parent-task fields (the "which task" pointer)

The uniform task contract is realized today across more than one concrete entity
(`workstream` / `WSK-`, `work_task` / `WTK-`, and the PI-level gate steps). A
`task_transition` therefore identifies its parent **polymorphically** by
(type, identifier) rather than a single typed FK:

| Field | Type | Null | Notes |
|---|---|---|---|
| `task_transition_task_type` | `String(32)` | no | The parent task's entity type, e.g. `work_task`, `workstream`. CHECK-restricted to a `TASK_TRANSITION_TASK_TYPES` frozenset in `vocab.py`. |
| `task_transition_task_identifier` | `String(32)` | no | The parent task's identifier, e.g. `WTK-213`. Not a hard FK — the append-only log must outlive a retired/retained parent (mirrors the `role_assignments` "not a FK so the audit log outlives a deleted principal" pattern, `models.py:5152`). |

#### 3.2.3 Transition fields (every row)

| Field | Type | Null | Notes |
|---|---|---|---|
| `task_transition_from_status` | `String(16)` | yes | Source status. **NULL only for the inaugural transition** (creation into `not_started`/`in_progress`, which has no prior status). CHECK: NULL or ∈ task-contract status vocabulary. |
| `task_transition_to_status` | `String(16)` | no | Destination status. CHECK: ∈ task-contract status vocabulary (`not_started, in_progress, succeeded, needs_human, failed`). |
| `task_transition_reason` | `Text` | no | Human-readable reason the transition happened (why the scheduler/Agent moved the task). Non-empty. |
| `task_transition_sequence` | `Integer` | no | Per-task monotonically increasing ordinal (1, 2, 3, …) — see §3.4. |
| `task_transition_at` | `DateTime(timezone=True)` | no | When the transition occurred. `default=_utcnow`. Indexed. |

#### 3.2.4 Terminal-report fields (terminal transitions only)

Populated **iff** `to_status` is terminal (`succeeded | needs_human | failed`).
This is the Agent's report DEC-692 / REQ-278 require at the terminal transition.

| Field | Type | Null | Notes |
|---|---|---|---|
| `task_transition_outcome` | `String(16)` | yes | The terminal outcome the Agent declares. CHECK-restricted to a `TASK_TRANSITION_OUTCOMES` frozenset. NULL on non-terminal rows; **required** when `to_status` is terminal. |
| `task_transition_reasoning_summary` | `Text` | yes | The Agent's prose summary of what it did and concluded. **Required** when `to_status` is terminal; NULL otherwise. |
| `task_transition_escalation` | `JSONColumn` | yes | Structured escalation payload (what a human must decide/review, references to the blocking decision/finding). **Required when `to_status = needs_human`**; optional on `failed`; NULL on `succeeded` and on non-terminal rows. |

> The terminal-report fields live on the same row as the terminal transition (not
> a separate entity) because the report *is* a property of the terminal status
> change — this keeps the lifecycle account a single ordered stream and makes the
> "terminal report present at the terminal transition" verification a single-row
> check.

#### 3.2.5 Timestamp fields

| Field | Type | Null | Notes |
|---|---|---|---|
| `task_transition_created_at` | `DateTime(timezone=True)` | no | Row insertion time. `default=_utcnow`. **No `_updated_at`, no `_deleted_at`** — append-only, exactly as `deposit_event`. |

`task_transition_at` (the semantic time of the transition) and
`task_transition_created_at` (the row-insertion time) are separate by design so
a transition recorded slightly after the fact still orders correctly; in the
common real-time path they coincide.

### 3.3 Relationships

#### 3.3.1 Outbound

- **`task_transition_records_task`** — new reference vocabulary kind, edge
  `(task_transition → work_task | workstream)`. Mirrors the
  `deposit_event → close_out_payload` `wrote_record` precedent. The
  (type, identifier) columns in §3.2.2 are the denormalized fast path; this edge
  is the queryable graph form. *(Vocab membership and the
  `(source_type, target_type)` constraint pair are an access-area concern — this
  storage spec only declares the requirement; the access-layer Work Task adds the
  kind to `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`.)*

#### 3.3.2 Inbound

None. Nothing points *at* a transition row; it is a leaf record.

#### 3.3.3 Hierarchy

A `task_transition` is a **child of exactly one task**. A task has 1..N
transitions (at least the inaugural one once it leaves `not_started`).

### 3.4 Lifecycle, ordering, and identity per task

- **Born-terminal, status-free row.** A transition row has **no status of its
  own** and never transitions — like `deposit_event`, it carries content
  (`outcome`) instead of a `_status`. Its "lifecycle" is: inserted, then
  immutable forever.
- **Per-task ordering via `task_transition_sequence`.** Each task's transitions
  are numbered `1, 2, 3, …` in occurrence order. The repository assigns the next
  sequence as `MAX(sequence) + 1` for the parent task under the same
  SAVEPOINT-retry safety used for identifier assignment, so concurrent appends to
  the *same* task cannot collide. A **UNIQUE constraint on
  `(engagement_id, task_transition_task_type, task_transition_task_identifier,
  task_transition_sequence)`** enforces no duplicate ordinal per task.
- **Reconstructing the history.** `SELECT * FROM task_transitions WHERE
  task_type = ? AND task_identifier = ? ORDER BY task_transition_sequence` yields
  the complete, gap-free lifecycle of any task. `task_transition_at` is the
  secondary/tie-break sort and the human-facing timeline.
- **Chain consistency (advisory, repository-enforced).** For sequence *n>1*, the
  row's `from_status` should equal the prior row's `to_status`. The inaugural row
  (sequence 1) has `from_status = NULL`. This is validated at write time by the
  repository, not by a DB CHECK (a CHECK cannot see the prior row).

### 3.5 Append-only / immutability constraints (the heart of this spec)

1. **Create-only API.** The only write verb is `POST /task-transitions`. There is
   **no PUT/PATCH and no DELETE** endpoint, and the repository exposes no update
   or delete method. (Same posture as `deposit_event`, whose router is "POST + GET
   only, born-terminal append-only.")
2. **No mutability columns.** The table has **no `_updated_at` and no
   `_deleted_at`** column, so there is structurally no soft-delete or
   touch-on-update path.
3. **Retain-not-delete cleanup (REQ-264).** Run cleanup retires the *parent* task
   /run (a marker on the parent), and **never** touches transition rows. Because
   the parent pointer is not a hard FK (§3.2.2), retiring or even removing a
   parent does not cascade to or orphan-delete the log.
4. **Transaction control.** POST is atomic — row insert + sequence assignment +
   the `task_transition_records_task` edge in one transaction, under the project's
   `BEGIN IMMEDIATE` / SAVEPOINT-retry discipline (the same fix that closed the
   orphan-row bug for the other governance creates).

### 3.6 Validation (repository / API layer)

The storage schema declares the columns and DB CHECKs below; the conditional
field rules are enforced at the repository layer (a CHECK cannot express
"required when to_status terminal" portably across SQLite + Postgres):

DB CHECK constraints:
- `ck_task_transition_identifier_format` — `_IdentifierFormatCheck(..., ["TXN"])`.
- `ck_task_transition_to_status` — `_check_in(to_status, TASK_CONTRACT_STATUSES)`.
- `ck_task_transition_from_status` — NULL or `_check_in(..., TASK_CONTRACT_STATUSES)`.
- `ck_task_transition_task_type` — `_check_in(task_type, TASK_TRANSITION_TASK_TYPES)`.
- `ck_task_transition_outcome` — NULL or `_check_in(outcome, TASK_TRANSITION_OUTCOMES)`.
- UNIQUE `(engagement_id, task_type, task_identifier, sequence)`.

Repository-layer rules (reject → 422):
- `reason` non-empty.
- terminal `to_status` ⇒ `outcome` and `reasoning_summary` present.
- `to_status = needs_human` ⇒ `escalation` present.
- non-terminal `to_status` ⇒ `outcome`, `reasoning_summary`, `escalation` all NULL.
- `from_status` NULL **iff** this is the inaugural (sequence 1) row for the task;
  otherwise it must equal the prior row's `to_status`.

### 3.7 Acceptance criteria (the Test task verifies these, blind to code)

1. **Append-only — never mutated.** No code path (API or repository) can update a
   `task_transition` row after insert. A `PATCH`/`PUT` to a transition resource
   404s (no route); the repository exposes no update method. *(Test: assert the
   router has no update handler and the repo module exports no `update_*`.)*
2. **Append-only — never deleted.** No `DELETE` route and no repository delete
   method exist; the table has no `_deleted_at`. Retiring a parent task leaves its
   transition rows present and unchanged. *(Test: retire a parent, re-query the
   log, assert row count and contents are identical.)*
3. **Complete history reconstructable per task.** After driving a task through
   `not_started → in_progress → <terminal>`, selecting its transitions ordered by
   `sequence` returns every step in order with gap-free 1..N sequence and
   chained `from/to` statuses. *(Test: drive a multi-step lifecycle, assert the
   ordered list matches the driven path exactly.)*
4. **Terminal report present at terminal transition.** Every row whose `to_status`
   is terminal has non-NULL `outcome` and `reasoning_summary` (and non-NULL
   `escalation` when `to_status = needs_human`); no non-terminal row carries any
   terminal-report field. A POST that violates either is rejected 422. *(Test:
   POST a terminal transition without a report → 422; POST a non-terminal
   transition with a report → 422; POST a valid terminal transition → 201 with the
   report persisted.)*
5. **Ordering identity per task.** Two concurrent appends to the same task yield
   distinct, consecutive sequence numbers and never violate the UNIQUE
   constraint. *(Test: the SAVEPOINT-retry sequence assignment, as exercised for
   identifier assignment elsewhere.)*

### 3.8 What this spec does NOT do

- It does not define the **run-level rollup view** (REQ-277's assembled account
  *over* these rows) — that is a separate (access/api) Work Task that *reads*
  this log. This spec provides the substrate the rollup queries.
- It does not change any task-contract status value or transition rule (PI-236
  owns those); it records the transitions that vocabulary produces.
- It does not author the **scheduler stamping** that emits a transition on each
  status change — that is the other half of Phase 6a (a scheduler/access Work
  Task). This spec defines the record the stamping writes.
- It does not add the **reference vocabulary kind** to `vocab.py` or the
  desktop monitoring panel — declared as cross-area dependencies in §3.3.1 / §4.

## 4. Cross-area dependencies (declared, not built here)

| Dependency | Owning area | Why |
|---|---|---|
| `task_transition_records_task` added to `REFERENCE_RELATIONSHIPS` + `_kinds_for_pair`; `refs.relationship_kind` CHECK migration | access | The graph-form parent edge (§3.3.1). |
| `TASK_CONTRACT_STATUSES`, `TASK_TRANSITION_TASK_TYPES`, `TASK_TRANSITION_OUTCOMES` frozensets in `vocab.py` | access | The CHECK vocabularies referenced in §3.6. |
| `change_log` entity-type CHECK rebuilt to admit `task_transition` (the documented gotcha for any new entity type) | storage/migration | A new ENTITY_TYPE must rebuild `change_log`'s CHECK, not just `refs`. |
| Alembic SQLite + PG migrations creating `task_transitions` | storage/migration | A *separate* Work Task — WTK-213 specifies; it does not author migrations it was not asked for. |
| Run-level rollup view; scheduler stamping; Qt monitoring | access / api / ui | §3.8. |

## 5. Cross-references

- **DEC-692** — governing decision (append-only task-transition log; retain-not-delete).
- **PI-236 / REQ-284** — the uniform task contract this record extends.
- **REQ-335 / REQ-277 / REQ-263 / REQ-264** — the requirements realized.
- **`access/models.py:DepositEvent`** + `governance-schema-specs/deposit-path-provenance-and-schema.md` — born-terminal append-only precedent mirrored here.
- **`access/models.py:ReviewSignoff`** — append-only attestation precedent.
- **`PRDs/product/NEW-Master PRDs/Agent PRDs/Agent-System-Target-Model.md` §1.2/§1.4, glossary** — the task / status / contract definitions.
