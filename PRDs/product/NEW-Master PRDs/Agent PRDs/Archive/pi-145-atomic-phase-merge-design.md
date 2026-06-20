# PI-145 — Atomic (all-or-nothing) phase merge for the parallel ADO runtime

Status: **Design spec** (WTK-083, methodology-process area). Delivers the spec
only — implementing the change (Develop) and writing the test code (Test) are
separate Work Tasks in the same Workstream and are **out of scope here**.

Scope of this PI: `runtime/parallel_runtime.py` (the driver's core merge path)
and a small new helper on `runtime/coordinating_runtime.py`. No schema change,
no migration, no new entity, no API-surface change.

## 1. The problem

On the parallel path (`--max-concurrent >= 2`), a phase's Work Tasks are run as
a capped pool by `ParallelCoordinatingRuntime.run()`
(`parallel_runtime.py:548`). Every worker creates its worktree by forking from
`cfg.base_branch` (`main`) at the moment `Worktree.create()` runs
(`coordinating_runtime.py:239`), and the pool starts **all** eligible siblings
up front (cap permitting) before any of them has merged. So two parallel
siblings branch from the **same** base commit.

As each agent finishes, `_integrate` (`parallel_runtime.py:462`) verifies by
result and, under `self._repo_lock`, calls `self._l1._merge(branch)`
(`coordinating_runtime.py:607`) which does `git checkout main` + `git merge
--no-ff <branch>` **in completion order**. The merges are serialized by the
lock, but they land **eagerly and independently**:

- A later sibling's merge can hit a **CONFLICT** (`MergeStatus.CONFLICT`) — but
  earlier siblings that merged cleanly are **already on `main`**. `main` is now
  partial: it carries some of the phase's work but not all.
- A sibling can fail verification (**`VerifyOutcome` ≠ `OK`** →
  `TaskOutcome.VERIFY_FAILED`) — same outcome: earlier clean siblings are
  already on `main` while this one never lands.

In both cases the run pauses new dispatch and flags the owning Workstream
`needs_attention` (good), but **`main` is left red/partial** — a phase that was
supposed to be a coherent unit has landed half its work. The reconciliation
gate and the human now inherit a `main` that does not build as a whole, and the
half-merged commits are awkward to unwind by hand.

This is the parallel-specific hazard. On `--max-concurrent 1` it does not
arise, because each task is dispatched only after the prior one has merged, so
each worktree forks from **main-with-prior-merges** and conflicts are far
rarer; see §6.

## 2. The chosen approach (PI-145 bounded design)

Make a **phase's merges all-or-nothing** by capturing `main`'s HEAD before the
pool runs and **rolling the whole phase back to it if any task in the phase
fails**:

1. **Capture** `pre_phase_head = <main HEAD>` once, before the phase pool
   dispatches its first worker.
2. **Merge eagerly, as today** — tasks still verify and merge in completion
   order under `self._repo_lock`. No staging branch, no held-back merges. This
   keeps the diff small and reuses `_merge` unchanged.
3. **On the first failure** (a merge `CONFLICT` *or* a `VERIFY_FAILED` task) the
   run already pauses new dispatch and drains in-flight agents. We add: at the
   **end of the run, if any task failed**, `git reset --hard pre_phase_head` on
   `base_branch` to undo **every** sibling merge this phase produced, flag the
   owning Workstream `needs_attention` (the existing `_flag_needs_attention`
   path — already called per-failure), and **do not advance the phase**.
4. **Only when ALL tasks succeed** are the merges left on `main`.

Why eager-merge-then-rollback rather than stage-then-commit: `git reset --hard`
to a captured ref is a single, well-understood, atomic undo of the merge
commits, and it requires **no change** to `_merge`, to `Worktree`, or to the
completion-order merge loop. The alternative (a per-phase staging branch that is
fast-forwarded onto `main` only when the phase is whole) is a larger change to
the merge path for the same external behavior. The serialize-same-area-tasks
alternative is noted in §7 but **not adopted**.

## 3. Hook points and lock scope

Everything below happens under `self._repo_lock` — this is the driver's core
merge path and `pre_phase_head` capture, every `_merge`, and the rollback must
not interleave with any worker's `Worktree.create()` / `has_commits_beyond()`
git ops (which already take the same lock).

### 3.1 Capture `pre_phase_head`

`run()` (`parallel_runtime.py:557`) captures the base HEAD **before**
`self._fill_slots(executor, active)` first runs. At that point no worker has
created a worktree and no merge has happened, so `main` is still at the
phase's true starting commit. Capture under the lock:

```text
with self._repo_lock:
    pre_phase_head = self._l1._base_head()   # new helper, §4
```

`pre_phase_head` is a local in `run()` (a single phase == a single `run()`
invocation; see §5). It is also worth surfacing on `PoolRunReport`
(`pre_phase_head: str | None`) so the report records exactly what a rollback
would/did target — useful for the orchestrator log and for the Test task's
assertions.

### 3.2 Track whether any task failed

`run()` already appends a `TaskReport` per completed task and already sets
`report.paused = True` on the first non-`MERGED` outcome
(`parallel_runtime.py:589`). The rollback predicate is exactly *"any
`TaskReport.outcome is not TaskOutcome.MERGED`"*, which is equivalent to
`report.paused` under the current loop (paused is set iff a non-merged outcome
occurred). The Develop task may reuse `report.paused` directly or compute
`any(r.outcome is not TaskOutcome.MERGED for r in report.task_reports)`; the two
are equivalent and the latter is more self-documenting.

No change is needed to the per-failure flagging: `_integrate` already calls
`self._l1._flag_needs_attention(...)` on both the `VERIFY_FAILED` branch
(`parallel_runtime.py:470`) and the `MERGE_CONFLICT` branch
(`parallel_runtime.py:495`), and `_record_finding` alongside it. The rollback
does **not** introduce a second flag; the existing one already raised
`workstream_needs_attention`, which is what stops the orchestrator from
advancing the phase (§5).

### 3.3 Roll back at phase end

In `run()`'s `finally` block, **after** `executor.shutdown(wait=True)` (so all
workers are quiesced and no further `_merge` can run) and after the API is
stopped, perform the rollback if the phase failed:

```text
finally:
    executor.shutdown(wait=True)
    if cfg.manage_api and self.api is not None:
        self.api.stop()
    phase_failed = any(
        r.outcome is not TaskOutcome.MERGED for r in report.task_reports
    )
    if phase_failed and report.task_reports:   # nothing to undo on an empty drain
        with self._repo_lock:
            self._l1._reset_base_to(pre_phase_head)   # new helper, §4
        report.rolled_back = True
        report.rolled_back_to = pre_phase_head
        self.log(
            f"↩ phase rolled back: {cfg.base_branch} reset --hard {pre_phase_head[:8]} "
            f"— undoing every sibling merge from this phase (a task failed; "
            f"workstream flagged needs_attention)"
        )
```

Placing the rollback in `finally`, after `shutdown(wait=True)`, guarantees:

- No worker thread is mid-`_merge` (the executor is fully drained), so the
  `git reset --hard` cannot race a merge.
- The rollback runs even if the loop returned early on the pause path — the
  loop body returns the report through the same `finally`.

`report.rolled_back` / `report.rolled_back_to` are new `PoolRunReport` fields so
the orchestrator and tests can observe the rollback distinctly from a plain
pause. They default to `False` / `None`.

### 3.4 Lock scope, stated precisely

| Step | Under `self._repo_lock`? | Why |
|---|---|---|
| capture `pre_phase_head` | **yes** | reads `main` HEAD; must not race a worker's worktree create/merge |
| each `_merge` (unchanged) | **yes** (already) | `_integrate` already wraps `_merge` in the lock (`parallel_runtime.py:489`) |
| each `Worktree.create` / `has_commits_beyond` | **yes** (already) | already locked in `_worker` (`parallel_runtime.py:421`, `:447`) |
| rollback `_reset_base_to` | **yes** | mutates `main` HEAD; held for the whole checkout+reset |

The rollback acquires the lock when no workers remain (post-shutdown), so it
never actually contends — the lock is taken for correctness/consistency, not to
resolve a live race.

## 4. New `coordinating_runtime` helpers

Two small methods on `CoordinatingRuntime`, placed beside `_merge`
(`coordinating_runtime.py:607`) and using the existing module-level `_git`
helper. They are methods on `_l1` so the parallel runtime composes them exactly
as it composes `_merge` / `_flag_needs_attention` today (no new free functions,
matching the established reuse pattern).

```text
def _base_head(self) -> str:
    """Return base_branch's current HEAD SHA (the phase's pre-merge anchor)."""
    cfg = self.config
    return _git(cfg.repo_root, "rev-parse", cfg.base_branch).stdout.strip()

def _reset_base_to(self, head: str) -> None:
    """Hard-reset base_branch back to `head`, undoing this phase's merges.

    Checks out base_branch first (mirrors `_merge`, which checks it out before
    merging), then `git reset --hard <head>`. Used by the parallel runtime to
    make a phase's merges all-or-nothing: if any sibling failed, every clean
    sibling merge from the same phase is undone in one step.
    """
    cfg = self.config
    _git(cfg.repo_root, "checkout", cfg.base_branch)
    _git(cfg.repo_root, "reset", "--hard", head)
```

