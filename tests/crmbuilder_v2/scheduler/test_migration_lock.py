"""PI-133 — exclusive migration lock: pure decisions, coordinator, pool window.

Three layers, mirroring the module's pure/coordinator/integration split:

* **pure decisions** — ``dispatch_allowed`` (paused unless OPEN) and
  ``can_enter_exclusive`` (only PENDING + fully drained) exercised directly;
* **the coordinator** — request → pause, no-op until drained, run-when-drained,
  resume-even-on-error, one-window-at-a-time;
* **the pool window** — with the Layer 2 pool's I/O seams stubbed, a migration
  requested while agents are in flight forces the pool to drain to zero, runs
  the migration with **no live worker**, then resumes and dispatches held work.

The genuine end-to-end run (a real alembic migration held exclusive while real
agents drain) is the demo in the build notes; the lock/drain/resume *mechanism*
is pinned deterministically here.
"""

from __future__ import annotations

import subprocess
import threading
import time

import pytest
from crmbuilder_v2.scheduler import parallel_scheduler as pr
from crmbuilder_v2.scheduler.coordinating_scheduler import (
    MergeResult,
    MergeStatus,
    TestRunResult,
    _ResolvedAssignment,
)
from crmbuilder_v2.scheduler.migration_lock import (
    ExclusiveMigrationLock,
    MigrationPhase,
    can_enter_exclusive,
    dispatch_allowed,
)
from crmbuilder_v2.scheduler.parallel_scheduler import (
    ParallelCoordinatingScheduler,
    ParallelSchedulerConfig,
)


def _pass_runner(worktree_path, target):
    """PI-147: fake test runner that always passes (no subprocess)."""
    return TestRunResult(passed=True, returncode=0, target=target)

# ==========================================================================
# Pure decisions
# ==========================================================================


def test_dispatch_allowed_only_when_open():
    assert dispatch_allowed(MigrationPhase.OPEN) is True
    assert dispatch_allowed(MigrationPhase.PENDING) is False
    assert dispatch_allowed(MigrationPhase.EXCLUSIVE) is False


def test_can_enter_exclusive_requires_pending_and_full_drain():
    # Only PENDING + zero in-flight opens the window.
    assert can_enter_exclusive(MigrationPhase.PENDING, 0) is True
    # Still draining → not yet.
    assert can_enter_exclusive(MigrationPhase.PENDING, 1) is False
    assert can_enter_exclusive(MigrationPhase.PENDING, 3) is False
    # No migration requested → never.
    assert can_enter_exclusive(MigrationPhase.OPEN, 0) is False
    # Already running → not re-entered.
    assert can_enter_exclusive(MigrationPhase.EXCLUSIVE, 0) is False


# ==========================================================================
# The coordinator
# ==========================================================================


def test_request_pauses_dispatch():
    lock = ExclusiveMigrationLock(log=lambda m: None)
    assert lock.dispatch_allowed() is True
    lock.request(lambda: None, label="m")
    assert lock.phase is MigrationPhase.PENDING
    assert lock.dispatch_allowed() is False  # paused the moment it is requested
    assert lock.pending_or_running() is True


def test_maybe_run_is_noop_while_draining():
    ran = []
    lock = ExclusiveMigrationLock(log=lambda m: None)
    lock.request(lambda: ran.append(True), label="m")
    # Two agents still in flight → the migration must not run yet.
    assert lock.maybe_run(active_count=2) is False
    assert ran == []
    assert lock.phase is MigrationPhase.PENDING


def test_maybe_run_executes_when_drained_then_resumes():
    ran = []
    lock = ExclusiveMigrationLock(log=lambda m: None)
    lock.request(lambda: ran.append("done"), label="schema-x")
    # Drained to zero → runs exclusively, then resumes.
    assert lock.maybe_run(active_count=0) is True
    assert ran == ["done"]
    assert lock.phase is MigrationPhase.OPEN
    assert lock.dispatch_allowed() is True
    # The record proves it ran with no concurrent writer.
    (record,) = lock.records
    assert record.label == "schema-x"
    assert record.active_at_run == 0
    assert record.error is None
    assert record.finished_at is not None


def test_maybe_run_noop_when_nothing_pending():
    lock = ExclusiveMigrationLock(log=lambda m: None)
    assert lock.maybe_run(active_count=0) is False
    assert lock.records == []


