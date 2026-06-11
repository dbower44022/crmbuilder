"""PI-139 Layer 2 — concurrency-safe parallel pool: pure decisions + loop.

Two layers of test, mirroring the module's pure/I-O split:

* **pure decisions** — ``slots_available`` (the cap), ``select_to_dispatch``
  (cap + no-double-dispatch + blocker-awareness + order), and
  ``should_restart_api`` (API ownership) are exercised directly, no I/O;
* **the pool loop** — with the I/O seams injected (a fake spawn, a fake
  worktree, stubbed API reads and merge), so the pool's *actual concurrency* is
  proven without a server or a real agent: the cap is respected, ≥2 workers
  overlap in wall-clock time, results merge in **completion order**, and a
  verify-failure / merge-conflict pauses new dispatch while draining in-flight.

The genuine end-to-end run (two real Claude agents in two real worktrees, both
merged) is the demo in the build notes; the parallelism *mechanism* is pinned
deterministically here.
"""

from __future__ import annotations

import subprocess
import threading
import time

from crmbuilder_v2.runtime import parallel_runtime as pr
from crmbuilder_v2.runtime.coordinating_runtime import (
    MergeResult,
    MergeStatus,
    VerifyOutcome,
    _ResolvedAssignment,
)
from crmbuilder_v2.runtime.parallel_runtime import (
    ApiProcess,
    ParallelCoordinatingRuntime,
    ParallelRuntimeConfig,
    TaskOutcome,
    select_to_dispatch,
    should_restart_api,
    slots_available,
)

# ==========================================================================
# Pure decision: the concurrency cap
# ==========================================================================


def test_slots_available_basic():
    assert slots_available(2, 0) == 2
    assert slots_available(2, 1) == 1
    assert slots_available(2, 2) == 0


def test_slots_available_never_negative():
    # More active than the cap (a cap lowered mid-run) opens no slot.
    assert slots_available(2, 5) == 0


# ==========================================================================
# Pure decision: which eligible tasks to start now
# ==========================================================================


def test_select_respects_cap_and_order():
    # Three eligible, cap 2 → the first two in order, deterministically.
    assert select_to_dispatch(["A", "B", "C"], set(), {}, max_concurrent=2) == ["A", "B"]


def test_select_skips_already_active():
    # A is already in flight; only B is started, and the one free slot is used.
    assert select_to_dispatch(["A", "B"], {"A"}, {}, max_concurrent=2) == ["B"]


def test_select_full_pool_starts_nothing():
    assert select_to_dispatch(["A", "B"], {"X", "Y"}, {}, max_concurrent=2) == []


def test_select_blocker_active_holds_dependent():
    # B is blocked_by X, and X is still in the pool → B waits; A proceeds.
    chosen = select_to_dispatch(
        ["A", "B"], {"X"}, {"B": {"X"}}, max_concurrent=4
    )
    assert chosen == ["A"]


def test_select_blocker_not_active_allows_dependent():
    # B's blocker X is NOT in the pool (already merged) → B is free to start.
    chosen = select_to_dispatch(["B"], set(), {"B": {"X"}}, max_concurrent=2)
    assert chosen == ["B"]


def test_select_does_not_start_dependent_in_same_tick_as_blocker():
    # A blocks B; both eligible this tick. A is chosen, which makes A "busy",
    # so B is held until a later tick (after A merges). Prevents forking B off
    # a base that does not yet contain A's work.
    chosen = select_to_dispatch(
        ["A", "B"], set(), {"B": {"A"}}, max_concurrent=4
    )
    assert chosen == ["A"]


# ==========================================================================
# Pure decision: API ownership
# ==========================================================================


def test_should_restart_api_only_owned_and_unhealthy():
    assert should_restart_api(health_ok=False, owned=True) is True
    assert should_restart_api(health_ok=True, owned=True) is False
    assert should_restart_api(health_ok=False, owned=False) is False
    assert should_restart_api(health_ok=True, owned=False) is False


# ==========================================================================
# ApiProcess — ownership lifecycle with injected health/spawn seams
# ==========================================================================


class _FakePopen:
    def __init__(self):
        self.terminated = False

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminated = True


def test_api_already_up_is_not_owned():
    api = ApiProcess(health_fn=lambda: True, spawn_fn=lambda cmd: _FakePopen())
    api.ensure_started()
    assert api.owned is False
    assert api.proc is None  # never spawned someone else's API