Design notes the Develop task must honor:

- **`rev-parse cfg.base_branch`**, not `rev-parse HEAD` — `_merge` does
  `git checkout cfg.base_branch` and leaves the repo on `base_branch`, but at
  capture time (before any merge) the repo's checked-out branch is whatever the
  worktree-parent repo was on; resolving by branch name is unambiguous and
  matches `_merge`'s own reference to `cfg.base_branch`.
- **`check=True` (the `_git` default)** for both calls is acceptable: a failure
  to read or reset `main` is a hard environment error the operator must see, not
  something to swallow. (Contrast `_merge`, which uses `check=False` only
  because a non-zero merge is an *expected* conflict outcome it interprets.)
- **The per-task feature branches are intentionally left intact.** Rollback
  only moves `main`'s ref; the agents' branches (and their commits) still exist
  and are reachable, so a human investigating the `needs_attention` flag can
  inspect exactly what each sibling produced. The next pool run's
  `Worktree.create()` deletes a stale same-named branch (`git branch -D`,
  `coordinating_runtime.py:242`) before re-creating, so no cleanup is owed here.

## 5. Failure / rollback state machine

A single `run()` call drives one phase (the orchestrator scopes the pool to one
Workstream via `target_workstream`/`target_work_tasks`, then calls the pool once
per phase — `ado_runtime.py:500`). States are per-phase:

```
                 ┌─────────────────────────────────────────────┐
                 │  capture pre_phase_head (main HEAD, locked)  │
                 └───────────────────────┬─────────────────────┘
                                         │
                            ┌────────────▼─────────────┐
                            │  RUNNING: fill slots,     │
                            │  workers spawn in parallel│
                            └────────────┬─────────────┘
                                         │ each completion → _integrate (locked)
                          ┌──────────────┼───────────────┐
                          │              │               │
                  verify != OK     merge CONFLICT    verify OK + merge CLEAN
                          │              │               │
                          ▼              ▼               ▼
                  flag needs_attn  flag needs_attn   TaskReport=MERGED
                  TaskReport=       TaskReport=       (merge stays — for now)
                  VERIFY_FAILED     MERGE_CONFLICT
                          │              │               │
                          └──────┬───────┘               │
                                 │ paused=True            │ keep filling slots
                                 │ stop new dispatch,     │ until drained
                                 │ DRAIN in-flight        │
                                 └───────────┬────────────┘
                                             │
                       ┌─────────────────────▼──────────────────────┐
                       │  finally: executor.shutdown(wait=True)      │
                       └─────────────────────┬──────────────────────┘
                                             │
                          any TaskReport.outcome != MERGED ?
                              │                         │
                            yes                        no
                              │                         │
                              ▼                         ▼
          ┌───────────────────────────────┐   ┌──────────────────────────┐
          │ ROLLBACK (locked):            │   │ COMMIT phase:            │
          │  reset --hard pre_phase_head  │   │  all sibling merges stay │
          │  → main back to pre-phase     │   │  on main                 │
          │  report.rolled_back = True    │   │  report.paused = False   │
          │  report.paused = True         │   │  report.rolled_back=False│
          │  (workstream already flagged) │   └────────────┬─────────────┘
          └───────────────┬───────────────┘                │
                          │                                 │
                          ▼                                 ▼
          orchestrator sees paused → does            orchestrator calls
          NOT call complete-phase; PI Lead's         /workstreams/{ws}/complete-phase
          needs_attention flag → AdoStep.PAUSE       → phase advances
          (ado_runtime.py:501, decide_next §86)
```

Key invariants the state machine guarantees:

- **Atomicity:** at `run()` return, `main` is either at `pre_phase_head` (no
  phase work) or carries **all** of the phase's merges. It is never partial.
- **"Do not advance the phase" is already enforced by the existing pause/flag
  wiring**, not by new code: `report.paused` short-circuits the orchestrator
  before `/complete-phase` (`ado_runtime.py:501`), and the
  `workstream_needs_attention` flag drives `decide_next` to `StepKind.PAUSE`
  (`ado_runtime.py:93–95`) on any subsequent DB-backed-stateless re-read. The
  rollback adds the `main`-restoration that those signals previously lacked.
