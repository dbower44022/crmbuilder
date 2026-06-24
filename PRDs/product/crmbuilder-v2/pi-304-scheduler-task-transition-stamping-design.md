# Scheduler Task-Transition Stamping — access-layer design (Phase 6a)

**Status:** design (requirement-first). No implementation in the originating
session; this document is the design deliverable for human review.

**Planning item:** PI-304 — *Phase 6a — append-only task_transition record +
scheduler stamping* (PRJ-041, ADO). Workstream **WSK-169** (Design),
Work Task **WTK-214** (area `access`).

**Governance:** Requirement **REQ-335** (observability derives from task
records); approving / mechanism decision **DEC-692** (*Observability derived from
task records via an append-only task-transition log*, CNV-183); related
**REQ-277** (single durable account), **REQ-263/264** (preserve / never-destroy
failed-run history).

**Scope split.** This document specifies the **access-layer write/read
behavior** — *when* a `task_transition` row is stamped, *how* it is made atomic
with the status update, and the read path that turns these rows into the single
source of truth for observability. The **record schema itself** (fields,
append-only/immutability constraints, ordering/identity, terminal agent-report
shape, relation to the PI-236 uniform task contract) is the sibling deliverable
**WTK-213** (area `storage`). Where the two meet — column names, the terminal
report payload — this document defers to WTK-213 and references it by intent, not
by restating the DDL.

---

## 1. Why this exists

DEC-692 makes the canonical task records the single source of truth for
observability: each task gains a dedicated **append-only `task_transition`
record** — one row per status change `(from_status, to_status, timestamp,
reason)`, and at the terminal transition the agent's report `(outcome, reasoning
summary, escalation)`. The task row continues to hold only its *current* status;
the transition log holds the *history*.

Today the access layer changes a Work Task's status through a single chokepoint
and emits only a generic `change_log` audit event. The generic log has no notion
of `reason`, agent report, or escalation (DEC-692 rejected deriving observability
from it for exactly this reason). This design adds the semantic lifecycle account
**at the same chokepoint**, so a transition row is stamped *every* time — and
*only* when — a status actually changes.

The companion `pipeline_events` table (PI-273) remains a best-effort console
mirror; it is **not** the source of truth and is not modified here. DEC-692
explicitly rejects a parallel telemetry log as primary because it can drift from
the task records. The transition log lives *on* the task records, so it cannot.

---

## 2. The trigger point — exactly one chokepoint

All Work Task status changes already funnel through one private function in
`access/repositories/work_tasks.py`:

```python
def _apply_status(row: WorkTask, status: str) -> None:
    _require_status(status)
    if status != row.work_task_status:
        gov.check_transition(
            row.work_task_status, status, WORK_TASK_STATUS_TRANSITIONS
        )
        row.work_task_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
```

Every public mutation path reaches a status change only here — there are
**three** such paths:

- `update_work_task` → `_apply_status(row, status)`
- `patch_work_task` → `_apply_status(row, fields["status"])`
- `claim_work_task` → `_apply_status(row, "Claimed")` (the `Ready → Claimed`
  advance)

`release_work_task` is deliberately **not** in this list: it clears
`claimed_by`/`claimed_at` only and leaves `work_task_status` untouched (releasing
a claim is not a lifecycle transition), so it stamps no row — correctly, because
no status changed.

**Decision: stamp inside `_apply_status`, guarded by the existing
`if status != row.work_task_status` branch.** That branch is already the precise
definition of "a real status change": it is entered iff the target status differs
from the current one, *after* `check_transition` has validated the move. Stamping
there gives, structurally:

- **exactly one row per real change** — the branch runs once per accepted change;
- **no row for a no-op** — re-PATCHing the same status (`status == current`) skips
  the branch entirely, so it stamps nothing (idempotent caller, no duplicate row);
- **no row for a rejected change** — an illegal transition raises in
  `check_transition` *before* the assignment, so no row is written.

`_apply_status` currently takes only `(row, status)`. It must also receive the
**reason** (and, for a terminal move, the agent report). The minimal signature
change:

```python
def _apply_status(
    row: WorkTask,
    status: str,
    *,
    reason: str | None = None,
    agent_report: dict | None = None,
) -> None:
    _require_status(status)
    if status != row.work_task_status:
        gov.check_transition(
            row.work_task_status, status, WORK_TASK_STATUS_TRANSITIONS
        )
        from_status = row.work_task_status
        row.work_task_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
        task_transitions.record(
            session,                 # threaded in; see §3
            work_task_identifier=row.work_task_identifier,
            from_status=from_status,
            to_status=status,
            reason=reason,
            agent_report=agent_report if status in _TERMINAL_STATUSES else None,
        )