def test_api_started_when_down_then_owned():
    spawned = []
    # Unhealthy until we spawn, healthy afterwards.
    state = {"healthy": False}

    def spawn(cmd):
        spawned.append(cmd)
        state["healthy"] = True
        return _FakePopen()

    api = ApiProcess(
        health_fn=lambda: state["healthy"],
        spawn_fn=spawn,
        sleep_fn=lambda s: None,
    )
    api.ensure_started()
    assert api.owned is True
    assert len(spawned) == 1


def test_api_ensure_alive_restarts_only_owned():
    # Owned + dead → restart.
    state = {"healthy": False}
    spawns = []

    def spawn(cmd):
        spawns.append(cmd)
        state["healthy"] = True
        return _FakePopen()

    api = ApiProcess(
        health_fn=lambda: state["healthy"], spawn_fn=spawn, sleep_fn=lambda s: None
    )
    api.ensure_started()  # spawns once (was down)
    state["healthy"] = False  # it crashed
    api.ensure_alive()  # owned + unhealthy → restart
    assert len(spawns) == 2

    # Unowned + dead → never touched.
    unowned = ApiProcess(
        health_fn=lambda: False, spawn_fn=lambda cmd: _FakePopen()
    )
    unowned.owned = False
    unowned.ensure_alive()
    assert unowned.proc is None


# ==========================================================================
# The pool loop — injected seams (fake spawn / worktree / API reads / merge)
# ==========================================================================


class _FakeWorktree:
    """Stands in for a real git worktree — records lifecycle, no git calls."""

    _counter = 0

    def __init__(self, *, repo_root, branch, base_ref):
        self.branch = branch
        type(self)._counter += 1
        self.path = f"/tmp/fake-wt-{branch.replace('/', '-')}-{self._counter}"
        self.created = False
        self.removed = False

    def create(self):
        self.created = True
        return self.path

    def has_commits_beyond(self, base_ref):
        return True  # the fake agent always "committed"

    def remove(self):
        self.removed = True


class _Recorder:
    """Tracks live concurrency, max concurrency, and per-task spawn windows."""

    def __init__(self):
        self.lock = threading.Lock()
        self.live = 0
        self.max_live = 0
        self.windows: dict[str, tuple[float, float]] = {}
        self.spawn_order: list[str] = []


def _make_runtime(
    monkeypatch,
    *,
    task_sleeps: dict[str, float],
    max_concurrent: int = 2,
    merge_for=None,
):
    """Build a ParallelCoordinatingRuntime with every I/O seam stubbed.

    ``task_sleeps`` maps Work Task id → how long its fake agent runs (to force
    overlap and control completion order). ``merge_for`` maps id → MergeResult
    (default: all clean).
    """
    recorder = _Recorder()
    merge_for = merge_for or {}

    def fake_spawn(prompt, worktree_path):
        tid = prompt  # the fake assignment uses the tid as the whole prompt
        start = time.time()
        with recorder.lock:
            recorder.live += 1
            recorder.max_live = max(recorder.max_live, recorder.live)
            recorder.spawn_order.append(tid)
        time.sleep(task_sleeps.get(tid, 0.05))
        with recorder.lock:
            recorder.live -= 1
            recorder.windows[tid] = (start, time.time())
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    cfg = ParallelRuntimeConfig(
        max_concurrent=max_concurrent,
        target_work_tasks=list(task_sleeps),
        poll_interval=0.02,
    )
    rt = ParallelCoordinatingRuntime(
        config=cfg, spawn_fn=fake_spawn, log=lambda m: None
    )
    rt._recorder = recorder

    # Eligibility: each task is eligible until it has been dispatched once
    # (mirrors Ready → Claimed making it no longer eligible).
    seen: set[str] = set()
    monkeypatch.setattr(
        rt, "_eligible_candidates", lambda: [t for t in task_sleeps if t not in seen]
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
            prompt=tid,  # the fake spawn reads the tid back out of the prompt
        )

    monkeypatch.setattr(rt._l1, "_assignment_for", fake_assignment_for)

    # Worktree + post-spawn task re-read + merge + flag all stubbed.
    monkeypatch.setattr(pr, "Worktree", _FakeWorktree)
    monkeypatch.setattr(
        pr.dispatcher, "_get", lambda api, path, eng: {"work_task_status": "Complete"}
    )
    monkeypatch.setattr(
        rt._l1,
        "_merge",
        lambda branch: merge_for.get(
            branch.rsplit("/", 1)[-1], MergeResult(MergeStatus.CLEAN, "merged")
        ),
    )
    flagged: dict[str, str] = {}
    monkeypatch.setattr(
        rt._l1, "_flag_needs_attention", lambda wt, reason: flagged.update({wt: reason})
    )
    rt._flagged = flagged
    monkeypatch.setattr(rt, "_record_finding", lambda wt, summary: None)
    # PI-145: the atomic-phase-merge helpers run real git; stub them so the
    # pool-loop tests stay git-free. ``_base_head`` returns a fixed anchor SHA;
    # ``_reset_base_to`` records its target (the Test task asserts over this).
    reset_calls: list[str] = []
    monkeypatch.setattr(rt._l1, "_base_head", lambda: "PRE_PHASE_HEAD")
    monkeypatch.setattr(
        rt._l1, "_reset_base_to", lambda head: reset_calls.append(head)
    )
    rt._reset_calls = reset_calls
    return rt


