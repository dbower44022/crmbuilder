"""Coordinating runtime — Layer 2 (concurrency-safe parallel execution).

Layer 1 (:mod:`.coordinating_scheduler`) closed the loop: it actually spawns a
Claude Code agent in a worktree, verifies, merges, and pauses for a human — but
**one agent at a time** (DEC-395). Layer 2 generalizes that single-spawn unit
into a **capped parallel pool** per **DEC-397**:

1. **a capped pool of agents** — up to ``max_concurrent`` Claude Code sessions
   run at once, each in its **own** git worktree taken from current ``main``;
2. **start-on-slot-free** — whenever a slot frees and eligible (unblocked) work
   exists, a new agent starts, up to the cap;
3. **merge-as-complete** — as each agent finishes, the runtime verifies by
   result and merges its branch back (``--no-ff``) **in completion order**; a
   merge conflict halts *that* merge, records a finding, raises
   ``needs_attention``, and stops new dispatch — never force-resolved;
4. **the runtime owns the API process** — it starts it if needed, monitors
   ``/health``, and restarts it on crash, so **no agent ever restarts it**.

This is where the multi-user safety of the agent system lands. The exclusive
migration lock (PI-133) and the reconciliation-gate enforcement (PI-134) are
**separate PIs built on top of this engine** and are deliberately *not* here.

Layer 1's proven single-spawn-in-worktree is reused unchanged as the pool unit:
:class:`~.coordinating_scheduler.Worktree`, :func:`~.coordinating_scheduler.spawn_claude_agent`,
:func:`~.coordinating_scheduler.verify_result`, :func:`~.coordinating_scheduler.interpret_merge`,
and the I/O helpers on :class:`~.coordinating_scheduler.CoordinatingScheduler`
(``_assignment_for`` / ``_merge`` / ``_flag_needs_attention`` / ``_owning_workstream``)
are composed here rather than reimplemented.

The pure decisions — how many slots are free, which eligible Work Tasks to start
now (cap + completion-order + blocker-awareness), and whether to restart the API
— are split from the threading / git / subprocess / HTTP I/O so they are
unit-testable without a server, a worktree, or a spawned agent.
"""

from __future__ import annotations

import queue
import subprocess
import threading
import time
import urllib.parse
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

from crmbuilder_v2.scheduler import dispatcher
from crmbuilder_v2.scheduler.coordinating_scheduler import (
    CoordinatingScheduler,
    MergeResult,
    MergeStatus,
    SchedulerConfig,
    TestRunnerFn,
    Worktree,
    _ResolvedAssignment,
    spawn_claude_agent,
    verify_result,
)
from crmbuilder_v2.scheduler.task_contract import TaskResult
from crmbuilder_v2.scheduler.migration_lock import ExclusiveMigrationLock

# --------------------------------------------------------------------------
# Pure pool decisions (no I/O — unit-tested directly)
# --------------------------------------------------------------------------


def slots_available(max_concurrent: int, active_count: int) -> int:
    """How many new agents may start right now, given the cap (REQ-055).

    Never negative: if more are somehow active than the cap, no new slot opens.
    """
    return max(0, max_concurrent - active_count)


def select_to_dispatch(
    candidates: list[str],
    active: set[str],
    blockers_of: dict[str, set[str]],
    *,
    max_concurrent: int,
) -> list[str]:
    """Pick which candidate Work Task ids to start now — the core pool decision.

    Honors three constraints, so the pool stays concurrency-safe (REQ-055/056):

    * **the cap** — at most ``slots_available`` new tasks, never exceeding
      ``max_concurrent`` across the already-active set plus the chosen set;
    * **no double-dispatch** — a task already ``active`` is skipped;
    * **blocker-awareness** — a task is *not* started while any task it is
      ``blocked_by`` is still being processed by this pool (active). A blocker
      that is *not* active is assumed already merged (a prior completion or a
      prior run), so its dependent is free to fork from the now-current base.

    ``candidates`` is consumed in priority order (the caller supplies identifier
    order), so the selection is deterministic.
    """
    free = slots_available(max_concurrent, len(active))
    chosen: list[str] = []
    busy = set(active)
    for cand in candidates:
        if free <= 0:
            break
        if cand in busy:
            continue
        if blockers_of.get(cand, set()) & busy:
            # A blocker is still in the pool (in-flight or awaiting merge): the
            # dependent must wait so it forks from the merged predecessor.
            continue
        chosen.append(cand)
        busy.add(cand)
        free -= 1
    return chosen