def test_migration_error_still_resumes_dispatch():
    def boom():
        raise ValueError("bad DDL")

    lock = ExclusiveMigrationLock(log=lambda m: None)
    lock.request(boom, label="broken")
    assert lock.maybe_run(active_count=0) is True
    # Phase resumed despite the failure — the pool is never wedged.
    assert lock.phase is MigrationPhase.OPEN
    (record,) = lock.records
    assert "ValueError: bad DDL" in record.error


def test_only_one_exclusive_window_at_a_time():
    lock = ExclusiveMigrationLock(log=lambda m: None)
    lock.request(lambda: None, label="first")
    with pytest.raises(RuntimeError, match="already"):
        lock.request(lambda: None, label="second")


# ==========================================================================
# The pool window — migration drains the pool, runs alone, then resumes
# ==========================================================================


class _FakeWorktree:
    _counter = 0

    def __init__(self, *, repo_root, branch, base_ref):
        self.branch = branch
        type(self)._counter += 1
        self.path = f"/tmp/fake-wt-{branch.replace('/', '-')}-{self._counter}"

    def create(self):
        return self.path

    def has_commits_beyond(self, base_ref):
        return True

    def changed_files(self, base_ref):
        return []  # PI-147: full-suite target, harmless under the fake runner

    def remove(self):
        return None


def test_migration_runs_with_no_live_agent_then_pool_resumes(monkeypatch):
    """A migration requested while agents are in flight drains the pool to zero,
    runs alone (no concurrent writer), then the held work dispatches."""
    live = {"n": 0, "max": 0}
    live_lock = threading.Lock()
    observed_live_at_migration: list[int] = []
    requested = {"done": False}

    rt_holder: dict = {}

    def fake_spawn(prompt, worktree_path):
        with live_lock:
            live["n"] += 1
            live["max"] = max(live["max"], live["n"])
        # The first agent to start requests a migration while it (and possibly a
        # sibling) is still in flight — forcing a real drain.
        if not requested["done"]:
            requested["done"] = True
            rt_holder["rt"].request_migration(_migration_fn, label="add-findings")
        time.sleep(0.12)
        with live_lock:
            live["n"] -= 1
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def _migration_fn():
        # Capture how many agents are live at the instant the migration runs.
        with live_lock:
            observed_live_at_migration.append(live["n"])
        time.sleep(0.02)

    cfg = ParallelSchedulerConfig(
        max_concurrent=2,
        target_work_tasks=["WTK-1", "WTK-2", "WTK-3"],
        poll_interval=0.02,
    )
    rt = ParallelCoordinatingScheduler(config=cfg, spawn_fn=fake_spawn, log=lambda m: None,
                                     test_runner_fn=_pass_runner)
    rt_holder["rt"] = rt

    seen: set[str] = set()
    monkeypatch.setattr(
        rt, "_eligible_candidates", lambda: [t for t in cfg.target_work_tasks if t not in seen]
    )
    monkeypatch.setattr(rt, "_blockers_of", lambda tid: set())

    def fake_assignment_for(tid):
        seen.add(tid)
        return _ResolvedAssignment(
            work_task={"work_task_identifier": tid, "work_task_status": "Ready"},
            work_task_id=tid,
            area="api",
            profile_id="AGP-runtime",
            branch=f"ado/{tid.lower()}",
            prompt=tid,
        )

    monkeypatch.setattr(rt._l1, "_assignment_for", fake_assignment_for)
    monkeypatch.setattr(pr, "Worktree", _FakeWorktree)
    monkeypatch.setattr(
        pr.dispatcher, "_get", lambda api, path, eng: {"work_task_status": "Complete"}
    )
    monkeypatch.setattr(
        rt._l1, "_merge", lambda branch: MergeResult(MergeStatus.CLEAN, "merged")
    )
    monkeypatch.setattr(rt._l1, "_flag_needs_attention", lambda wt, reason: None)
    monkeypatch.setattr(rt, "_record_finding", lambda wt, summary: None)

    report = rt.run()

    # All three tasks completed (the held WTK-3 dispatched after the migration).
    assert len(report.merged) == 3
    # The migration ran exactly once, and ran with NO live agent — the proof of
    # exclusion, observed two independent ways.
    assert len(report.migrations) == 1
    assert report.migrations[0].active_at_run == 0
    assert observed_live_at_migration == [0]
    # The cap was never exceeded.
    assert live["max"] <= 2
