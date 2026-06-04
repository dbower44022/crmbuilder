"""Coordinating runtime — Layer 1 (serial spawn / verify / merge).

This is the capability the earlier "dispatcher" never had. The dispatcher
(:mod:`.dispatcher`) finds the next eligible Work Task and resolves the agent's
contract, but it stops there — it only *prints* a prompt. This module closes the
loop per **DEC-395**: it actually **spawns** a Claude Code agent in a fresh git
worktree, **waits** for it, **verifies** the result, **merges** the work back,
marks the task Complete, and **pauses for a human** at the gated points.

Layer 1 is **serial** — one agent at a time. Concurrency (many agents, a
concurrency cap, an exclusive migration lock, parallel worktrees) is **Layer 2**
and is deliberately *not* built here (DEC-395).

The loop, once per iteration:

1. find the next ready Work Task — ``Ready``, unclaimed, every ``blocked_by``
   predecessor ``Complete`` (reuses :func:`.dispatcher.next_assignment`,
   optionally narrowed to a target Work Task or Workstream so a demo run does not
   grab another session's real work);
2. resolve that ``(area, tier)`` agent's contract from the registry (reuses
   :func:`.agent_runtime.build_agent_prompt`), falling back to a minimal built-in
   contract when the registry has no matching profile;
3. **spawn one Claude Code agent** in a fresh git worktree taken from the base
   branch HEAD, with the resolved contract (plus the operating protocol) as its
   prompt — the agent claims the Work Task, does it, commits, drives it to
   ``Complete``, and exits;
4. **wait** for the agent, then **verify**: the Work Task is ``Complete`` and its
   branch carries commits;
5. **merge** the worktree's branch back into the base branch;
6. mark the step done and move to the next ready Work Task;
7. **pause for a human** (``needs_attention``) at the gated points — a failed
   verify, a merge conflict, or a Work Task already flagged.

The pure decision helpers (eligibility delegated to the dispatcher; verification,
the merge-outcome reading, and the pause decision here) are separated from the
git/subprocess/HTTP I/O so they are unit-testable without a server, a worktree,
or a spawned agent.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from crmbuilder_v2.runtime import dispatcher
from crmbuilder_v2.runtime.agent_runtime import AgentInvocation, build_agent_prompt

# --------------------------------------------------------------------------
# Outcomes (small enums + records the loop and its tests reason over)
# --------------------------------------------------------------------------


class VerifyOutcome(str, Enum):
    """The result of checking an agent's work before advancing (REQ-057)."""

    OK = "ok"  # Work Task Complete + branch carries commits → safe to merge
    NOT_COMPLETE = "not_complete"  # agent exited without driving the task Complete
    NO_COMMITS = "no_commits"  # task marked Complete but the branch is empty


class StepResult(str, Enum):
    """What happened to one Work Task this iteration."""

    MERGED = "merged"  # verified + merged + marked Complete
    PAUSED = "paused"  # stopped for a human (needs_attention gate)
    DRAINED = "drained"  # no eligible work remained


class MergeStatus(str, Enum):
    CLEAN = "clean"
    CONFLICT = "conflict"


@dataclass
class MergeResult:
    status: MergeStatus
    detail: str = ""


@dataclass
class IterationReport:
    """A human- and test-readable record of one loop iteration."""

    result: StepResult
    work_task_id: str | None = None
    verify: VerifyOutcome | None = None
    merge: MergeResult | None = None
    pause_reason: str | None = None
    agent_returncode: int | None = None
    branch: str | None = None


# --------------------------------------------------------------------------
# Pure decision helpers (no I/O — unit-tested directly)
# --------------------------------------------------------------------------


def verify_result(work_task: dict, branch_has_commits: bool) -> VerifyOutcome:
    """Decide whether an agent's finished work is safe to advance (REQ-057).

    A result is ``OK`` only when the agent drove the Work Task to ``Complete``
    *and* left commits on its branch. A task that is not ``Complete`` is sent
    back (``NOT_COMPLETE``); a task marked ``Complete`` with an empty branch is
    suspect and held (``NO_COMMITS``) rather than merged.
    """
    if work_task.get("work_task_status") != dispatcher._COMPLETE_STATUS:
        return VerifyOutcome.NOT_COMPLETE
    if not branch_has_commits:
        return VerifyOutcome.NO_COMMITS
    return VerifyOutcome.OK


