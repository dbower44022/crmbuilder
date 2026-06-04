"""Coordinating runtime — Layer 2 (concurrency-safe parallel execution).

Layer 1 (:mod:`.coordinating_runtime`) closed the loop: it actually spawns a
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
:class:`~.coordinating_runtime.Worktree`, :func:`~.coordinating_runtime.spawn_claude_agent`,
:func:`~.coordinating_runtime.verify_result`, :func:`~.coordinating_runtime.interpret_merge`,
and the I/O helpers on :class:`~.coordinating_runtime.CoordinatingRuntime`
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

from crmbuilder_v2.runtime import dispatcher
from crmbuilder_v2.runtime.coordinating_runtime import (
    CoordinatingRuntime,
    MergeResult,
    MergeStatus,
    RuntimeConfig,
    VerifyOutcome,
    Worktree,
    _ResolvedAssignment,
    spawn_claude_agent,
    verify_result,
)

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
    verify: VerifyOutcome | None = None
    merge: MergeResult | None = None
    agent_returncode: int | None = None
    spawned_at: float | None = None
    finished_at: float | None = None
    merged_at: float | None = None


@dataclass
class PoolRunReport:
    """The result of one parallel run: every task's report + the pause state."""

    task_reports: list[TaskReport] = field(default_factory=list)
    paused: bool = False
    pause_reason: str | None = None

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
class ParallelRuntimeConfig(RuntimeConfig):
    """Layer-2 wiring: Layer-1 config + the concurrency cap and API ownership."""

    max_concurrent: int = 2
    manage_api: bool = False
    poll_interval: float = 1.0
    # Run only this explicit set of Work Tasks (the most precise demo control);
    # falls back to ``target_workstream`` / next-eligible-globally when None.
    target_work_tasks: list[str] | None = None


# Type alias for the injectable spawn seam.
SpawnFn = Callable[[str, str], subprocess.CompletedProcess]


@dataclass
class ParallelCoordinatingRuntime:
    """The Layer-2 concurrency-safe parallel pool (DEC-397).

    Composition over inheritance: a Layer-1 :class:`CoordinatingRuntime` is held
    as ``_l1`` and its I/O helpers (assignment resolution, merge, flag,
    owning-workstream lookup) are reused, so this class only adds the pool
    orchestration — slot filling, parallel spawn, completion-ordered merging,
    and API-process ownership.
    """

    config: ParallelRuntimeConfig
    spawn_fn: SpawnFn | None = None
    log: Callable[[str], None] = print
    reports: list[TaskReport] = field(default_factory=list)
    api: ApiProcess | None = None

    def __post_init__(self) -> None:
        # The Layer-1 runtime provides the proven per-task I/O unit. Its spawn
        # is unused here (we drive spawns from the pool), but it carries the
        # assignment/merge/flag helpers keyed off the same config.
        self._l1 = CoordinatingRuntime(
            config=self.config, spawn_fn=None, log=self.log
        )
        self._repo_lock = threading.Lock()
        self._completed: queue.Queue[_AgentRun] = queue.Queue()
        if self.config.manage_api and self.api is None:
            self.api = ApiProcess(
                api_base=self.config.api_base,
                engagement=self.config.engagement,
                log=self.log,
            )

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
                if dispatcher.is_work_task_eligible(wt, blockers):
                    out.append(tid)
            return out
        eligible = dispatcher.eligible_work_tasks(cfg.api_base, cfg.engagement)
        if cfg.target_workstream is not None:
            members = self._l1._workstream_members(cfg.target_workstream)
            eligible = [
                w for w in eligible if w["work_task_identifier"] in members
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
    def _worker(self, assignment: _ResolvedAssignment) -> None:
        cfg = self.config
        spawned_at = time.time()
        # Git worktree metadata mutations are serialized; the long agent spawn
        # is NOT — that is where the real parallelism lives.
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
        self._completed.put(
            _AgentRun(
                assignment=assignment,
                worktree=worktree,
                returncode=returncode,
                refreshed_task=refreshed,
                has_commits=has_commits,
                spawned_at=spawned_at,
                finished_at=finished_at,
            )
        )

    # --- integrate one completed agent (main thread, serialized) --------
    def _integrate(self, run: _AgentRun) -> TaskReport:
        a = run.assignment
        verdict = verify_result(run.refreshed_task, run.has_commits)
        self.log(
            f"  [{a.work_task_id}] verify: {verdict.value} "
            f"(branch_has_commits={run.has_commits})"
        )
        if verdict is not VerifyOutcome.OK:
            self._l1._flag_needs_attention(
                a.work_task_id,
                f"verification failed: {verdict.value} (agent rc={run.returncode})",
            )
            self._record_finding(
                a.work_task_id, f"verification failed: {verdict.value}"
            )
            run.worktree.remove()
            return TaskReport(
                work_task_id=a.work_task_id,
                branch=a.branch,
                outcome=TaskOutcome.VERIFY_FAILED,
                verify=verdict,
                agent_returncode=run.returncode,
                spawned_at=run.spawned_at,
                finished_at=run.finished_at,
            )
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
            return TaskReport(
                work_task_id=a.work_task_id,
                branch=a.branch,
                outcome=TaskOutcome.MERGE_CONFLICT,
                verify=verdict,
                merge=merge,
                spawned_at=run.spawned_at,
                finished_at=run.finished_at,
            )
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
        executor = ThreadPoolExecutor(max_workers=cfg.max_concurrent)
        active: set[str] = set()
        report = PoolRunReport()
        paused = False
        try:
            if cfg.manage_api and self.api is not None:
                self.api.ensure_started()
            self._fill_slots(executor, active)
            while active:
                if cfg.manage_api and self.api is not None:
                    self.api.ensure_alive()
                try:
                    run = self._completed.get(timeout=cfg.poll_interval)
                except queue.Empty:
                    continue  # periodic wake — monitor the API, then re-wait
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
        return report


# --------------------------------------------------------------------------
# CLI — `crmbuilder-v2-runtime-pool`
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """``crmbuilder-v2-runtime-pool`` — run the Layer-2 parallel pool."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-runtime-pool",
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

    config = ParallelRuntimeConfig(
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
    runtime = ParallelCoordinatingRuntime(config=config)
    report = runtime.run()
    merged = len(report.merged)
    print(
        f"\npool run complete: {len(report.task_reports)} task(s), {merged} merged."
        + (f" PAUSED: {report.pause_reason}" if report.paused else "")
    )
    return 0 if not report.paused else 1


if __name__ == "__main__":
    raise SystemExit(main())