def should_restart_api(health_ok: bool, owned: bool) -> bool:
    """Whether the runtime should (re)start the API process now (API ownership).

    Restart **only** an API the runtime owns, and **only** when it is unhealthy.
    An externally-launched API (``owned`` False) is never touched — the runtime
    owns the process it started; it does not commandeer someone else's. And
    *agents* never restart it at all (the operating protocol gives them no such
    instruction). Together these guarantee a single owner of the API lifecycle.
    """
    return owned and not health_ok


# --------------------------------------------------------------------------
# Outcome records the pool and its tests reason over
# --------------------------------------------------------------------------


class TaskOutcome(str, Enum):
    """What happened to one Work Task that the pool ran to completion."""

    MERGED = "merged"  # verified + merged cleanly into the base branch
    VERIFY_FAILED = "verify_failed"  # not Complete, or Complete with no commits
    MERGE_CONFLICT = "merge_conflict"  # verified, but the branch would not merge


@dataclass
class TaskReport:
    """A human- and test-readable record of one Work Task's pool lifecycle.

    The timestamps are what *prove the parallelism*: two tasks whose
    ``[spawned_at, finished_at]`` intervals overlap ran at the same time.
    """

    work_task_id: str
    branch: str
    outcome: TaskOutcome
    verify: TaskResult | None = None
    merge: MergeResult | None = None
    agent_returncode: int | None = None
    spawned_at: float | None = None
    finished_at: float | None = None
    merged_at: float | None = None
    # PI-157: absolute path of the persisted verify-failure pytest output
    # (None on a green run, a pre-test verdict, or a failed log write).
    verify_log_path: str | None = None


@dataclass
class PoolRunReport:
    """The result of one parallel run: every task's report + the pause state."""

    task_reports: list[TaskReport] = field(default_factory=list)
    paused: bool = False
    pause_reason: str | None = None
    # PI-133: each exclusive migration window held during the run (proof of the
    # drained, no-concurrent-writer property is ``active_at_run == 0``).
    migrations: list = field(default_factory=list)
    # PI-145: atomic (all-or-nothing) phase merge. ``pre_phase_head`` is the
    # base_branch HEAD captured before the phase pool dispatched its first
    # worker; if any task failed, ``run()`` resets base_branch back to it,
    # undoing every sibling merge from this phase (``rolled_back`` /
    # ``rolled_back_to`` record that distinctly from a plain pause).
    pre_phase_head: str | None = None
    rolled_back: bool = False
    rolled_back_to: str | None = None

    @property
    def merged(self) -> list[TaskReport]:
        return [r for r in self.task_reports if r.outcome is TaskOutcome.MERGED]


@dataclass
class _AgentRun:
    """A worker thread's result, handed to the main thread for verify + merge."""

    assignment: _ResolvedAssignment
    worktree: Worktree
    returncode: int | None
    refreshed_task: dict
    has_commits: bool
    spawned_at: float
    finished_at: float


# --------------------------------------------------------------------------
# The API process the runtime owns (start / monitor / restart)
# --------------------------------------------------------------------------