- **A clean-then-failed ordering and a failed-then-clean ordering both roll
  back fully.** Because rollback is decided at phase end over all `task_reports`
  (not at the moment of the first failure), a clean sibling that merged *after*
  the failing one is still undone by the single `reset --hard`.

### 5.1 Edge cases the Develop/Test tasks must handle

- **Empty drain (no work):** `report.task_reports == []` → `phase_failed` is
  `False` and the `and report.task_reports` guard skips the reset; nothing is
  undone, `pre_phase_head` is never used. (Matches
  `test_drains_cleanly_when_no_work`.)
- **All clean:** no failure → no reset; `report.rolled_back` stays `False`,
  merges remain. (The all-clean acceptance criterion, §6b.)
- **Work Task DB status after rollback:** the agents marked their Work Tasks
  `Complete` before the rollback, and the rollback only moves git refs — it does
  **not** revert Work Task status in the DB. This is an accepted, deliberate
  gap: the `workstream_needs_attention` flag is the reconciliation signal, and a
  human (or the PI Lead's `complete_phase`, which independently re-checks the
  Work Tasks) owns reconciling DB status with the rolled-back code. Reverting
  task status on rollback is **out of scope** for PI-145; the Develop task must
  not silently flip statuses. Flagging this explicitly here so it is a known,
  intended state rather than a surprise.
- **Rollback git failure:** `_reset_base_to` runs with `check=True`; if the
  `reset` itself fails (e.g. a dirty working tree from a half-aborted merge),
  the exception propagates out of `run()`. The Develop task should ensure
  `_merge` always leaves a clean tree on its conflict path — it already does
  (`git merge --abort`, `coordinating_runtime.py:621`) — so `reset --hard` finds
  a clean tree. No new abort logic is required, but the Test task should cover
  the conflict-then-reset sequence end to end.

## 6. `--max-concurrent 1` happy path is structurally unaffected

On the serial path each Work Task is dispatched only after the prior one merged,
so its worktree forks from **main-with-prior-merges** (the `select_to_dispatch`
blocker-awareness plus the one-at-a-time cap guarantee no two run concurrently).
The happy path (every task clean) is therefore **byte-identical** under this
change:

- `pre_phase_head` is still captured, but with all-clean outcomes
  `phase_failed` is `False`, so `_reset_base_to` is **never called** — the
  merges stay exactly as today.
- No change to `_merge`, `Worktree`, dispatch order, or completion-order
  merging. The capture is a single `rev-parse`; the rollback branch is dead code
  on a clean run.

The **only** behavioral delta at `--max-concurrent 1` is on a *failing* phase:
previously a mid-phase failure left earlier clean siblings on `main`; now they
are rolled back too. This is the **intended** atomicity semantic — it is
phase-level all-or-nothing and is deliberately concurrency-independent (the
rollback predicate and mechanism are identical at any cap). The Develop task
must keep this delta confined to the failure path; the all-clean serial run must
not regress. The existing serial-path Layer-1 loop in
`coordinating_runtime.py` (`CoordinatingRuntime.run`, the `--max-iterations`
serial driver) is **untouched** by this PI — PI-145 changes only
`parallel_runtime.py`'s pool; the serial Layer-1 loop has no phase-pool concept
and is out of scope.

## 7. Noted-but-not-adopted alternative: serialize same-area Work Tasks

An alternative that would also avoid same-base conflicts is to **never run two
Work Tasks of the same area in parallel** — i.e. extend `select_to_dispatch` so
that two candidates sharing a `work_task_area` are mutually exclusive in a tick,
forcing the second to fork from the first's merged result (as the `blocked_by`
case already does, `parallel_runtime.py:105`). This narrows the conflict window
(most conflicts are within an area touching the same files) without any
rollback.

It is **not adopted** because:

- It is a **conflict-avoidance heuristic, not a guarantee** — cross-area tasks
  can still conflict (shared `__init__`, vocab, config), and a `VERIFY_FAILED`
  task still leaves clean siblings on `main`. It does not deliver atomicity.
- It **reduces parallelism** exactly where areas are busiest, working against
  the throughput the pool exists to provide.