```

`from_status` is captured **before** the assignment. The agent report is attached
**only** at a *run-ending* transition and ignored otherwise (DEC-692: "at the
terminal transition the agent's report").

> **Edge case — "terminal" means run-ending, not graph-sink.** The obvious
> definition, "a status with no outgoing transition in
> `WORK_TASK_STATUS_TRANSITIONS`," is **wrong** here: only `Complete` has an
> empty outgoing set, while `Blocked` (`→ Ready/Claimed/In Progress`) and
> `Failed` (`→ Ready`) are recoverable in the lifecycle yet are exactly the
> **halt points** REQ-263 anchors the failed-run rollup on. The agent reports at
> *every* run-ending outcome, including a recoverable halt. So
> `_TERMINAL_STATUSES = frozenset({"Complete", "Failed", "Blocked"})` — the
> agent-outcome / run-ending set, not the graph sinks. A later recovery
> (`Blocked → Ready`) is itself a fresh transition row with no report, and the
> halt's report survives on its own append-only row, satisfying REQ-263/264.
> This set is small and lifecycle-semantic (it tracks the agent-outcome
> statuses, which mirror `AGENT_OUTCOMES`), so it is stated explicitly rather
> than derived from the transition graph, which would silently mis-derive it.

> `_apply_status` is currently called as `_apply_status(row, status)` and does
> not receive the `session`. The session is in scope in every caller
> (`update_work_task`, `patch_work_task`, `claim_work_task`,
> `release_work_task`); threading it (and `reason` / `agent_report`) through is
> the only call-site change. The `reason`/`agent_report` inputs ride in on the
> existing request bodies — surfacing them through `update`/`patch` is the
> sibling **api**-area concern, out of scope for this access task; this design
> only requires that `_apply_status` accept and persist them.

### 2.1 Why not a DB trigger or an ORM event hook

A SQLite/Postgres trigger or a SQLAlchemy `before_update` event would also fire
"on status change," but is rejected: it cannot see the **reason** or the **agent
report** (they are not columns on `work_tasks`), it would fire under raw
back-fills and tests that legitimately set status directly, and it splits the
invariant across two layers. The repository chokepoint is the one place that has
the reason, the report, the validated transition, and the open session
together — keeping the stamp there keeps the guarantee auditable in one function.

---

## 3. Atomicity with the status update

The transition row and the status mutation **must commit together or not at
all** — a status change with no transition row (missed history) or a transition
row with no status change (phantom history) both violate DEC-692.

This is achieved by construction, with no new transaction machinery:

- `task_transitions.record(...)` runs against the **same `Session`** that
  `_apply_status` is mutating `row` in. Both the `UPDATE work_tasks` and the
  `INSERT task_transition` are pending in one unit of work.
- The access layer's `session_scope()` is **flush-then-commit** (one
  `BEGIN IMMEDIATE` on SQLite; one transaction on Postgres). The caller's
  `session.flush()` (already present after the field assignments in
  `update_work_task` / `patch_work_task` / the claim path) flushes both rows;
  the surrounding `session_scope` commits both in the same transaction.
- If `check_transition` raises, nothing is written. If the `INSERT` fails
  (e.g. the append-only / immutability guard from WTK-213 rejects a malformed
  row), the **whole unit rolls back**, including the status `UPDATE` — the task
  stays in its prior status, consistent with "no transition was recorded." There
  is never a status change the log did not capture.

The stamp is therefore **synchronous and transactional**, deliberately unlike the
best-effort `pipeline_events.emit` / `cost_capture` wrappers (which open their own
`session_scope` and swallow exceptions so observability never breaks the work).
The distinction is the whole point of DEC-692: the transition log **is** the
record, not a side observation of it, so it shares the work's transaction and its
failure is the work's failure.

### 3.1 Concurrency

Two agents racing to change the same task's status serialize on the row: SQLite's
`BEGIN IMMEDIATE` + 5 s `busy_timeout` and Postgres's row lock under the existing
`access/db.py` engine config already serialize the `work_tasks` `UPDATE`. The
loser re-reads the now-current status; if its target equals the current status
the `if status != ...` branch is skipped and **no second row is written** — the
single-row-per-change invariant holds under concurrency without new locking.

---

## 4. The read / access path — single source of truth

Reads come from the transition rows; nothing derives task history from
`change_log` or `pipeline_events`. Three access-layer reads, all new in
`access/repositories/task_transitions.py` (the module WTK-213's schema backs):

1. **`list_for_task(session, work_task_identifier) -> list[dict]`** — the
   complete, ordered transition history for one task (oldest → newest). This is
   the primitive the other two compose; it is the literal "complete transition
   history per task is reconstructable" verification criterion made queryable.

2. **`terminal_report(session, work_task_identifier) -> dict | None`** — the
   agent report attached at the task's terminal transition, or `None` if the task
   has not reached a terminal status. Convenience over `list_for_task`.

3. **`run_rollup(session, release_identifier) -> dict`** — the **run-level
   rollup** DEC-692 calls the single durable account (REQ-277): walk
   `release → projects → planning_items → workstreams → work_tasks`, and for each
   task fold in its transition history. For a **failed** run the rollup is
   *anchored on the halt point* — the task that transitioned to `needs_human` /
   `Failed` / `Blocked` — and its cause (the `reason` + terminal `agent_report`
   on that transition), per REQ-263. This mirrors the existing
   `pipeline_events.history(session, release_identifier)` read shape but sources
   from the canonical transition rows, not the best-effort event table.

The rollup is a **derived view**, computed at read time from the append-only
rows — never a stored, separately-mutated summary (DEC-692 rejected embedded
mutable JSON history for exactly this reason). The REST/UI surfacing of these
reads is the api/ui sibling concern; this document fixes only the access-layer
read contract that those surfaces consume.

### 4.1 Retain-not-delete is upheld, not implemented here

DEC-692's cleanup rule (a closed/failed run is *retired*, never hard-deleted, so
its tasks and transition logs survive — REQ-263/264) is satisfied *for the
transition log* by the append-only/immutability constraint owned by WTK-213: rows
are never mutated or deleted, so the history survives any run-level retire. This
design adds no delete path for transition rows and assumes none exists; the
run-retire mechanism itself is the `preserve-failed-run-history-design.md`
(PRJ-038) lineage, out of scope here.

---

## 5. Interaction with the existing generic `change_log`

Unchanged. `update_work_task` / `patch_work_task` / `claim_work_task` continue to
call `change_log.emit(... operation="update", before=..., after=...)` for generic
audit. DEC-692 keeps the generic change_log for generic audit and adds the
transition log as the **semantic lifecycle account** — they are complementary,
not redundant: change_log answers "what bytes changed on this row, by whom,"
the transition log answers "this task moved Ready→Claimed→In Progress→Complete,
here is why and the agent's closing report." No change_log behavior is removed.

---

## 6. Verification criteria

Directly testable against the chokepoint design (these become the access-layer
test contract for the build phase):

1. **Exactly one row per real status change.** A status change through any of the
   three status-changing paths (`update`, `patch`, `claim`) writes precisely one
   `task_transition` row with the correct `(from_status, to_status)`. A claim
   that advances `Ready → Claimed` writes one row for that advance.
   `release_work_task` (no status change) writes **zero** rows.
2. **No missed transition.** Every accepted `_apply_status` change has a matching
   row; for any task, replaying its rows in order reproduces its full status
   path with no gaps. (`list_for_task` returns a contiguous chain where each
   row's `from_status` equals the prior row's `to_status`.)
3. **No duplicate / phantom transition.** Re-applying the current status (PATCH
   to the same value) writes **zero** rows. A rejected (illegal) transition
   writes **zero** rows and leaves the task status unchanged.
4. **Atomicity.** If the transition `INSERT` is forced to fail, the status
   `UPDATE` is rolled back too — the task is observed in its prior status with no
   orphan row, and vice-versa (no status change without its row). Asserted by
   injecting a failure in `task_transitions.record` within one `session_scope`
   and confirming both the row and the status are absent afterward.
5. **Terminal report captured.** A transition into a terminal status persists the
   agent report (`outcome`, reasoning summary, escalation); a non-terminal
   transition persists `agent_report = NULL`. `terminal_report(...)` returns the
   report after the terminal move and `None` before it.
6. **Concurrency safety.** Two concurrent status changes to the same task produce
   exactly one row for the one change that wins; the no-op loser writes nothing.

---

## 7. Build-phase footprint (for the implementing PI, not built here)

- `access/repositories/work_tasks.py`: extend `_apply_status` signature
  (`reason`, `agent_report`, `session`); stamp inside the existing change branch;
  thread the new args through the three status-changing call sites
  (`update_work_task`, `patch_work_task`, `claim_work_task`); define
  `_TERMINAL_STATUSES = {"Complete", "Failed", "Blocked"}` (the run-ending set,
  per §2's edge case).
- `access/repositories/task_transitions.py` (**new**): `record(...)` (insert,
  append-only; the immutability guard is WTK-213's schema), `list_for_task`,
  `terminal_report`, `run_rollup`.
- Tests: the six §6 criteria, in `tests/access/` alongside the existing
  `work_tasks` tests.
- Out of scope (sibling areas): the `task_transition` table/DDL and immutability
  constraint (WTK-213, storage); surfacing `reason`/`agent_report` on the
  request bodies and the rollup endpoint (api); any UI.