@dataclass
class ApiProcess:
    """The API process under the runtime's ownership (REQ — API ownership).

    ``ensure_started`` brings an API up if one is not already reachable; if one
    *is* already reachable the runtime treats it as externally owned and will
    not manage it (``owned`` stays False). ``ensure_alive`` restarts only an
    owned API that has gone unhealthy. ``stop`` tears down only what we started.
    """

    api_base: str = "http://127.0.0.1:8765"
    engagement: str = "CRMBUILDER"
    command: list[str] = field(default_factory=lambda: ["crmbuilder-v2-api"])
    log: Callable[[str], None] = print
    ready_timeout: float = 30.0
    poll: float = 0.5
    proc: subprocess.Popen | None = None
    owned: bool = False
    # Injectable seams so ownership is testable without a real process/server.
    health_fn: Callable[[], bool] | None = None
    spawn_fn: Callable[[list[str]], subprocess.Popen] | None = None
    sleep_fn: Callable[[float], None] = time.sleep

    def health_ok(self) -> bool:
        if self.health_fn is not None:
            return self.health_fn()
        try:
            data = dispatcher._get(self.api_base, "/health", self.engagement)
            return bool(isinstance(data, dict) and data.get("ok"))
        except Exception:
            return False

    def ensure_started(self) -> None:
        if self.health_ok():
            self.owned = False  # already up — not ours to manage
            self.log("  (api) reachable already — externally owned, not managed")
            return
        self._spawn_and_wait()

    def ensure_alive(self) -> None:
        if not should_restart_api(self.health_ok(), self.owned):
            return
        self.log("  (api) owned API unhealthy — restarting")
        self._spawn_and_wait()

    def stop(self) -> None:
        if self.proc is not None and self.owned:
            self.log("  (api) stopping owned API")
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None

    def _spawn_and_wait(self) -> None:
        self.log(f"  (api) starting: {' '.join(self.command)}")
        spawn = self.spawn_fn or (
            lambda cmd: subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        )
        self.proc = spawn(self.command)
        self.owned = True
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            if self.health_ok():
                self.log("  (api) healthy")
                return
            self.sleep_fn(self.poll)
        raise RuntimeError(
            f"owned API did not become healthy within {self.ready_timeout}s"
        )


# --------------------------------------------------------------------------
# Configuration + the parallel pool
# --------------------------------------------------------------------------


@dataclass
class ParallelSchedulerConfig(SchedulerConfig):
    """Layer-2 wiring: Layer-1 config + the concurrency cap and API ownership."""

    max_concurrent: int = 2
    manage_api: bool = False
    poll_interval: float = 1.0
    # Run only this explicit set of Work Tasks (the most precise demo control);
    # falls back to ``target_workstream`` / next-eligible-globally when None.
    target_work_tasks: list[str] | None = None
    # PI-220 (PRJ-030): engage the file-lock backstop on merge-back — verify the
    # sub-agent's diff against the resource locks and reclaim a dead child's locks.
    # Default off; a no-op anyway outside a dev-lane release. The release-dev driver
    # sets it True. Existing ADO runs are byte-identical with it off.
    enable_file_locks: bool = False


# Type alias for the injectable spawn seam.
SpawnFn = Callable[[str, str], subprocess.CompletedProcess]


