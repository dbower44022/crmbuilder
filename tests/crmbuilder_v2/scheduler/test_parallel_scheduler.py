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
from pathlib import Path

from crmbuilder_v2.scheduler import parallel_scheduler as pr
from crmbuilder_v2.scheduler.coordinating_scheduler import (
    CoordinatingScheduler,
    SchedulerConfig,
    TestRunResult,
    _ResolvedAssignment,
)
from crmbuilder_v2.scheduler.parallel_scheduler import (
    ApiProcess,
    ParallelCoordinatingScheduler,
    ParallelSchedulerConfig,
    select_to_dispatch,
    should_restart_api,
    slots_available,
)
from crmbuilder_v2.scheduler.task_contract import TaskResult, TaskStatus


def _pass_runner(worktree_path, target):
    """PI-147: a fake test runner that always passes (no subprocess)."""
    return TestRunResult(passed=True, returncode=0, target=target)


def _fail_runner(worktree_path, target):
    """PI-147: a fake test runner that always fails (no subprocess)."""
    return TestRunResult(passed=False, returncode=1, target=target, output="boom")

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
    # REQ-463: per-test injectable refresh behavior, keyed by the branch suffix
    # exactly the way ``merge_for`` keys the landing merge. ``refresh_results``
    # maps suffix → CompletedProcess (default: rc=0 "Already up to date." — the
    # fast path, so pre-REQ-463 tests behave unchanged); ``unmerged_results``
    # maps suffix → the conflicted paths ``ls-files -u`` would report (a test's
    # stub resolver clears its entry to simulate a concluded resolution).
    refresh_results: dict = {}
    unmerged_results: dict = {}

    def __init__(self, *, repo_root, branch, base_ref):
        self.branch = branch
        type(self)._counter += 1
        self.path = f"/tmp/fake-wt-{branch.replace('/', '-')}-{self._counter}"
        self.created = False
        self.removed = False
        self.abort_calls = 0

    def _key(self):
        return self.branch.rsplit("/", 1)[-1]

    def create(self):
        self.created = True
        return self.path

    def has_commits_beyond(self, base_ref):
        return True  # the fake agent always "committed"

    def changed_files(self, base_ref):
        return []  # PI-147: no git read in the fake → full-suite target, harmless

    def refresh_from(self, base_ref):
        return self.refresh_results.get(
            self._key(),
            subprocess.CompletedProcess(
                args=[], returncode=0, stdout="Already up to date.\n", stderr=""
            ),
        )

    def unmerged_paths(self):
        return list(self.unmerged_results.get(self._key(), []))

    def merge_in_progress(self):
        # The fake ties "merge concluded" to "no markers left": a resolver that
        # clears the unmerged entry has both resolved and concluded the merge.
        return bool(self.unmerged_results.get(self._key()))

    def abort_merge(self):
        self.abort_calls += 1

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
    refresh_for=None,
    unmerged_for=None,
    spawn_stdout: str = "",
    engagement: str = "CRMBUILDER",
):
    """Build a ParallelCoordinatingScheduler with every I/O seam stubbed.

    ``task_sleeps`` maps Work Task id → how long its fake agent runs (to force
    overlap and control completion order). ``merge_for`` maps id → TaskResult
    (default: all clean). ``refresh_for`` / ``unmerged_for`` map id → the
    branch-refresh CompletedProcess / conflicted paths (REQ-463; default:
    every refresh is "Already up to date", the fast path).
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
        return subprocess.CompletedProcess(
            args=[], returncode=0, stdout=spawn_stdout, stderr=""
        )

    cfg = ParallelSchedulerConfig(
        max_concurrent=max_concurrent,
        target_work_tasks=list(task_sleeps),
        poll_interval=0.02,
        engagement=engagement,
    )
    rt = ParallelCoordinatingScheduler(
        config=cfg, spawn_fn=fake_spawn, log=lambda m: None,
        test_runner_fn=_pass_runner,
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

    # Worktree + post-spawn task re-read + merge + flag all stubbed. The
    # worktree fake is a per-runtime subclass so a test's injected refresh /
    # unmerged behavior (REQ-463) never leaks across tests; the created
    # instances are kept for assertions (e.g. abort_merge calls).
    worktrees: list[_FakeWorktree] = []

    class _Wt(_FakeWorktree):
        refresh_results = refresh_for or {}
        unmerged_results = unmerged_for if unmerged_for is not None else {}

        def __init__(self, **kw):
            super().__init__(**kw)
            worktrees.append(self)

    monkeypatch.setattr(pr, "Worktree", _Wt)
    rt._worktrees = worktrees
    monkeypatch.setattr(
        pr.dispatcher, "_get", lambda api, path, eng: {"work_task_status": "Complete"}
    )
    # The landing-merge stub also records its calls so a test can assert a
    # refresh-conflicted branch never reached the landing merge (REQ-463).
    merge_calls: list[str] = []

    def fake_merge(branch):
        merge_calls.append(branch)
        return merge_for.get(
            branch.rsplit("/", 1)[-1], TaskResult(TaskStatus.SUCCEEDED, "merged")
        )

    monkeypatch.setattr(rt._l1, "_merge", fake_merge)
    rt._merge_calls = merge_calls
    flagged: dict[str, str] = {}
    monkeypatch.setattr(
        rt._l1, "_flag_needs_attention", lambda wt, reason: flagged.update({wt: reason})
    )
    rt._flagged = flagged
    monkeypatch.setattr(rt, "_record_finding", lambda wt, summary: None)
    # The phase-anchor helpers run real git; stub them so the pool-loop tests
    # stay git-free. ``_base_head`` returns a fixed anchor SHA;
    # ``_reset_base_to`` records its target — under REQ-463 the pool never
    # rolls back, so the tests assert this recorder stays EMPTY.
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
        merge_for={"wtk-1": TaskResult(TaskStatus.NEEDS_HUMAN, "CONFLICT in f.py")},
    )
    report = rt.run()
    assert report.paused is True
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.NEEDS_HUMAN
    assert "WTK-1" in rt._flagged  # surfaced for a human, never force-resolved
    # WTK-2 was already in flight (cap 2) and still drains + merges cleanly.
    assert outcomes["WTK-2"] is TaskStatus.SUCCEEDED


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
    assert r.outcome is TaskStatus.FAILED
    assert r.verify.detail == "not_complete"
    assert "WTK-1" in rt._flagged


def test_build_agent_retried_once_on_incomplete_then_merges(monkeypatch):
    # Per-agent retry: the post-spawn re-read is In Progress the first time
    # (agent incomplete) and Complete on the retry → the pool re-spawns the
    # agent once and the task then merges, instead of failing the phase.
    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.02}, max_concurrent=1)
    reads = {"n": 0}

    def fake_get(api, path, eng):
        reads["n"] += 1
        return {"work_task_status": "Complete" if reads["n"] >= 2 else "In Progress"}

    monkeypatch.setattr(pr.dispatcher, "_get", fake_get)
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED
    assert reads["n"] == 2  # re-read twice → the agent was re-spawned once
    assert "WTK-1" not in rt._flagged


def test_build_agent_incomplete_twice_fails_the_phase(monkeypatch):
    # If the retry is also incomplete, the task fails (pausing the phase —
    # REQ-463: only this task, sibling merges stand) — the retry does not mask
    # a persistently-failing agent.
    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.02}, max_concurrent=1)
    monkeypatch.setattr(
        pr.dispatcher, "_get", lambda api, path, eng: {"work_task_status": "In Progress"}
    )
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.FAILED
    assert "WTK-1" in rt._flagged


def test_affected_tests_failure_pauses_phase_and_keeps_sibling(monkeypatch):
    # PI-147: a lifecycle-clean task (Complete + commits) whose affected tests
    # are RED gets verdict TESTS_FAILED, which routes through the same fail path
    # as a verify failure — the phase pauses, and per REQ-463 the clean sibling
    # that already merged is KEPT while the Workstream is flagged. Proves the
    # PI-147 gate composes with the REQ-463 pause with no change to either.
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.05, "WTK-2": 0.15},
        max_concurrent=2,
    )
    # Both tasks are Complete (default re-read), but the affected-test run fails
    # for WTK-2's worktree (its branch name is in the fake worktree path).
    rt._l1.test_runner_fn = lambda wp, target: TestRunResult(
        passed="wtk-2" not in wp, returncode=0 if "wtk-2" not in wp else 1,
        target=target,
    )
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED  # the clean sibling stands
    assert outcomes["WTK-2"] is TaskStatus.FAILED
    verdicts = {r.work_task_id: r.verify for r in report.task_reports}
    assert verdicts["WTK-2"].detail == "tests_failed"
    assert report.rolled_back is False
    assert rt._reset_calls == []  # no reset — REQ-463 keeps the sibling merge
    assert report.paused is True
    assert "WTK-2" in rt._flagged


def test_run_pytest_real_construction(tmp_path):
    # DEC-410: an injected-seam test misses real subprocess/construction bugs.
    # Exercise the REAL run_pytest against a single fast passing test node, from
    # the repo root, asserting the command runs and the verdict maps correctly.
    from pathlib import Path

    from crmbuilder_v2.scheduler.coordinating_scheduler import run_pytest

    repo_root = str(Path(__file__).resolve().parents[3])
    target = (
        "tests/crmbuilder_v2/scheduler/test_coordinating_scheduler.py"
        "::test_verify_ok_requires_complete_and_commits"
    )
    result = run_pytest(repo_root, target)
    assert result.target == target
    assert result.passed is True
    assert result.returncode == 0


# --------------------------------------------------------------------------
# PI-157: verify-failure output persistence — parallel site (§5g) + real
# runner construction (§5h, DEC-410)
# --------------------------------------------------------------------------


def test_verify_failure_persists_output_log_parallel(monkeypatch, tmp_path):
    from crmbuilder_v2.scheduler import coordinating_scheduler as cr

    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.05})
    rt._l1.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="FAILED test_y — boom"
    )
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    report = rt.run()
    r = report.task_reports[0]
    assert r.outcome is TaskStatus.FAILED
    assert r.verify.detail == "tests_failed"
    files = list((tmp_path / "verify").glob("WTK-1-*.log"))
    assert len(files) == 1
    assert "FAILED test_y" in files[0].read_text()
    assert r.verify_log_path == str(files[0])
    # The flag reason the Workstream carries points at the log.
    assert str(files[0]) in rt._flagged["WTK-1"]


def test_verify_failure_finding_summary_carries_log_path(monkeypatch, tmp_path):
    # §3.3: the parallel finding summary gets the same " — output: {path}"
    # suffix as the flag reason (``_make_runtime`` stubs ``_record_finding`` to
    # a no-op, so capture it here).
    from crmbuilder_v2.scheduler import coordinating_scheduler as cr

    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.05})
    rt._l1.test_runner_fn = lambda wp, target: TestRunResult(
        passed=False, returncode=1, target=target, output="FAILED test_z"
    )
    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    findings: dict[str, str] = {}
    monkeypatch.setattr(
        rt, "_record_finding", lambda wt, summary: findings.update({wt: summary})
    )
    rt.run()
    [logfile] = (tmp_path / "verify").glob("WTK-1-*.log")
    assert findings["WTK-1"] == f"verification failed: tests_failed — output: {logfile}"


def test_run_pytest_real_failure_persists_wide_tail(monkeypatch, tmp_path):
    # §5h: a real red run, persisted through the real _run_affected_tests. Also
    # pins the PI-157 tail-widening — a >2000-char output is preserved (the old
    # cap truncated the traceback away).
    from crmbuilder_v2.scheduler import coordinating_scheduler as cr
    from crmbuilder_v2.scheduler.coordinating_scheduler import run_pytest

    repo_root = str(Path(__file__).resolve().parents[3])
    failing = tmp_path / "test_wtk094_deliberate_fail.py"
    failing.write_text(
        "def test_deliberately_fails():\n"
        "    print('x' * 5000)\n"
        "    raise AssertionError('deliberate failure for PI-157')\n"
    )
    result = run_pytest(repo_root, str(failing))
    assert result.passed is False and result.returncode != 0
    assert len(result.output) > 2500  # the 2000-char tail was widened

    monkeypatch.setattr(cr, "verify_log_dir", lambda: tmp_path / "verify")
    rt = CoordinatingScheduler(
        config=SchedulerConfig(),
        log=lambda m: None,
        test_runner_fn=lambda wp, target: result,
    )

    class _Wt:
        path = "/tmp/fake-wt"

        def changed_files(self, base_ref):
            return []

    verdict, log_path = rt._run_affected_tests(_Wt(), "WTK-094")
    assert verdict.detail == "tests_failed"
    assert log_path is not None and "WTK-094-" in log_path
    text = Path(log_path).read_text()
    assert "deliberate failure for PI-157" in text
    assert "work_task:  WTK-094" in text


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


# ==========================================================================
# REQ-463 — conflict-tolerant phase merge: control-flow (injected seams)
#
# REQ-463 replaced the PI-145 all-or-nothing rollback: a failed task pauses
# only itself and every verified sibling merge STANDS on the base.
# ``_make_runtime`` still records ``_reset_base_to`` calls into
# ``rt._reset_calls`` — these tests now assert that recorder stays EMPTY. The
# git *semantics* (real merge; the retained manual reset helper) are proven
# separately below.
# ==========================================================================


def test_conflict_keeps_clean_sibling_merges(monkeypatch):
    # Two parallel tasks, the second conflicts. WTK-1 merges clean first
    # (shorter sleep); WTK-2 then conflicts → REQ-463: the failed task pauses
    # only itself. WTK-1's landed merge stands (no hard reset), WTK-2 is
    # surfaced for a human, and the pool pauses new dispatch.
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.05, "WTK-2": 0.15},
        max_concurrent=2,
        merge_for={"wtk-2": TaskResult(TaskStatus.NEEDS_HUMAN, "CONFLICT in f.py")},
    )
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED  # the sibling landed…
    assert outcomes["WTK-2"] is TaskStatus.NEEDS_HUMAN
    # …and STAYS landed: no reset was issued and the report says so.
    assert rt._reset_calls == []
    assert report.rolled_back is False
    assert report.rolled_back_to is None
    assert report.pre_phase_head == "PRE_PHASE_HEAD"  # still captured (observability)
    # The owning Workstream is flagged needs_attention; the phase is paused.
    assert "WTK-2" in rt._flagged
    assert report.paused is True


def test_all_clean_phase_keeps_merges_and_does_not_roll_back(monkeypatch):
    # (b) Both tasks merge clean → the phase advances: no pause, no rollback,
    # _reset_base_to never called, both merges remain (TaskStatus.SUCCEEDED).
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.1, "WTK-2": 0.1}, max_concurrent=2
    )
    report = rt.run()
    assert {r.outcome for r in report.task_reports} == {TaskStatus.SUCCEEDED}
    assert len(report.merged) == 2
    assert report.paused is False
    assert report.rolled_back is False
    assert report.rolled_back_to is None
    assert rt._reset_calls == []  # the all-clean phase is never reset
    assert report.pre_phase_head == "PRE_PHASE_HEAD"  # still captured up front


def test_verify_failure_keeps_clean_sibling_merges(monkeypatch):
    # A VERIFY_FAILED task pauses the phase exactly like a conflict — and, per
    # REQ-463, exactly as narrowly: the clean sibling that already merged is
    # KEPT, no reset is issued, the Workstream is flagged, and the phase is not
    # advanced. Proves the pause predicate keys off ANY non-MERGED outcome
    # while the keep-siblings behavior holds for all of them.
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.05, "WTK-2": 0.15},
        max_concurrent=2,
    )
    # WTK-2's post-spawn re-read is not Complete → verify fails; WTK-1 stays Complete.
    def fake_get(api, path, eng):
        status = "In Progress" if path.endswith("WTK-2") else "Complete"
        return {"work_task_status": status}

    monkeypatch.setattr(pr.dispatcher, "_get", fake_get)
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED
    assert outcomes["WTK-2"] is TaskStatus.FAILED
    assert report.rolled_back is False
    assert report.rolled_back_to is None
    assert rt._reset_calls == []  # the clean sibling merge stands
    assert "WTK-2" in rt._flagged
    assert report.paused is True


def test_cap_one_happy_path_is_structurally_unchanged(monkeypatch):
    # (d) --max-concurrent 1: the serial happy path is identical to pre-PI-145 —
    # both tasks merge clean, the run never pauses, never rolls back,
    # _reset_base_to is never called, and at most one agent runs at a time.
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.05, "WTK-2": 0.05}, max_concurrent=1
    )
    report = rt.run()
    assert {r.outcome for r in report.task_reports} == {TaskStatus.SUCCEEDED}
    assert len(report.merged) == 2
    assert report.paused is False
    assert report.rolled_back is False
    assert rt._reset_calls == []
    assert rt._recorder.max_live == 1  # strictly serial — the cap held at 1


# ==========================================================================
# REQ-463 / PI-394 — the refresh-and-resolve flow (injected seams)
# ==========================================================================


def _conflict_proc() -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=[], returncode=1,
        stdout="CONFLICT (content): Merge conflict in pkg/__init__.py\n",
        stderr="",
    )


def test_refresh_conflict_without_auto_resolve_pauses_and_aborts(monkeypatch):
    # REQ-463 with the resolution agent OFF: a textual refresh conflict aborts
    # the worktree merge and takes the human-pause path — the branch never
    # reaches the landing merge, while the clean sibling's merge is kept.
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.05, "WTK-2": 0.15},
        max_concurrent=2,
        refresh_for={"wtk-2": _conflict_proc()},
    )
    rt.config.auto_resolve_conflicts = False
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED  # the sibling merge stands
    assert outcomes["WTK-2"] is TaskStatus.NEEDS_HUMAN
    assert report.paused is True
    assert rt._reset_calls == []
    # The conflicted worktree merge was aborted, and the landing merge was
    # never invoked for the conflicted branch.
    aborted = [w for w in rt._worktrees if w.branch == "ado/wtk-2"]
    assert aborted and aborted[0].abort_calls == 1
    assert rt._merge_calls == ["ado/wtk-1"]
    assert "WTK-2" in rt._flagged
    assert "refresh conflict on ado/wtk-2" in rt._flagged["WTK-2"]


def test_refresh_conflict_auto_resolved_by_agent_then_lands(monkeypatch):
    # REQ-463 with the resolution agent ON: the spawned agent resolves the
    # markers and concludes the merge (the fake clears the unmerged entry), so
    # the task lands instead of pausing — and the resolution prompt named the
    # conflicted files.
    unmerged = {"wtk-1": ["pkg/__init__.py"]}
    rt = _make_runtime(
        monkeypatch,
        task_sleeps={"WTK-1": 0.02},
        max_concurrent=1,
        refresh_for={"wtk-1": _conflict_proc()},
        unmerged_for=unmerged,
    )
    resolution_prompts: list[str] = []
    inner_spawn = rt.spawn_fn

    def spawn(prompt, worktree_path):
        if prompt.startswith("You are resolving a git merge conflict"):
            resolution_prompts.append(prompt)
            unmerged["wtk-1"] = []  # the agent resolved + concluded the merge
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="", stderr=""
            )
        return inner_spawn(prompt, worktree_path)

    rt.spawn_fn = spawn
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED
    assert report.paused is False
    assert rt._merge_calls == ["ado/wtk-1"]  # the branch reached the landing merge
    assert "WTK-1" not in rt._flagged
    assert len(resolution_prompts) == 1
    assert "pkg/__init__.py" in resolution_prompts[0]  # the files were named
    assert "WTK-1" in resolution_prompts[0]


def test_refresh_merge_reruns_the_affected_test_gate(monkeypatch):
    # REQ-463: a clean refresh that actually folded base commits in (NOT
    # "Already up to date") changes the code under test, so the affected-test
    # gate runs a second time before the landing merge.
    refreshed = subprocess.CompletedProcess(
        args=[], returncode=0, stdout="Merge made by the 'ort' strategy.\n",
        stderr="",
    )
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.02}, max_concurrent=1,
        refresh_for={"wtk-1": refreshed},
    )
    runs = {"n": 0}

    def counting_runner(worktree_path, target):
        runs["n"] += 1
        return TestRunResult(passed=True, returncode=0, target=target)

    rt._l1.test_runner_fn = counting_runner
    report = rt.run()
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.SUCCEEDED
    assert runs["n"] == 2  # the pre-merge gate + the post-refresh gate


def test_refresh_up_to_date_skips_the_re_test(monkeypatch):
    # The fast path: the default fake refresh is "Already up to date", so the
    # gate runs exactly once — refresh adds no re-test when nothing changed.
    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.02}, max_concurrent=1)
    runs = {"n": 0}

    def counting_runner(worktree_path, target):
        runs["n"] += 1
        return TestRunResult(passed=True, returncode=0, target=target)

    rt._l1.test_runner_fn = counting_runner
    report = rt.run()
    assert report.task_reports[0].outcome is TaskStatus.SUCCEEDED
    assert runs["n"] == 1


# ==========================================================================
# Real-git integration (actual merge; the retained manual reset helper)
#
# The control-flow tests above stub the git helpers; these exercise the real
# ``CoordinatingScheduler._base_head`` / ``_merge`` / ``_reset_base_to`` against
# a throwaway ``tmp_path`` repo. The merge --no-ff semantics and the REQ-463
# keep-sibling behavior are proven on real git; ``_reset_base_to`` is now
# manual tooling (the pool's automatic PI-145 use was removed by REQ-463) but
# its git semantics stay pinned.
# ==========================================================================


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _init_real_repo(repo: Path) -> str:
    """Init a git repo on ``main`` with one base commit; return its HEAD SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-q", "-m", "base commit")
    out = subprocess.run(
        ["git", "rev-parse", "main"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _branch_with_file(repo: Path, branch: str, filename: str, content: str) -> None:
    """Create ``branch`` off main with a one-file commit, leaving main checked out."""
    _git(repo, "checkout", "-q", "-b", branch, "main")
    (repo / filename).write_text(content)
    _git(repo, "add", filename)
    _git(repo, "commit", "-q", "-m", f"{branch}: add {filename}")
    _git(repo, "checkout", "-q", "main")


def _l1(repo: Path) -> CoordinatingScheduler:
    return CoordinatingScheduler(
        config=SchedulerConfig(repo_root=str(repo), base_branch="main"),
        spawn_fn=None,
        log=lambda _m: None,
    )


def test_real_git_clean_merges_land_then_reset_undoes_them(tmp_path):
    # ``_reset_base_to`` is manual tooling now — REQ-463 removed the pool's
    # automatic PI-145 use — but its git semantics (checkout base, then
    # ``reset --hard``) stay pinned here for the operator/tests that keep it.
    repo = tmp_path / "repo"
    anchor = _init_real_repo(repo)
    rt = _l1(repo)
    assert rt._base_head() == anchor  # the captured pre_phase_head anchor
    _branch_with_file(repo, "ado/wtk-1", "a.txt", "alpha\n")
    _branch_with_file(repo, "ado/wtk-2", "b.txt", "beta\n")
    # Both branches merge clean → two merge commits, main advances, both present.
    assert rt._merge("ado/wtk-1").status is TaskStatus.SUCCEEDED
    assert rt._merge("ado/wtk-2").status is TaskStatus.SUCCEEDED
    assert rt._base_head() != anchor
    assert (repo / "a.txt").exists() and (repo / "b.txt").exists()
    # The manual reset hard-resets main to the anchor — neither merge survives.
    rt._reset_base_to(anchor)
    assert rt._base_head() == anchor
    assert not (repo / "a.txt").exists()
    assert not (repo / "b.txt").exists()


def test_real_git_conflict_keeps_clean_sibling_on_main(tmp_path):
    # REQ-463 on real git: a conflicted branch pauses only itself. A lands and
    # STAYS on main; B's conflict is aborted (auto-resolve off — no agent);
    # no reset is ever issued, so main still carries A's merge afterwards.
    repo = tmp_path / "repo"
    anchor = _init_real_repo(repo)
    rt = _l1(repo)
    # Two branches that both add the SAME new file with conflicting content.
    _branch_with_file(repo, "ado/wtk-1", "shared.txt", "from one\n")
    _branch_with_file(repo, "ado/wtk-2", "shared.txt", "from two\n")
    # The first merges clean and lands on main...
    assert rt._merge("ado/wtk-1").status is TaskStatus.SUCCEEDED
    head_after_a = rt._base_head()
    assert head_after_a != anchor
    # ...the second conflicts; ``_merge`` aborts it, leaving no merge in progress.
    assert rt._merge("ado/wtk-2").status is TaskStatus.NEEDS_HUMAN
    # Main is exactly where A's merge left it — the clean sibling stands, with
    # A's content intact (nothing rolled back).
    assert rt._base_head() == head_after_a
    assert (repo / "shared.txt").read_text() == "from one\n"


def test_real_git_refresh_conflict_stub_resolver_lands_both(tmp_path):
    # REQ-463 end-to-end on real git: two branches fork from one base and BOTH
    # append to the same __all__-style list — the canonical union conflict. A
    # lands first; B's refresh from main then textually conflicts; a stubbed
    # resolution agent writes the union and concludes the merge inside B's
    # worktree — so B lands too and main carries BOTH additions (the conflict
    # cost an agent, not a human pause).
    from crmbuilder_v2.scheduler.coordinating_scheduler import Worktree

    repo = tmp_path / "repo"
    _init_real_repo(repo)
    (repo / "pkg.py").write_text('__all__ = [\n    "alpha",\n]\n')
    _git(repo, "add", "pkg.py")
    _git(repo, "commit", "-q", "-m", "add pkg.py")

    def _wt_git(path: str, *args: str) -> None:
        subprocess.run(
            ["git", *args], cwd=path, check=True, capture_output=True, text=True
        )

    def _fork_and_commit(branch: str, name: str) -> Worktree:
        wt = Worktree(repo_root=str(repo), branch=branch, base_ref="main")
        wt.create()
        (Path(wt.path) / "pkg.py").write_text(
            f'__all__ = [\n    "alpha",\n    "{name}",\n]\n'
        )
        _wt_git(wt.path, "add", "pkg.py")
        _wt_git(wt.path, "commit", "-q", "-m", f"{branch}: add {name}")
        return wt

    # Both worktrees fork BEFORE either lands, so B goes stale once A merges.
    wt_a = _fork_and_commit("ado/wtk-a", "bravo")
    wt_b = _fork_and_commit("ado/wtk-b", "charlie")

    prompts: list[str] = []

    def stub_resolver(prompt, worktree_path):
        # The "resolution agent": write the union resolution, then conclude
        # the merge exactly as the prompt instructs (add + commit --no-edit).
        prompts.append(prompt)
        (Path(worktree_path) / "pkg.py").write_text(
            '__all__ = [\n    "alpha",\n    "bravo",\n    "charlie",\n]\n'
        )
        _wt_git(worktree_path, "add", "pkg.py")
        _wt_git(worktree_path, "commit", "-q", "--no-edit")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    cfg = ParallelSchedulerConfig(
        repo_root=str(repo), base_branch="main", max_concurrent=1
    )
    rt = ParallelCoordinatingScheduler(
        config=cfg, spawn_fn=stub_resolver, log=lambda _m: None,
        test_runner_fn=_pass_runner,
    )

    def _integrate(wt: Worktree, tid: str):
        assignment = _ResolvedAssignment(
            work_task={"work_task_identifier": tid, "work_task_status": "Complete"},
            work_task_id=tid, area="scheduler", profile_id="AGP-runtime",
            branch=wt.branch, prompt=tid,
        )
        run = pr._AgentRun(
            assignment=assignment, worktree=wt, returncode=0,
            refreshed_task={"work_task_status": "Complete"},
            has_commits=True, spawned_at=0.0, finished_at=0.0,
        )
        return rt._integrate(run)

    # A lands clean (its refresh is "Already up to date" — main never moved).
    assert _integrate(wt_a, "WTK-A").outcome is TaskStatus.SUCCEEDED
    assert prompts == []  # no conflict, no resolution agent

    # B's refresh conflicts; the stub resolver settles it; B lands too.
    assert _integrate(wt_b, "WTK-B").outcome is TaskStatus.SUCCEEDED
    assert len(prompts) == 1
    assert "pkg.py" in prompts[0] and "WTK-B" in prompts[0]

    merged = (repo / "pkg.py").read_text()
    assert '"bravo"' in merged and '"charlie"' in merged  # both additions on main


def test_parallel_run_records_fleet_cost(v2_env, monkeypatch):
    """Regression (DEC-637): the Layer-2 pool is the path the ADO runtime uses for
    development, so a coding-agent spawn here must record a claude_cli cost event.
    PI-264 originally instrumented only the Layer-1 loop, so the dominant fleet spend
    went uncaptured — a live dev-lane run recorded zero claude_cli events."""
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import cost_events

    blob = (
        '{"type":"result","total_cost_usd":0.4,'
        '"usage":{"input_tokens":1000,"output_tokens":500},'
        '"model":"claude-opus-4-8"}'
    )
    # The pool runs agents in worker threads where the main thread's ambient
    # engagement does NOT propagate, so capture must resolve cfg.engagement. v2_env
    # seeds ENG-001 (code TESTENG); pass the code, exactly as the live ADO config does.
    rt = _make_runtime(
        monkeypatch, task_sleeps={"WTK-1": 0.05}, max_concurrent=1,
        spawn_stdout=blob, engagement="TESTENG",
    )
    rt.run()
    with session_scope() as s:
        agg = cost_events.aggregate(s, source="claude_cli")
        assert agg["event_count"] == 1, "Layer-2 fleet spawn must record a cost event"
        row = cost_events.recent(s, source="claude_cli")[0]
    assert row["work_task"] == "WTK-1"
    assert row["area"] == "api" and row["stage"] == "develop"
    assert row["cost_reported_usd"] == 0.4
    assert row["cost_usd"] > 0  # opus priced from tokens


def test_worker_error_pauses_not_hangs(monkeypatch):
    """DEC-645 (PI-139 defect): a worker whose post-agent verify call raises (e.g. the
    API 500s) must still report a failure, so the pool drains and pauses. Pre-fix the
    unreported task pinned `active` and the pool hung forever — so this runs the pool
    in a thread with a deadline and asserts it actually returned."""
    import threading

    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.02}, max_concurrent=1)

    def boom(api, path, eng):  # the verify-by-result HTTP call fails
        raise RuntimeError("API 500 during verify")

    monkeypatch.setattr(pr.dispatcher, "_get", boom)

    result: dict = {}

    def go():
        result["report"] = rt.run()

    t = threading.Thread(target=go)
    t.start()
    t.join(timeout=15)
    assert not t.is_alive(), "pool hung — a worker error was not reported (DEC-645)"
    report = result["report"]
    assert report.paused is True
    outcomes = {r.work_task_id: r.outcome for r in report.task_reports}
    assert outcomes["WTK-1"] is TaskStatus.FAILED
    assert "WTK-1" in rt._flagged  # surfaced for a human