def pause_reason_for(
    work_task: dict, workstream: dict | None = None
) -> str | None:
    """Return a human-judgment pause reason, or ``None`` to proceed (REQ-058).

    The scheduler is not fully autonomous: it stops for a person whenever the
    Work Task — or its owning Workstream — is flagged ``needs_attention``.
    (Approving an enforced-rule change and settling an unresolvable conflict are
    the other reserved points; in Layer 1 they surface as the same flag.)
    """
    if work_task.get("work_task_needs_attention"):
        return (
            work_task.get("work_task_needs_attention_reason")
            or "Work Task flagged needs_attention"
        )
    if workstream and workstream.get("workstream_needs_attention"):
        return (
            workstream.get("workstream_needs_attention_reason")
            or "Workstream flagged needs_attention"
        )
    return None


def interpret_merge(returncode: int, output: str) -> MergeResult:
    """Read a ``git merge`` invocation into a clean/conflict outcome.

    A non-zero exit with conflict markers in the output is a merge conflict —
    recorded as a finding and surfaced to a human, never force-resolved (REQ-056).
    """
    if returncode == 0:
        return MergeResult(MergeStatus.CLEAN, output.strip())
    lowered = output.lower()
    if "conflict" in lowered or "automatic merge failed" in lowered:
        return MergeResult(MergeStatus.CONFLICT, output.strip())
    return MergeResult(MergeStatus.CONFLICT, output.strip() or "merge failed")


# --------------------------------------------------------------------------
# The operating protocol injected on top of the resolved contract
# --------------------------------------------------------------------------


def operating_protocol(
    *, work_task_id: str, area: str, api_base: str, engagement: str, branch: str
) -> str:
    """The runtime's per-spawn operating instructions, appended to the contract.

    The registry contract says *what kind of agent* this is and what it knows;
    this block says *exactly how to operate* within the runtime: claim the task,
    do the work in this worktree, commit, and drive the task to ``Complete`` —
    the lifecycle the runtime verifies afterward.
    """
    return (
        "### How to operate (coordinating runtime, Layer 1)\n"
        "You are running non-interactively in a dedicated git worktree on branch "
        f"`{branch}`. The live V2 API is at `{api_base}` and EVERY request must "
        f"send the header `X-Engagement: {engagement}`. Do exactly this and then "
        "exit:\n"
        f"1. Claim your Work Task:\n"
        f"   `curl -s -X POST -H 'X-Engagement: {engagement}' -H 'Content-Type: application/json' "
        f"{api_base}/work-tasks/{work_task_id}/claim -d '{{\"claimed_by\": \"AGP-runtime\"}}'`\n"
        f"   then move it to In Progress:\n"
        f"   `curl -s -X PATCH -H 'X-Engagement: {engagement}' -H 'Content-Type: application/json' "
        f"{api_base}/work-tasks/{work_task_id} -d '{{\"work_task_status\": \"In Progress\"}}'`\n"
        "2. Do the work the Work Task describes, here in this worktree.\n"
        "3. Commit your changes with git (a clear message naming the Work Task). "
        "Do NOT push and do NOT merge — the runtime merges your branch.\n"
        f"4. Mark the Work Task Complete:\n"
        f"   `curl -s -X PATCH -H 'X-Engagement: {engagement}' -H 'Content-Type: application/json' "
        f"{api_base}/work-tasks/{work_task_id} -d '{{\"work_task_status\": \"Complete\"}}'`\n"
        "5. Exit. The runtime will verify (task Complete + your branch carries "
        "commits) and merge your branch back."
    )


_MINIMAL_TIER = dispatcher._DEFAULT_TIER