@dataclass
class ParallelCoordinatingScheduler:
    """The Layer-2 concurrency-safe parallel pool (DEC-397).

    Composition over inheritance: a Layer-1 :class:`CoordinatingScheduler` is held
    as ``_l1`` and its I/O helpers (assignment resolution, merge, flag,
    owning-workstream lookup) are reused, so this class only adds the pool
    orchestration — slot filling, parallel spawn, completion-ordered merging,
    and API-process ownership.
    """

    config: ParallelSchedulerConfig
    spawn_fn: SpawnFn | None = None
    log: Callable[[str], None] = print
    reports: list[TaskReport] = field(default_factory=list)
    api: ApiProcess | None = None
    migration_lock: ExclusiveMigrationLock | None = None
    # PI-147: pass-through to the Layer-1 runtime's injectable test runner, so
    # the parallel verify step (which calls self._l1._run_affected_tests) uses
    # the same seam. Default None → the real run_pytest.
    test_runner_fn: TestRunnerFn | None = None
    # An optional *shared* repo lock. When several pools run concurrently against
    # one repo (parallel independent PIs, ADO item 2), passing one shared lock
    # serializes their worktree/merge git ops across pools; left None each pool
    # gets its own lock (the single-PI case).
    repo_lock: threading.Lock | None = None

    def __post_init__(self) -> None:
        # The Layer-1 runtime provides the proven per-task I/O unit. Its spawn
        # is unused here (we drive spawns from the pool), but it carries the
        # assignment/merge/flag helpers keyed off the same config.
        self._l1 = CoordinatingScheduler(
            config=self.config, spawn_fn=None, log=self.log,
            test_runner_fn=self.test_runner_fn,
        )
        self._repo_lock = self.repo_lock or threading.Lock()
        self._completed: queue.Queue[_AgentRun] = queue.Queue()
        if self.config.manage_api and self.api is None:
            self.api = ApiProcess(
                api_base=self.config.api_base,
                engagement=self.config.engagement,
                log=self.log,
            )
        # PI-133: the exclusive-migration coordinator the loop consults each tick.
        if self.migration_lock is None:
            self.migration_lock = ExclusiveMigrationLock(log=self.log)

    def request_migration(
        self, migration_fn: Callable[[], None], *, label: str = "migration"
    ) -> None:
        """Request a schema migration as a runtime-owned exclusive step (PI-133).

        Pauses new agent dispatch immediately; the pool then drains its in-flight
        agents and runs ``migration_fn`` alone (no concurrent writer) before
        resuming. Thread-safe — may be called from another thread mid-run.
        """
        assert self.migration_lock is not None
        self.migration_lock.request(migration_fn, label=label)

    # --- pure-ish reads that feed the pool decisions --------------------
    def _eligible_candidates(self) -> list[str]:
        """The dispatchable Work Task ids right now, in identifier order."""
        cfg = self.config
        if cfg.target_work_tasks:
            out: list[str] = []
            for tid in cfg.target_work_tasks:
                wt = dispatcher._get(
                    cfg.api_base, f"/work-tasks/{tid}", cfg.engagement
                )
                blockers = dispatcher._blocker_statuses(
                    cfg.api_base, cfg.engagement, tid
                )
                # PI-134: the reconciliation gate withholds a Develop Work Task
                # whose Design is incomplete or has an open blocking finding.
                if dispatcher.is_work_task_eligible(
                    wt, blockers
                ) and self._l1._reconciliation_gate_open(wt):
                    out.append(tid)
            return out
        eligible = dispatcher.eligible_work_tasks(cfg.api_base, cfg.engagement)
        if cfg.target_workstream is not None:
            members = self._l1._workstream_members(cfg.target_workstream)
            eligible = [
                w for w in eligible if w["work_task_identifier"] in members
            ]
        eligible = [
            w for w in eligible if self._l1._reconciliation_gate_open(w)
        ]
        return [w["work_task_identifier"] for w in eligible]

    def _blockers_of(self, work_task_id: str) -> set[str]:
        cfg = self.config
        edges = dispatcher._get(
            cfg.api_base,
            "/references?"
            + urllib.parse.urlencode(
                {"source_id": work_task_id, "relationship": "blocked_by"}
            ),
            cfg.engagement,
        )
        return {
            e["target_id"] for e in edges if e.get("target_type") == "work_task"
        }

    # --- slot filling: start as many eligible agents as the cap allows --
    def _fill_slots(self, executor: ThreadPoolExecutor, active: set[str]) -> None:
        cfg = self.config
        # PI-133: while a migration is pending/running, dispatch is paused so the
        # pool can drain to zero in-flight agents and the migration runs alone.
        if self.migration_lock is not None and not self.migration_lock.dispatch_allowed():
            return
        if slots_available(cfg.max_concurrent, len(active)) <= 0:
            return
        candidates = self._eligible_candidates()
        blockers_of = {c: self._blockers_of(c) for c in candidates}
        chosen = select_to_dispatch(
            candidates, set(active), blockers_of, max_concurrent=cfg.max_concurrent
        )
        for tid in chosen:
            assignment = self._l1._assignment_for(tid)
            if assignment is None:
                # Lost eligibility in a race between the poll and now — skip.
                continue
            active.add(tid)
            self.log(
                f"▶ dispatching {tid} (area={assignment.area}, "
                f"profile={assignment.profile_id}) → worktree branch "
                f"{assignment.branch}"
            )
            executor.submit(self._worker, assignment)

    # --- the worker thread: create worktree, spawn agent, prep result ---
    def _spawn_one(self, assignment: _ResolvedAssignment) -> _AgentRun:
        """Spawn one agent for ``assignment`` and collect its result by reading
        the task + branch back. Factored out of :meth:`_worker` so the
        integration step can re-spawn synchronously for a per-agent retry."""
        cfg = self.config
        spawned_at = time.time()
        # Git worktree metadata mutations are serialized; the long agent spawn
        # is NOT — that is where the real parallelism lives. Worktree.create
        # deletes any stale same-named branch, so a re-spawn starts clean.
        with self._repo_lock:
            worktree = Worktree(
                repo_root=cfg.repo_root,
                branch=assignment.branch,
                base_ref=cfg.base_branch,
            )
            worktree.create()
        self.log(f"  [{assignment.work_task_id}] spawning agent in {worktree.path} …")
        returncode: int | None = None
        try:
            spawn = self.spawn_fn or (
                lambda p, wp: spawn_claude_agent(p, wp, timeout=cfg.agent_timeout)
            )
            proc = spawn(assignment.prompt, worktree.path)
            returncode = proc.returncode
            self.log(f"  [{assignment.work_task_id}] agent exited rc={returncode}")
        except subprocess.TimeoutExpired:
            self.log(
                f"  [{assignment.work_task_id}] hit the {cfg.agent_timeout}s "
                "deadline and was killed — verifying by result anyway"
            )
        finished_at = time.time()
        # Verify by result (DEC-396): re-read the task + check the branch.
        refreshed = dispatcher._get(
            cfg.api_base, f"/work-tasks/{assignment.work_task_id}", cfg.engagement
        )
        with self._repo_lock:
            has_commits = worktree.has_commits_beyond(cfg.base_branch)
        return _AgentRun(
            assignment=assignment,
            worktree=worktree,
            returncode=returncode,
            refreshed_task=refreshed,
            has_commits=has_commits,
            spawned_at=spawned_at,
            finished_at=finished_at,
        )

    def _worker(self, assignment: _ResolvedAssignment) -> None:
        self._completed.put(self._spawn_one(assignment))

    # --- integrate one completed agent (main thread, serialized) --------
    def _integrate(self, run: _AgentRun) -> TaskReport:
        a = run.assignment
        verdict = verify_result(run.refreshed_task, run.has_commits)
        if verdict.detail in ("not_complete", "no_commits"):
            # Per-agent retry: an agent that exits without driving its task to
            # Complete (or with an empty branch) is most often a transient agent
            # incompletion — not bad work the gate should reject. Re-spawn the
            # agent ONCE before failing the task (which would roll the whole
            # all-or-nothing phase back). A genuine test failure (TESTS_FAILED)
            # or merge conflict is NOT retried here — only incompletion.
            self.log(
                f"  [{a.work_task_id}] incomplete ({(verdict.detail or verdict.status.value)}) "
                "— retrying agent once"
            )
            run.worktree.remove()
            run = self._spawn_one(a)
            verdict = verify_result(run.refreshed_task, run.has_commits)
        verify_log_path = None
        if verdict.ok:
            # PI-147: run the affected test package before merging. The
            # changed_files git read touches the shared repo, so take the lock
            # for it; the helper's pytest subprocess runs in the worker's own
            # worktree (a future optimization may drop the lock around it).
            with self._repo_lock:
                verdict, verify_log_path = self._l1._run_affected_tests(
                    run.worktree, a.work_task_id
                )
        self.log(
            f"  [{a.work_task_id}] verify: {(verdict.detail or verdict.status.value)} "
            f"(branch_has_commits={run.has_commits})"
        )
        if not verdict.ok:
            log_suffix = f" — output: {verify_log_path}" if verify_log_path else ""
            self._l1._flag_needs_attention(
                a.work_task_id,
                f"verification failed: {(verdict.detail or verdict.status.value)} "
                f"(agent rc={run.returncode}){log_suffix}",
            )
            self._record_finding(
                a.work_task_id,
                f"verification failed: {(verdict.detail or verdict.status.value)}{log_suffix}",
            )
            self._reclaim_locks(a.work_task_id)  # PI-220: free a failed child's locks (FL-6)
            run.worktree.remove()
            return TaskReport(
                work_task_id=a.work_task_id,
                branch=a.branch,
                outcome=TaskOutcome.VERIFY_FAILED,
                verify=verdict,
                agent_returncode=run.returncode,
                spawned_at=run.spawned_at,
                finished_at=run.finished_at,
                verify_log_path=verify_log_path,
            )
        # PI-220 (FL-5): capture the sub-agent's touched files from its worktree
        # before it is removed, so the lock backstop can verify the real diff.
        touched_paths: list[str] = []
        if self.config.enable_file_locks:
            try:
                touched_paths = run.worktree.changed_files(self.config.base_branch)
            except Exception as exc:  # never let a diff read break the merge
                self.log(f"  [{a.work_task_id}] (lock) could not read diff: {exc}")
        # Merge is serialized: only one branch lands on the base at a time, in
        # completion order (the order results arrive on the queue).
        with self._repo_lock:
            merge = self._l1._merge(a.branch)
            merged_at = time.time()
            run.worktree.remove()
        self.log(f"  [{a.work_task_id}] merge: {merge.status.value}")
        if merge.status is MergeStatus.CONFLICT:
            self._l1._flag_needs_attention(
                a.work_task_id,
                f"merge conflict on {a.branch}: {merge.detail[:200]}",
            )
            self._record_finding(
                a.work_task_id, f"merge conflict on {a.branch}"
            )
            self._reclaim_locks(a.work_task_id)  # PI-220: free the child's locks (FL-6)
            return TaskReport(
                work_task_id=a.work_task_id,
                branch=a.branch,
                outcome=TaskOutcome.MERGE_CONFLICT,
                verify=verdict,
                merge=merge,
                spawned_at=run.spawned_at,
                finished_at=run.finished_at,
            )
        # PI-220 (FL-5): verify the merged diff against the resource locks +
        # release this holder's locks. A flagged overlap is the mis-judged grain.
        if self.config.enable_file_locks:
            self._coordinate_locks_on_merge(a.work_task_id, touched_paths)
        self.log(
            f"✔ {a.work_task_id} verified + merged into {self.config.base_branch}"
        )
        return TaskReport(
            work_task_id=a.work_task_id,
            branch=a.branch,
            outcome=TaskOutcome.MERGED,
            verify=verdict,
            merge=merge,
            agent_returncode=run.returncode,
            spawned_at=run.spawned_at,
            finished_at=run.finished_at,
            merged_at=merged_at,
        )

    def _coordinate_locks_on_merge(
        self, work_task_id: str, touched_paths: list[str]
    ) -> None:
        """PI-220 (FL-5): verify the merged diff against the file locks + release
        them. Defensive and no-op outside a dev-lane release — a lock error never
        breaks the merge / PI-145 atomicity. An overlap held by another sub-agent
        is the mis-judged grain the lock exists to catch; surface it as a finding.
        """
        try:
            from crmbuilder_v2.access.db import session_scope
            from crmbuilder_v2.scheduler import sub_agent_locks

            with session_scope() as s:
                report = sub_agent_locks.verify_and_release(
                    s, work_task_id, touched_paths
                )
            if report and report.get("conflicts"):
                detail = "; ".join(
                    f"{c['resource']}@{c['holder']}" for c in report["conflicts"]
                )
                self.log(f"  [{work_task_id}] (lock) overlap: {detail}")
                self._record_finding(
                    work_task_id, f"file-lock overlap on merge: {detail}"
                )
        except Exception as exc:  # lock coordination is a backstop, never fatal
            self.log(f"  [{work_task_id}] (lock) coordination skipped: {exc}")

    def _reclaim_locks(self, work_task_id: str) -> None:
        """PI-220 (FL-6): release a failed/dead sub-agent's locks. Defensive +
        opt-in; no-op when file locks are off or outside a dev-lane release."""
        if not self.config.enable_file_locks:
            return
        try:
            from crmbuilder_v2.access.db import session_scope
            from crmbuilder_v2.scheduler import sub_agent_locks

            with session_scope() as s:
                if sub_agent_locks.dev_lane_release(s, work_task_id) is not None:
                    sub_agent_locks.reclaim(s, work_task_id)
        except Exception as exc:
            self.log(f"  [{work_task_id}] (lock) reclaim skipped: {exc}")

    def _record_finding(self, work_task_id: str, summary: str) -> None:
        """Record a conflict/verify-failure as a finding (DEC-397).

        The ``finding`` (``FND-``) entity is a PI-134 reconciliation-gate build
        and is not yet a live endpoint; until it lands, the ``needs_attention``
        flag set alongside this call IS the recorded, queryable human signal.
        Best-effort: try the endpoint, never mask the real outcome on failure.
        """
        try:
            dispatcher._post(
                self.config.api_base,
                "/findings",
                self.config.engagement,
                {
                    "finding_summary": summary,
                    "finding_source_work_task": work_task_id,
                },
            )
        except Exception:
            self.log(f"  [{work_task_id}] finding recorded as needs_attention: {summary}")

    # --- the pool loop ---------------------------------------------------
    def run(self) -> PoolRunReport:
        """Drive the capped parallel pool to drain or a human-judgment pause.

        Fills free slots with eligible work, waits for completions, and merges
        each result in completion order — refilling as slots free — until no
        eligible work remains *and* nothing is in flight (drained), or a
        verify-failure / merge-conflict pauses new dispatch (the in-flight
        agents are then drained and integrated before the run returns).
        """
        cfg = self.config
        lock = self.migration_lock
        executor = ThreadPoolExecutor(max_workers=cfg.max_concurrent)
        active: set[str] = set()
        report = PoolRunReport()
        paused = False

        def migration_outstanding() -> bool:
            return lock is not None and lock.pending_or_running()

        try:
            if cfg.manage_api and self.api is not None:
                self.api.ensure_started()
            # PI-145: capture the phase's pre-merge anchor BEFORE any worker forks
            # a worktree or merges, so a failed phase can be rolled back to a main
            # that still carries none of this phase's work. Locked so the rev-parse
            # cannot race a worker's worktree create/merge git ops.
            with self._repo_lock:
                pre_phase_head = self._l1._base_head()
            report.pre_phase_head = pre_phase_head
            self._fill_slots(executor, active)
            # The loop also stays alive while a migration is draining/running, so
            # an exclusive window that begins after the last agent completes still
            # gets its drained tick (PI-133).
            while active or migration_outstanding():
                if cfg.manage_api and self.api is not None:
                    self.api.ensure_alive()
                # PI-133: once the pool has drained to zero in-flight agents, run
                # any pending migration EXCLUSIVELY, then resume dispatch.
                if lock is not None and lock.maybe_run(len(active)) and not paused:
                    self._fill_slots(executor, active)
                try:
                    run = self._completed.get(timeout=cfg.poll_interval)
                except queue.Empty:
                    continue  # periodic wake — monitor the API + migration, re-wait
                task_report = self._integrate(run)
                report.task_reports.append(task_report)
                self.reports.append(task_report)
                active.discard(task_report.work_task_id)
                if task_report.outcome is not TaskOutcome.MERGED:
                    if not paused:
                        paused = True
                        report.paused = True
                        report.pause_reason = (
                            f"{task_report.work_task_id}: "
                            f"{task_report.outcome.value}"
                        )
                    self.log(
                        f"⏸ pausing new dispatch ({report.pause_reason}); "
                        f"draining {len(active)} in-flight"
                    )
                elif not paused:
                    self._fill_slots(executor, active)
        finally:
            executor.shutdown(wait=True)
            if cfg.manage_api and self.api is not None:
                self.api.stop()
            # PI-145: phase-level atomicity. After every worker is quiesced (so no
            # `_merge` can race the reset), if ANY task in the phase failed
            # (a merge CONFLICT or a VERIFY_FAILED), undo every sibling merge by
            # hard-resetting base_branch to the captured anchor — leaving main
            # either whole or untouched, never partial. The owning Workstream was
            # already flagged needs_attention per-failure in `_integrate`; the
            # rollback only restores main. An empty drain (no task_reports) has
            # nothing to undo and never used pre_phase_head.
            phase_failed = any(
                r.outcome is not TaskOutcome.MERGED for r in report.task_reports
            )
            if phase_failed and report.task_reports:
                with self._repo_lock:
                    self._l1._reset_base_to(pre_phase_head)
                report.rolled_back = True
                report.rolled_back_to = pre_phase_head
                self.log(
                    f"↩ phase rolled back: {cfg.base_branch} reset --hard "
                    f"{pre_phase_head[:8]} — undoing every sibling merge from this "
                    f"phase (a task failed; workstream flagged needs_attention)"
                )
        if lock is not None and lock.records:
            report.migrations = list(lock.records)
        return report


