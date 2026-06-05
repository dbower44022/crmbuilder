# Exclusive migration lock — build notes (PI-133)

Status: **Built on branch `pi-133-134`** (Design WSK-030 + Develop WSK-031 +
Test WSK-032). Left **In Progress** for a separate PM session to verify the
working-demo bar (an exclusive window actually held — dispatch paused, the
migration runs with no concurrent writer, dispatch resumes), merge to `main`,
and resolve PI-133.

The spec is **DEC-399**; it builds on the Layer 2 pool (**DEC-397** / PI-139)
and its API-process ownership. Requirements topic: **TOP-012** (Runtime &
Scheduling).

## What PI-133 is

A schema migration rebuilds tables / constraints and locks out or times out any
*concurrent* writer (the collision seen migrating the four-step constraint). So
a migration must run **alone**. PI-133 makes that a runtime-owned exclusive
operation layered over the Layer 2 pool — codifying the by-hand "stop API →
migrate → restart" drill as a single coordinated step, so no agent migrates ad
hoc.

The window has three phases (DEC-399):

1. **PAUSE** — the moment a migration is requested, the runtime stops filling
   slots, so no *new* agent starts.
2. **DRAIN then RUN** — the migration may begin only once the in-flight agent
   set has emptied to **zero** (a full drain). It then runs **alone** on the
   runtime's main thread, so there is provably no concurrent writer.
3. **RESUME** — when the migration finishes, the window closes and slot-filling
   resumes, dispatching any work held during the pause.

No new locking machinery: the pool's own active-agent bookkeeping plus its
main-thread serialization (already used for merges) *are* the exclusion
primitive. Pausing dispatch and waiting for `active == 0` is exactly the
no-concurrent-writer guarantee a migration needs.

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/migration_lock.py`
  - **Pure decisions** (no I/O, unit-tested directly):
    - `dispatch_allowed(phase)` — the pool may start new agents only in
      `MigrationPhase.OPEN`; both `PENDING` and `EXCLUSIVE` hold the gate closed.
    - `can_enter_exclusive(phase, active_count)` — the window may begin only when
      a migration is `PENDING` *and* the pool has fully drained (`active == 0`).
  - **`ExclusiveMigrationLock`** — the thread-safe coordinator the pool loop
    consults each tick: `request()` (OPEN → PENDING, pauses dispatch),
    `dispatch_allowed()`, `maybe_run(active_count)` (runs the migration when
    drained, then resumes — even if it raises, so the pool is never wedged),
    plus a `MigrationRecord` per window capturing `active_at_run` (== 0, the
    proof of exclusion).
- `crmbuilder-v2/src/crmbuilder_v2/runtime/parallel_runtime.py` — wired in:
  - `ParallelCoordinatingRuntime.request_migration(fn, label=...)` — the
    operator/PM (or another thread mid-run) requests an exclusive migration.
  - `_fill_slots` returns early while `not dispatch_allowed()` (the pause).
  - The `run()` loop now stays alive while a migration is outstanding, and each
    tick calls `migration_lock.maybe_run(len(active))`; when the pool drains the
    migration runs and `run()` then refills the held slots. `PoolRunReport.migrations`
    carries the windows held during the run.
- `crmbuilder-v2/scripts/demo_pi133_migration_lock.py` — the runnable demo.
- `tests/crmbuilder_v2/runtime/test_migration_lock.py` — 9 tests (pure
  decisions, coordinator lifecycle incl. error-still-resumes and
  one-window-at-a-time, and the pool window with stubbed seams).

## The working demo

`uv run python scripts/demo_pi133_migration_lock.py` — three Work Tasks, cap 2,
a migration requested while agents are in flight. Captured run:

```
  [ 0.000s] agent for WTK-1 STARTED  (live agents now: 1)
  [ 0.000s] >>> migration requested (schema change: add findings table) while agents are in flight
  [ 0.000s] agent for WTK-2 STARTED  (live agents now: 2)
  [ 0.150s] agent for WTK-1 FINISHED (live agents now: 1)
  [ 0.151s] agent for WTK-2 FINISHED (live agents now: 0)
  [ 0.151s] *** MIGRATION RUNNING — live agents at this instant: 0 (EXCLUSIVE — no concurrent writer)
  [ 0.201s] *** MIGRATION COMPLETE
  [ 0.201s] agent for WTK-3 STARTED  (live agents now: 1)
  [ 0.351s] agent for WTK-3 FINISHED (live agents now: 0)

Result
  tasks merged           : 3 / 3
  peak concurrent agents : 2 (cap 2)
  migration 'add-findings-table': ran with 0 live agent(s) → EXCLUSIVE ✔
  DEMO PASSED ✔
```

WTK-1 and WTK-2 are in flight (cap 2) when the migration is requested; **WTK-3
is held** (dispatch paused), the two in-flight agents drain to zero, the
migration runs with **0 live agents**, and only then does WTK-3 dispatch.

## What is NOT here

The substrate is the runtime coordination; the *content* of a real migration
(running an actual `alembic upgrade` as the `migration_fn`) is the caller's to
supply. The live-DB finding-table migration this enables is PI-134's, and is
prepared-but-not-applied for a PM session (see `findings-entity-build-notes.md`).