def minimal_contract_prompt(work_task: dict, *, area: str) -> str:
    """A built-in contract used when the registry resolves no matching profile.

    Keeps Layer 1 runnable end-to-end without depending on the registry being
    seeded; when a profile *does* exist, the resolved registry contract is used
    instead (REQ-054). The operating protocol is appended by the caller.
    """
    return (
        f"You are an Area Specialist for the `{area}` area. You have been given "
        "exactly one Work Task to complete.\n\n"
        "### Your assigned Work Task\n"
        f"- identifier: {work_task['work_task_identifier']}\n"
        f"- area: {area}\n"
        f"- title: {work_task['work_task_title']}\n"
        f"- description: {work_task.get('work_task_description') or '(none)'}"
    )


# --------------------------------------------------------------------------
# Git worktree + agent-spawn I/O (injectable for tests)
# --------------------------------------------------------------------------


def _git(repo_root: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", repo_root, *args],
        capture_output=True,
        text=True,
        check=check,
    )


@dataclass
class Worktree:
    """A throwaway git worktree on its own branch, taken from a base ref."""

    repo_root: str
    branch: str
    base_ref: str
    path: str = ""

    def create(self) -> str:
        self.path = tempfile.mkdtemp(prefix=f"ado-{self.branch.replace('/', '-')}-")
        # Remove a stale branch of the same name so re-runs are clean.
        _git(self.repo_root, "branch", "-D", self.branch, check=False)
        _git(
            self.repo_root,
            "worktree",
            "add",
            "-b",
            self.branch,
            self.path,
            self.base_ref,
        )
        return self.path

    def head(self) -> str:
        return _git(self.path, "rev-parse", "HEAD").stdout.strip()

    def has_commits_beyond(self, base_ref: str) -> bool:
        out = _git(self.path, "rev-list", "--count", f"{base_ref}..HEAD").stdout.strip()
        try:
            return int(out) > 0
        except ValueError:
            return False

    def remove(self) -> None:
        if self.path:
            _git(self.repo_root, "worktree", "remove", "--force", self.path, check=False)
            shutil.rmtree(self.path, ignore_errors=True)
            self.path = ""


def spawn_claude_agent(
    prompt: str, worktree_path: str, *, timeout: int = 1800
) -> subprocess.CompletedProcess:
    """Spawn one real Claude Code agent in ``worktree_path`` with ``prompt``.

    Non-interactive (``-p``), permissions bypassed so it can use Bash/Write
    without prompting, scoped to the worktree. The agent boots from the contract
    + operating protocol, does the task, and exits.
    """
    return subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "bypassPermissions",
            "--add-dir",
            worktree_path,
        ],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# Type aliases for the injectable seams the loop uses.
SpawnFn = Callable[[str, str], subprocess.CompletedProcess]


# --------------------------------------------------------------------------
# Configuration + the loop
# --------------------------------------------------------------------------


@dataclass
class RuntimeConfig:
    """How a coordinating-runtime run is wired."""

    api_base: str = "http://127.0.0.1:8765"
    engagement: str = "CRMBUILDER"
    repo_root: str = "."
    # Worktrees fork from this ref and merges land here. Default ``main``
    # (DEC-395). A demo run points it at a throwaway integration branch so it
    # never pollutes ``main``.
    base_branch: str = "main"
    tier: str = dispatcher._DEFAULT_TIER
    # Narrow the run to one Work Task or one Workstream so a demo does not grab
    # another session's real work. ``None`` means "next eligible globally".
    target_work_task: str | None = None
    target_workstream: str | None = None
    max_iterations: int = 1
    agent_timeout: int = 1800
    dry_run: bool = False  # resolve + report, never spawn/merge