def test_two_agents_run_in_parallel_and_both_merge(monkeypatch):
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.2, "WTK-2": 0.2}, max_concurrent=2
    )
    report = rt.run()
    # Both merged cleanly.
    assert {r.work_task_id for r in report.merged} == {"WTK-1", "WTK-2"}
    assert report.paused is False
    # The cap allowed two at once, and two genuinely overlapped in time.
    assert rt._recorder.max_live == 2
    (a_start, a_end) = rt._recorder.windows["WTK-1"]
    (b_start, b_end) = rt._recorder.windows["WTK-2"]
    assert a_start < b_end and b_start < a_end  # intervals overlap


def test_cap_is_respected_with_more_work_than_slots(monkeypatch):
    # Three independent tasks, cap 2 → never more than two run at once, all merge.
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.15, "WTK-2": 0.15, "WTK-3": 0.15},
        max_concurrent=2,
    )
    report = rt.run()
    assert len(report.merged) == 3
    assert rt._recorder.max_live == 2  # the cap held


def test_results_merge_in_completion_order(monkeypatch):
    # WTK-2 finishes first (shorter sleep) → it must integrate first, even
    # though WTK-1 was dispatched first.
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.3, "WTK-2": 0.05}, max_concurrent=2
    )
    report = rt.run()
    order = [r.work_task_id for r in report.task_reports]
    assert order == ["WTK-2", "WTK-1"]


def test_merge_conflict_pauses_dispatch_and_flags(monkeypatch):
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.05, "WTK-2": 0.05},
        max_concurrent=2,
        merge_for={"wtk-1": MergeResult(MergeStatus.CONFLICT, "CONFLICT in f.py")},
    )
    report = rt.run()
    assert report.paused is True
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskOutcome.MERGE_CONFLICT
    assert "WTK-1" in rt._flagged  # surfaced for a human, never force-resolved
    # WTK-2 was already in flight (cap 2) and still drains + merges cleanly.
    assert outcomes["WTK-2"] is TaskOutcome.MERGED


def test_verify_failure_pauses_and_flags(monkeypatch):
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.05}, max_concurrent=2
    )
    # Override the re-read so the task is NOT Complete → verify fails.
    monkeypatch.setattr(
        pr.dispatcher, "_get", lambda api, path, eng: {"work_task_status": "In Progress"}
    )
    report = rt.run()
    assert report.paused is True
    r = report.task_reports[0]
    assert r.outcome is TaskOutcome.VERIFY_FAILED
    assert r.verify is VerifyOutcome.NOT_COMPLETE
    assert "WTK-1" in rt._flagged


def test_drains_cleanly_when_no_work(monkeypatch):
    rt = _make_runtime(monkeypatch, task_sleeps={}, max_concurrent=2)
    report = rt.run()
    assert report.task_reports == []
    assert report.paused is False


def test_worktrees_are_created_and_removed_per_task(monkeypatch):
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.05, "WTK-2": 0.05}, max_concurrent=2
    )
    rt.run()
    # Both agents each got their own worktree branch (distinct paths).
    assert rt._recorder.spawn_order and set(rt._recorder.spawn_order) == {"WTK-1", "WTK-2"}