- It complicates the pure `select_to_dispatch` decision (now needs each
  candidate's area), whereas the chosen design keeps the pure decisions
  untouched and adds one bounded I/O step.

The bounded reset-to-`pre_phase_head` design gives a hard atomicity guarantee at
the cost of one `rev-parse` per phase and one `reset --hard` on the (rarer)
failure path, and is the recommendation.

## 8. Verification plan — acceptance criteria for Develop/Test

These are the criteria the Test Work Task must encode (mechanism pinned with the
existing injected seams in `tests/crmbuilder_v2/runtime/test_parallel_runtime.py`
— fake spawn, `_FakeWorktree`, stubbed `dispatcher._get`, injected `_merge` via
`merge_for`, and `_flag_needs_attention` capture into `rt._flagged`). Because
`_FakeWorktree` and the stubbed `_merge` do no real git, the rollback assertions
need the new helpers (`_base_head` / `_reset_base_to`) **also stubbed/recorded**
on `rt._l1` (record the reset target instead of running git), plus at least one
**real-git integration test** in a `tmp_path` repo that exercises an actual
`merge` + `reset --hard` so the git semantics are proven, not just the
control-flow.

**(a) Two parallel tasks, the second conflicts → full rollback.**
Two tasks dispatched (cap 2, both overlap), `merge_for` set so the second yields
`MergeStatus.CONFLICT`. Assert: `report.paused is True`;
`report.rolled_back is True` and `report.rolled_back_to == pre_phase_head`;
`main` is back at `pre_phase_head` (the real-git variant: `git rev-parse main`
equals the captured SHA, **neither** merge commit is present); the owning
Workstream was flagged `needs_attention` (`"WTK-…" in rt._flagged`); and the
phase is **not advanced** (no `/complete-phase` call — assert the orchestrator
short-circuits on `report.paused`, mirroring `ado_runtime.py:501`).

**(b) All clean → both merges present, no rollback.**
Two clean tasks. Assert: `report.paused is False`; `report.rolled_back is False`;
`_reset_base_to` was **never** called (record-and-assert-not-called); both
TaskReports are `TaskOutcome.MERGED`; the real-git variant shows both merge
commits on `main` and `main != pre_phase_head`.

**(c) A `VERIFY_FAILED` task triggers the same rollback as a conflict.**
One task whose re-read status is not `Complete` (so `verify_result` →
`NOT_COMPLETE` → `VERIFY_FAILED`), alongside one clean sibling. Assert the same
post-state as (a): `report.rolled_back is True`, `main` back at
`pre_phase_head`, the clean sibling's merge **also** undone, Workstream flagged,
phase not advanced. This proves the rollback predicate keys off *any*
non-`MERGED` outcome, not specifically a conflict.

**(d) No regression.**
All **97** existing runtime tests
(`tests/crmbuilder_v2/runtime/`: `test_parallel_runtime.py` 19,
`test_coordinating_runtime.py` 20, `test_ado_runtime.py` 26,
`test_reconciliation.py` 15, `test_migration_lock.py` 9, `test_dispatcher.py` 8)
stay green. In particular the existing
`test_two_agents_run_in_parallel_and_both_merge`,
`test_cap_is_respected_with_more_work_than_slots`,
`test_results_merge_in_completion_order`,
`test_merge_conflict_pauses_dispatch_and_flags`,
`test_verify_failure_pauses_and_flags`, and `test_drains_cleanly_when_no_work`
must continue to pass — the last two will gain rollback assertions but their
existing pause/flag assertions must not change. The `--max-concurrent 1` happy
path (covered through the serial Layer-1 tests and any cap-1 pool test) must
show identical all-clean behavior.

`ruff check` clean on every touched file
(`parallel_runtime.py`, `coordinating_runtime.py`, and the test module) is part
of the gate.

## 9. Implementation checklist (for the Develop Work Task)

1. `coordinating_runtime.py`: add `CoordinatingRuntime._base_head()` and
   `._reset_base_to(head)` beside `_merge` (§4).
2. `parallel_runtime.py`: add `pre_phase_head: str | None = None`,
   `rolled_back: bool = False`, `rolled_back_to: str | None = None` to
   `PoolRunReport`.
3. `parallel_runtime.py`: in `run()`, capture `pre_phase_head` under
   `self._repo_lock` before the first `_fill_slots` (§3.1); set
   `report.pre_phase_head`.
4. `parallel_runtime.py`: in `run()`'s `finally`, after
   `executor.shutdown(wait=True)` and `api.stop()`, roll back under the lock if
   `any(r.outcome is not TaskOutcome.MERGED ...)` and `report.task_reports`
   (§3.3); set `report.rolled_back` / `rolled_back_to`; log the rollback line.
5. Do **not** touch `_merge`, `_worker`, `Worktree`, the completion-order merge
   loop, `select_to_dispatch`, the serial Layer-1 loop, or any flagging path.
6. Self-verify: `ruff check` + the runtime test suite (§8d), including the new
   real-git integration test.