@dataclass
class CoordinatingRuntime:
    """The Layer-1 serial control loop (DEC-395)."""

    config: RuntimeConfig
    spawn_fn: SpawnFn | None = None
    log: Callable[[str], None] = print
    reports: list[IterationReport] = field(default_factory=list)

    # --- assignment selection (delegates eligibility to the dispatcher) ---
    def _next_assignment(self):
        cfg = self.config
        if cfg.target_work_task is not None:
            return self._assignment_for(cfg.target_work_task)
        eligible = dispatcher.eligible_work_tasks(cfg.api_base, cfg.engagement)
        if cfg.target_workstream is not None:
            members = self._workstream_members(cfg.target_workstream)
            eligible = [w for w in eligible if w["work_task_identifier"] in members]
        if not eligible:
            return None
        return self._assignment_for(eligible[0]["work_task_identifier"])

    def _assignment_for(self, work_task_id: str):
        """Resolve a specific Work Task into a ready-to-spawn assignment.

        Eligibility is re-checked for an explicit target; the contract is the
        registry contract when a profile exists, else the built-in fallback.
        """
        cfg = self.config
        wt = dispatcher._get(cfg.api_base, f"/work-tasks/{work_task_id}", cfg.engagement)
        blockers = dispatcher._blocker_statuses(cfg.api_base, cfg.engagement, work_task_id)
        if not dispatcher.is_work_task_eligible(wt, blockers):
            return None
        area = wt["work_task_area"]
        profiles = dispatcher._get(cfg.api_base, "/agent-profiles", cfg.engagement)
        profile_id = dispatcher.select_profile_id(profiles, area, cfg.tier)
        branch = f"ado/{work_task_id.lower()}"
        if profile_id is not None:
            invocation = build_agent_prompt(
                cfg.api_base, cfg.engagement, profile_id, work_task_id
            )
            base_prompt = invocation.system_prompt
        else:
            profile_id = "AGP-runtime"  # built-in fallback identity
            base_prompt = minimal_contract_prompt(wt, area=area)
        protocol = operating_protocol(
            work_task_id=work_task_id,
            area=area,
            api_base=cfg.api_base,
            engagement=cfg.engagement,
            branch=branch,
        )
        return _ResolvedAssignment(
            work_task=wt,
            work_task_id=work_task_id,
            area=area,
            profile_id=profile_id,
            branch=branch,
            prompt=f"{base_prompt}\n\n{protocol}",
        )

    def _workstream_members(self, workstream_id: str) -> set[str]:
        cfg = self.config
        edges = dispatcher._get(
            cfg.api_base,
            "/references?"
            + urllib.parse.urlencode(
                {
                    "target_id": workstream_id,
                    "relationship": "work_task_belongs_to_workstream",
                }
            ),
            cfg.engagement,
        )
        return {e["source_id"] for e in edges if e.get("source_type") == "work_task"}

    # --- one iteration: spawn → verify → merge / pause -------------------
    def run_one(self) -> IterationReport:
        cfg = self.config
        assignment = self._next_assignment()
        if assignment is None:
            self.log("· no eligible work — loop drained")
            return IterationReport(result=StepResult.DRAINED)

        # Gate: an already-flagged task pauses before we spend an agent on it.
        workstream = self._owning_workstream(assignment.work_task_id)
        reason = pause_reason_for(assignment.work_task, workstream)
        if reason:
            self.log(f"⏸ pausing for a human on {assignment.work_task_id}: {reason}")
            return IterationReport(
                result=StepResult.PAUSED,
                work_task_id=assignment.work_task_id,
                pause_reason=reason,
            )

        self.log(
            f"▶ dispatching {assignment.work_task_id} (area={assignment.area}, "
            f"profile={assignment.profile_id}) → worktree branch {assignment.branch}"
        )
        if cfg.dry_run:
            self.log("  (dry-run) resolved contract; not spawning")
            return IterationReport(
                result=StepResult.PAUSED,
                work_task_id=assignment.work_task_id,
                branch=assignment.branch,
                pause_reason="dry-run",
            )

        worktree = Worktree(
            repo_root=cfg.repo_root,
            branch=assignment.branch,
            base_ref=cfg.base_branch,
        )
        worktree.create()
        try:
            self.log(f"  spawning agent in {worktree.path} …")
            spawn = self.spawn_fn or (
                lambda p, wp: spawn_claude_agent(p, wp, timeout=cfg.agent_timeout)
            )
            # The runtime verifies by *result* (DB state + git), not by the
            # agent's exit. An agent that finished its work but did not cleanly
            # self-terminate is killed at the deadline; we still verify, and a
            # completed-and-committed result merges anyway (DEC: verify-by-result).
            returncode: int | None = None
            try:
                proc = spawn(assignment.prompt, worktree.path)
                returncode = proc.returncode
                self.log(f"  agent exited rc={returncode}")
            except subprocess.TimeoutExpired:
                self.log(
                    f"  agent hit the {cfg.agent_timeout}s deadline and was "
                    "killed — verifying by result anyway"
                )

            # Verify (REQ-057): re-read the task + check the branch.
            refreshed = dispatcher._get(
                cfg.api_base, f"/work-tasks/{assignment.work_task_id}", cfg.engagement
            )
            has_commits = worktree.has_commits_beyond(cfg.base_branch)
            verdict = verify_result(refreshed, has_commits)
            self.log(f"  verify: {verdict.value} (branch_has_commits={has_commits})")

            if verdict is not VerifyOutcome.OK:
                self._flag_needs_attention(
                    assignment.work_task_id,
                    f"verification failed: {verdict.value} "
                    f"(agent rc={returncode})",
                )
                return IterationReport(
                    result=StepResult.PAUSED,
                    work_task_id=assignment.work_task_id,
                    verify=verdict,
                    agent_returncode=returncode,
                    branch=assignment.branch,
                    pause_reason=f"verification {verdict.value}",
                )

            # Merge (REQ-056): land the agent's branch on the base branch.
            merge = self._merge(assignment.branch)
            self.log(f"  merge: {merge.status.value}")
            if merge.status is MergeStatus.CONFLICT:
                self._flag_needs_attention(
                    assignment.work_task_id,
                    f"merge conflict on {assignment.branch}: {merge.detail[:200]}",
                )
                return IterationReport(
                    result=StepResult.PAUSED,
                    work_task_id=assignment.work_task_id,
                    verify=verdict,
                    merge=merge,
                    branch=assignment.branch,
                    pause_reason="merge conflict",
                )

            self.log(
                f"✔ {assignment.work_task_id} verified + merged into {cfg.base_branch}"
            )
            return IterationReport(
                result=StepResult.MERGED,
                work_task_id=assignment.work_task_id,
                verify=verdict,
                merge=merge,
                agent_returncode=returncode,
                branch=assignment.branch,
            )
        finally:
            worktree.remove()

    def run(self) -> list[IterationReport]:
        """Drive the serial loop up to ``max_iterations`` or until drained/paused."""
        cfg = self.config
        for i in range(cfg.max_iterations):
            self.log(f"── iteration {i + 1}/{cfg.max_iterations} ──")
            report = self.run_one()
            self.reports.append(report)
            if report.result in (StepResult.DRAINED, StepResult.PAUSED):
                break
        return self.reports

    # --- small I/O helpers ----------------------------------------------
    def _owning_workstream(self, work_task_id: str) -> dict | None:
        cfg = self.config
        edges = dispatcher._get(
            cfg.api_base,
            "/references?"
            + urllib.parse.urlencode(
                {
                    "source_id": work_task_id,
                    "relationship": "work_task_belongs_to_workstream",
                }
            ),
            cfg.engagement,
        )
        for e in edges:
            if e.get("target_type") == "workstream":
                return dispatcher._get(
                    cfg.api_base, f"/workstreams/{e['target_id']}", cfg.engagement
                )
        return None

    def _flag_needs_attention(self, work_task_id: str, reason: str) -> None:
        cfg = self.config
        try:
            dispatcher._patch(
                cfg.api_base,
                f"/work-tasks/{work_task_id}",
                cfg.engagement,
                {
                    "work_task_needs_attention": True,
                    "work_task_needs_attention_reason": reason,
                },
            )
        except Exception as exc:  # best-effort flag; never mask the real outcome
            self.log(f"  (warning) could not flag needs_attention: {exc}")

    def _merge(self, branch: str) -> MergeResult:
        cfg = self.config
        _git(cfg.repo_root, "checkout", cfg.base_branch)
        proc = _git(
            cfg.repo_root,
            "merge",
            "--no-ff",
            branch,
            "-m",
            f"ado: merge {branch} (coordinating runtime)",
            check=False,
        )
        result = interpret_merge(proc.returncode, proc.stdout + proc.stderr)
        if result.status is MergeStatus.CONFLICT:
            _git(cfg.repo_root, "merge", "--abort", check=False)
        return result