def test_pool_watchdog_halts_a_stranded_worker(monkeypatch):
    # REQ-440 / PI-379: a worker dispatched into `active` that never enqueues a
    # result used to spin the drain loop forever (the REL-038 hang). The
    # no-progress watchdog must halt the phase cleanly within budget + grace.
    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-1": 0.01}, max_concurrent=1)
    rt.config.agent_timeout = 0
    rt.config.phase_no_progress_grace = 0.2
    # The worker never reports — simulate a strand (e.g. a worktree-add failure
    # that never made it onto the completion queue).
    monkeypatch.setattr(rt, "_worker", lambda assignment: None)

    start = time.time()
    report = rt.run()
    elapsed = time.time() - start

    assert elapsed < 5.0, "watchdog did not halt the stranded phase — it hung"
    assert report.paused is True
    assert "watchdog" in (report.pause_reason or "").lower()
    assert "WTK-1" in rt._flagged
    assert any(r.outcome is TaskStatus.FAILED for r in report.task_reports)


def test_worker_enqueues_result_even_when_token_revoke_raises(monkeypatch):
    # REQ-440 / PI-379: the result must be enqueued BEFORE the best-effort token
    # revoke, so a revoke error (a side-band write) can never strand the task.
    rt = _make_runtime(monkeypatch, task_sleeps={"WTK-9": 0.01})

    def boom(engagement, token_id):
        raise RuntimeError("revoke failed")

    monkeypatch.setattr(pr.agent_identity, "revoke", boom)
    assignment = _ResolvedAssignment(
        work_task={"work_task_identifier": "WTK-9", "work_task_status": "Ready"},
        work_task_id="WTK-9", area="api", profile_id="AGP-runtime",
        branch="ado/wtk-9", prompt="WTK-9",
    )

    rt._worker(assignment)  # must not raise despite the revoke error

    result = rt._completed.get_nowait()  # the result IS on the queue
    assert result.assignment.work_task_id == "WTK-9"