# --------------------------------------------------------------------------
# CLI — `crmbuilder-v2-scheduler-pool`
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """``crmbuilder-v2-scheduler-pool`` — run the Layer-2 parallel pool."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-scheduler-pool",
        description="Coordinating runtime, Layer 2: capped concurrency-safe "
        "parallel spawn / verify / merge-as-complete.",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8765")
    parser.add_argument("--engagement", default="CRMBUILDER")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--base-branch",
        default="main",
        help="worktrees fork from this ref and merges land here (default: main)",
    )
    parser.add_argument("--tier", default=dispatcher._DEFAULT_TIER)
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=2,
        help="maximum agents running at once (the concurrency cap, REQ-055)",
    )
    parser.add_argument(
        "--work-task",
        action="append",
        dest="work_tasks",
        default=None,
        help="run only this Work Task (repeatable for an explicit set)",
    )
    parser.add_argument(
        "--workstream", default=None, help="run only this Workstream's Work Tasks"
    )
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument(
        "--manage-api",
        action="store_true",
        help="the runtime owns the API process (start/monitor/restart-on-crash)",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    config = ParallelSchedulerConfig(
        api_base=args.api_base,
        engagement=args.engagement,
        repo_root=args.repo_root,
        base_branch=args.base_branch,
        tier=args.tier,
        max_concurrent=args.max_concurrent,
        target_work_tasks=args.work_tasks,
        target_workstream=args.workstream,
        agent_timeout=args.agent_timeout,
        poll_interval=args.poll_interval,
        manage_api=args.manage_api,
    )
    runtime = ParallelCoordinatingScheduler(config=config)
    report = runtime.run()
    merged = len(report.merged)
    print(
        f"\npool run complete: {len(report.task_reports)} task(s), {merged} merged."
        + (f" PAUSED: {report.pause_reason}" if report.paused else "")
    )
    return 0 if not report.paused else 1


if __name__ == "__main__":
    raise SystemExit(main())