@dataclass
class _ResolvedAssignment:
    work_task: dict
    work_task_id: str
    area: str
    profile_id: str
    branch: str
    prompt: str


# --------------------------------------------------------------------------
# Registry seed helper — make the contract-resolution path real for a demo
# --------------------------------------------------------------------------


def seed_minimal_profile(
    api_base: str, engagement: str, *, area: str, tier: str = _MINIMAL_TIER
) -> str:
    """Seed (idempotently) a minimal system Area-Specialist agent profile.

    The registry composes a profile's ``description`` into the resolved
    contract's ``system_prompt``. Seeding one system profile for ``(area, tier)``
    means the runtime exercises the genuine registry contract path (REQ-054)
    rather than only the built-in fallback. Returns the profile identifier.
    """
    existing = dispatcher._get(api_base, "/agent-profiles", engagement)
    for p in existing:
        if (
            p.get("scope") == "system"
            and p.get("area") == area
            and p.get("tier") == tier
        ):
            return p["identifier"]
    created = dispatcher._post(
        api_base,
        "/agent-profiles",
        engagement,
        {
            "area": area,
            "tier": tier,
            "scope": "system",
            "description": (
                f"You are an Area Specialist for the `{area}` area, spawned by the "
                "coordinating runtime to complete exactly one Work Task. Read your "
                "Work Task, do precisely what it describes (no more), and verify "
                "your own work before completing it."
            ),
        },
    )
    return created["identifier"]


# --------------------------------------------------------------------------
# CLI — `crmbuilder-v2-runtime`
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """``crmbuilder-v2-runtime`` — run the Layer-1 serial coordinating loop."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-runtime",
        description="Coordinating runtime, Layer 1: serial spawn / verify / merge.",
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8765")
    parser.add_argument("--engagement", default="CRMBUILDER")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--base-branch",
        default="main",
        help="worktrees fork from this ref and merges land here (default: main)",
    )
    parser.add_argument("--tier", default=_MINIMAL_TIER)
    parser.add_argument("--work-task", default=None, help="run only this Work Task")
    parser.add_argument(
        "--workstream", default=None, help="run only this Workstream's Work Tasks"
    )
    parser.add_argument("--max-iterations", type=int, default=1)
    parser.add_argument("--agent-timeout", type=int, default=1800)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve the assignment + contract and report; do not spawn or merge",
    )
    parser.add_argument(
        "--seed-profile",
        metavar="AREA",
        default=None,
        help="seed a minimal system profile for AREA, then exit",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.seed_profile:
        pid = seed_minimal_profile(
            args.api_base, args.engagement, area=args.seed_profile, tier=args.tier
        )
        print(f"seeded/found profile {pid} for ({args.seed_profile}, {args.tier})")
        return 0

    config = RuntimeConfig(
        api_base=args.api_base,
        engagement=args.engagement,
        repo_root=args.repo_root,
        base_branch=args.base_branch,
        tier=args.tier,
        target_work_task=args.work_task,
        target_workstream=args.workstream,
        max_iterations=args.max_iterations,
        agent_timeout=args.agent_timeout,
        dry_run=args.dry_run,
    )
    runtime = CoordinatingRuntime(config=config)
    reports = runtime.run()
    merged = sum(1 for r in reports if r.result is StepResult.MERGED)
    print(
        f"\nrun complete: {len(reports)} iteration(s), {merged} merged. "
        f"Last: {reports[-1].result.value if reports else 'none'}"
    )
    # Exit non-zero if the loop paused for a human (so a wrapper can notice).
    return 0 if reports and reports[-1].result is not StepResult.PAUSED else 1


if __name__ == "__main__":
    raise SystemExit(main())
