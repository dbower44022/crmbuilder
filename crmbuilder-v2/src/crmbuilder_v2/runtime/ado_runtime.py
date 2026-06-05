"""ADO orchestration driver — the PI-level scheduler (PI-143, slices 1–2).

The L1/L2 runtime (:mod:`coordinating_runtime`, :mod:`parallel_runtime`) drives
the *bottom* half of the delivery loop: it finds a ``Ready`` Work Task, spawns an
agent, verifies by result, and merges. It does not drive the *top* half — turning
a dispatched Planning Item into ``Ready`` Work Tasks and advancing it phase by
phase. That orchestration was hand-operated endpoint by endpoint.

This module is the deterministic outer loop that closes that gap by *composing*
the already-built substrate with the already-built execution pool:

    dispatch (PM) → decompose → for each phase in serial order:
        scope (Architect) → start_phase (Lead) → run the pool → complete_phase
    → advance the Planning Item to ``In Review``

**Slice 1** drove a pre-scoped PI (scoping supplied). **Slice 2 (this build) adds
the judgment**: for each ``Planned`` phase the driver spawns an Architect agent
that *decides* and creates the phase's Work Tasks (:func:`scope_phase_agent`,
verified by result — the phase reaching ``Ready`` / ``Not Applicable``), and before
a ``Develop`` phase it clears the reconciliation gate (:func:`develop_gate_open`,
reusing :mod:`reconciliation`) so no building begins while an open *blocking*
finding holds the Design (REQ-027/033). PM auto-dispatch from the project backlog
is slice 3.

Like the rest of the runtime, the **decision** (:func:`decide_next`) is a pure
function of the PI's recorded state, separated from the HTTP / pool / agent I/O, so
the loop is unit-testable without a server, a worktree, or a real agent. The driver
is DB-backed-stateless: every iteration re-reads ``phase-overview`` and continues
from wherever the records say things stand, so it is fully resumable (§4.4).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from . import dispatcher, reconciliation
from .parallel_runtime import (
    ParallelCoordinatingRuntime,
    ParallelRuntimeConfig,
    PoolRunReport,
)
from .reconciliation import GateDecision

_DEVELOP_PHASE = "Develop"
_TERMINAL_PHASE = frozenset({"Complete", "Not Applicable"})

# A PI in one of these statuses can still be dispatched (handed to a Lead).
_STARTABLE = frozenset({"Draft", "Decomposed", "Ready"})
# Where the driver parks a PI once every phase is terminal: execution is done,
# final Resolved is a governance closure act (the resolves edge), not the
# driver's call.
_DONE_STATUS = "In Review"


# --------------------------------------------------------------------------
# Pure decision — the heart, unit-testable with no I/O
# --------------------------------------------------------------------------


class StepKind(str, Enum):
    SCOPE = "scope"        # a Planned phase needs scoping (an Architect agent)
    START = "start"        # start + execute this Ready phase Workstream
    DONE = "done"          # every phase terminal — advance the PI
    PAUSE = "pause"        # a phase needs a human (needs_attention)
    BLOCKED = "blocked"    # a phase is in an unexpected state mid-loop


@dataclass(frozen=True)
class AdoStep:
    kind: StepKind
    workstream: str | None = None
    phase_type: str | None = None
    reason: str | None = None


def decide_next(overview: dict) -> AdoStep:
    """Decide the next orchestration step from a ``phase-overview`` payload.

    Phases are delivered strictly serially, so the decision is the action owed to
    the *first non-terminal phase* (in canonical order). Precedence: a human
    ``needs_attention`` flag stops everything; then "all phases terminal" is done.
    Otherwise the first non-terminal phase drives the step — ``SCOPE`` it if it is
    still ``Planned`` (slice 2 spawns an Architect to create its Work Tasks),
    ``START`` it once it is ``Ready``. A phase whose predecessors are not terminal,
    or one sitting in a transient ``Scoping``/``In Progress`` state between
    iterations, is an unexpected state and surfaces as ``BLOCKED``.
    """
    attention = overview.get("needs_attention") or []
    if attention:
        return AdoStep(StepKind.PAUSE, reason=f"needs_attention on {attention}")
    if overview.get("all_terminal"):
        return AdoStep(StepKind.DONE)

    phases = overview.get("phases") or []
    if not phases:
        return AdoStep(StepKind.BLOCKED, reason="planning item is not decomposed")

    for p in phases:
        if p["status"] in _TERMINAL_PHASE:
            continue
        wsid = p["workstream"]["workstream_identifier"]
        ptype = p.get("phase_type")
        if not p.get("predecessors_terminal", False):
            return AdoStep(
                StepKind.BLOCKED, workstream=wsid, phase_type=ptype,
                reason=f"phase {wsid} blocked by non-terminal predecessors "
                f"{p.get('blocked_by')}",
            )
        if p["status"] == "Planned":
            return AdoStep(StepKind.SCOPE, workstream=wsid, phase_type=ptype)
        if p["status"] == "Ready":
            return AdoStep(StepKind.START, workstream=wsid, phase_type=ptype)
        return AdoStep(
            StepKind.BLOCKED, workstream=wsid, phase_type=ptype,
            reason=f"phase {wsid} is {p['status']!r} (unexpected between iterations)",
        )

    return AdoStep(StepKind.DONE)


# --------------------------------------------------------------------------
# Config + report
# --------------------------------------------------------------------------


@dataclass
class AdoRuntimeConfig:
    planning_item: str
    api_base: str = "http://127.0.0.1:8765"
    engagement: str = "CRMBUILDER"
    repo_root: str = "."
    base_branch: str = "main"
    max_concurrent: int = 2
    tier: str = dispatcher._DEFAULT_TIER
    agent_timeout: int = 1800
    manage_api: bool = False
    dry_run: bool = False
    # Safety backstop against a non-advancing loop: at most this many phase
    # starts in one run (a PI has a small fixed number of phases).
    max_phases: int = 12
    log: Callable[[str], None] = print


@dataclass
class AdoRunReport:
    planning_item: str
    status: str = "incomplete"          # complete | paused | blocked | dry_run
    completed_phases: list[str] = field(default_factory=list)
    reason: str | None = None


# --------------------------------------------------------------------------
# Pool seam — patchable for tests (no real agents spawned under test)
# --------------------------------------------------------------------------


def run_pool_for_workstream(cfg: AdoRuntimeConfig, workstream_id: str) -> PoolRunReport:
    """Run the L2 parallel pool over exactly one phase Workstream's Work Tasks."""
    pool_cfg = ParallelRuntimeConfig(
        api_base=cfg.api_base,
        engagement=cfg.engagement,
        repo_root=cfg.repo_root,
        base_branch=cfg.base_branch,
        tier=cfg.tier,
        target_workstream=workstream_id,
        agent_timeout=cfg.agent_timeout,
        max_concurrent=cfg.max_concurrent,
        manage_api=cfg.manage_api,
        log=cfg.log,
    )
    return ParallelCoordinatingRuntime(config=pool_cfg).run()


# --------------------------------------------------------------------------
# Scoping-agent seam (slice 2) — patchable; spawns a real Architect under prod
# --------------------------------------------------------------------------


def build_scoping_prompt(cfg: AdoRuntimeConfig, workstream_id: str, phase_type: str) -> str:
    """The scoping agent's operating protocol.

    Unlike an execution agent it writes no code and needs no worktree — it reads
    the Planning Item and the prior phases' outputs, *decides* the Work Tasks this
    phase needs (one per area the phase touches), and records them in a single
    ``scope`` call (an empty list asserts the phase is Not Applicable, §4.3).
    """
    api = cfg.api_base
    eng = cfg.engagement
    h = f"-H 'X-Engagement: {eng}'"
    return (
        f"You are the {phase_type}-phase Architect for Planning Item "
        f"{cfg.planning_item}. Your one job: decide the Work Tasks the "
        f"{phase_type} phase (Workstream {workstream_id}) needs and record them. "
        f"You write NO code — you only decide and record. The live V2 API is at "
        f"{api} and EVERY request must send the header X-Engagement: {eng}.\n\n"
        f"Do exactly this:\n"
        f"1. Read the Planning Item — `curl -s {h} {api}/planning-items/"
        f"{cfg.planning_item}` — and its requirements/intent.\n"
        f"2. Read what earlier phases produced — `curl -s {h} {api}/workstreams/"
        f"{workstream_id}/prior-phase-outputs` — and build on them.\n"
        f"3. Decide the Work Tasks: one per area this phase touches, each a clear "
        f"single-area unit. Each needs a 'title' and an 'area' (a valid System or "
        f"Engagement area, e.g. storage, access, api, mcp, ui), plus an optional "
        f"'description'.\n"
        f"4. Record them in ONE call:\n"
        f"   `curl -s -X POST {h} -H 'Content-Type: application/json' "
        f"{api}/workstreams/{workstream_id}/scope "
        f"-d '{{\"work_tasks\": [{{\"title\": \"...\", \"area\": \"...\", "
        f"\"description\": \"...\"}}]}}'`\n"
        f"   If the phase genuinely needs no work, POST an empty list "
        f"(`{{\"work_tasks\": []}}`) — that asserts Not Applicable.\n"
        f"5. Confirm the Workstream is now 'Ready' (or 'Not Applicable') and exit."
    )


def spawn_scoping_agent(prompt: str, *, timeout: int = 1800):
    """Spawn one real Claude agent to scope a phase (no worktree — API writes only)."""
    import subprocess
    import tempfile

    workdir = tempfile.mkdtemp(prefix="ado-scope-")
    return subprocess.run(
        ["claude", "-p", prompt, "--permission-mode", "bypassPermissions",
         "--add-dir", workdir],
        cwd=workdir, capture_output=True, text=True, timeout=timeout,
    )


def scope_phase_agent(cfg: AdoRuntimeConfig, workstream_id: str, phase_type: str) -> None:
    """Default scope_runner: spawn an Architect to scope ``workstream_id``.

    Success is verified by the caller *by result* (the phase reaching ``Ready`` or
    ``Not Applicable``), not by this agent's exit — consistent with the runtime's
    verify-by-result rule (DEC-396).
    """
    prompt = build_scoping_prompt(cfg, workstream_id, phase_type)
    spawn_scoping_agent(prompt, timeout=cfg.agent_timeout)


# --------------------------------------------------------------------------
# Develop reconciliation-gate seam (slice 2) — proactive, phase-level
# --------------------------------------------------------------------------


def develop_gate_open(cfg: AdoRuntimeConfig, workstream_id: str) -> GateDecision:
    """Phase-level Develop-gate consult, reusing :mod:`reconciliation`.

    The pool already enforces the gate per Work Task at dispatch
    (``coordinating_runtime`` → ``reconciliation.develop_gate``); this lets the
    driver check it *before* running a futile pool and pause cleanly with a
    reconciliation reason. Reads one of the phase's Work Tasks and delegates to
    the same gate logic; a phase with no Work Tasks yet passes vacuously.
    """
    edges = dispatcher._get(
        cfg.api_base,
        f"/references?target_id={workstream_id}"
        "&relationship=work_task_belongs_to_workstream",
        cfg.engagement,
    )
    wt_ids = [e["source_id"] for e in edges] if isinstance(edges, list) else []
    if not wt_ids:
        return GateDecision(True, "no Work Tasks scoped yet")
    work_task = dispatcher._get(
        cfg.api_base, f"/work-tasks/{wt_ids[0]}", cfg.engagement
    )
    return reconciliation.develop_gate(cfg.api_base, cfg.engagement, work_task)


# --------------------------------------------------------------------------
# The driver
# --------------------------------------------------------------------------


@dataclass
class AdoRuntime:
    """Drives one Planning Item through its phases to ``In Review`` (or a pause)."""

    config: AdoRuntimeConfig
    # Injected for tests; defaults hit the live API / real pool / real agents.
    pool_runner: Callable[[AdoRuntimeConfig, str], PoolRunReport] = run_pool_for_workstream
    scope_runner: Callable[[AdoRuntimeConfig, str, str], None] = scope_phase_agent
    gate_checker: Callable[[AdoRuntimeConfig, str], GateDecision] = develop_gate_open

    def log(self, msg: str) -> None:
        self.config.log(msg)

    def _phase_status(self, workstream_id: str) -> str | None:
        for p in self._overview().get("phases", []):
            if p["workstream"]["workstream_identifier"] == workstream_id:
                return p["status"]
        return None

    # --- thin HTTP seams over the substrate endpoints -------------------

    def _get(self, path: str) -> object:
        return dispatcher._get(self.config.api_base, path, self.config.engagement)

    def _post(self, path: str, body: dict | None = None) -> object:
        return dispatcher._post(
            self.config.api_base, path, self.config.engagement, body or {}
        )

    def _pi(self) -> dict:
        return self._get(f"/planning-items/{self.config.planning_item}")  # type: ignore[return-value]

    def _overview(self) -> dict:
        return self._get(
            f"/planning-items/{self.config.planning_item}/phase-overview"
        )  # type: ignore[return-value]

    # --- the loop -------------------------------------------------------

    def run(self) -> AdoRunReport:
        cfg = self.config
        pi = cfg.planning_item
        report = AdoRunReport(planning_item=pi)

        # 1. ensure dispatched (idempotent: only a startable PI is dispatched).
        status = self._pi()["status"]
        if status in _STARTABLE:
            if cfg.dry_run:
                self.log(f"▶ would dispatch {pi} ({status} → In Progress)")
            else:
                self._post(f"/planning-items/{pi}/dispatch")
                self.log(f"▶ dispatched {pi} (→ In Progress)")

        # 2. ensure decomposed (idempotent: skip if phases already exist).
        if not self._overview().get("decomposed"):
            if cfg.dry_run:
                self.log(f"▶ would decompose {pi}")
            else:
                self._post(f"/planning-items/{pi}/decompose")
                self.log(f"▶ decomposed {pi} into phase Workstreams")

        if cfg.dry_run:
            ov = self._overview()
            step = decide_next(ov)
            self.log(f"dry-run: next step is {step.kind.value}"
                     + (f" ({step.workstream})" if step.workstream else "")
                     + (f" — {step.reason}" if step.reason else ""))
            report.status = "dry_run"
            report.reason = step.reason
            return report

        # 3. drive phases serially until done / paused / blocked. Each phase can
        # take two iterations (scope, then execute), so budget accordingly.
        for _ in range(cfg.max_phases * 2 + 1):
            ov = self._overview()
            step = decide_next(ov)

            if step.kind is StepKind.DONE:
                # advance the PI out of In Progress (execution complete).
                self._patch_pi_status(_DONE_STATUS)
                self.log(f"✔ {pi}: all phases terminal → {_DONE_STATUS}")
                report.status = "complete"
                return report

            if step.kind is StepKind.PAUSE:
                self.log(f"⏸ {pi}: paused — {step.reason}")
                report.status = "paused"
                report.reason = step.reason
                return report

            if step.kind is StepKind.BLOCKED:
                self.log(f"⏹ {pi}: blocked — {step.reason}")
                report.status = "blocked"
                report.reason = step.reason
                return report

            ws = step.workstream
            assert ws is not None

            # SCOPE: spawn an Architect to decide + create the phase's Work Tasks.
            if step.kind is StepKind.SCOPE:
                self.log(f"▶ {pi}: scoping phase {ws} ({step.phase_type}) "
                         f"— spawning Architect")
                self.scope_runner(cfg, ws, step.phase_type or "")
                after = self._phase_status(ws)  # verify by result
                if after not in ("Ready", "Not Applicable"):
                    report.status = "paused"
                    report.reason = (
                        f"scoping did not complete phase {ws} (still {after!r}); "
                        f"a person needs to scope it"
                    )
                    self.log(f"⏸ {pi}: {report.reason}")
                    return report
                self.log(f"  {ws} scoped → {after}")
                continue

            # START: a Develop phase first clears the reconciliation gate.
            if step.phase_type == _DEVELOP_PHASE:
                gate = self.gate_checker(cfg, ws)
                if not gate.allow:
                    report.status = "paused"
                    report.reason = (
                        f"Develop gate held on {ws}: {gate.reason} — reconcile the "
                        f"Design before building"
                    )
                    self.log(f"⏸ {pi}: {report.reason}")
                    return report

            # open the phase, run the pool over it, then complete it.
            self._post(f"/workstreams/{ws}/start-execution")
            self.log(f"▶ {pi}: started phase {ws} → running pool")

            pool_report = self.pool_runner(cfg, ws)
            if pool_report.paused:
                self.log(f"⏸ {pi}: execution paused in phase {ws}")
                report.status = "paused"
                report.reason = f"execution paused in {ws}"
                return report

            self._post(f"/workstreams/{ws}/complete-phase")
            self.log(f"✔ {pi}: phase {ws} complete "
                     f"({len(pool_report.merged)} task(s) merged)")
            report.completed_phases.append(ws)

        report.status = "blocked"
        report.reason = f"exceeded the phase budget ({cfg.max_phases}) without finishing"
        self.log(f"⚠ {pi}: {report.reason}")
        return report

    def _patch_pi_status(self, status: str) -> None:
        # The update endpoint is PATCH; dispatcher only has GET/POST, so go
        # through urllib directly with the same envelope/header contract.
        import json
        import urllib.request

        url = f"{self.config.api_base.rstrip('/')}/planning-items/{self.config.planning_item}"
        data = json.dumps({"status": status}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="PATCH",
            headers={
                "X-Engagement": self.config.engagement,
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError(f"PI status PATCH failed: {payload['errors']}")


# --------------------------------------------------------------------------
# Slice 3 — PM auto-dispatch over a Project's backlog
# --------------------------------------------------------------------------


@dataclass
class ProjectRuntimeConfig:
    project: str
    api_base: str = "http://127.0.0.1:8765"
    engagement: str = "CRMBUILDER"
    repo_root: str = "."
    base_branch: str = "main"
    max_concurrent: int = 2
    tier: str = dispatcher._DEFAULT_TIER
    agent_timeout: int = 1800
    manage_api: bool = False
    # Autonomous lever: when a PI's execution completes (all phases verified, the
    # PI at In Review), treat that as resolution so PIs blocked_by it unblock and
    # the chain flows. OFF by default — In Review awaits the resolves-edge closure
    # act, and the PM only dispatches the already-eligible frontier.
    resolve_on_complete: bool = False
    max_pis: int = 50  # backstop against a non-advancing PM loop
    log: Callable[[str], None] = print


@dataclass
class ProjectRunReport:
    project: str
    driven: list[dict] = field(default_factory=list)   # [{planning_item, status, reason}]
    eligible_remaining: list[str] = field(default_factory=list)
    blocked_remaining: list[str] = field(default_factory=list)
    all_resolved: bool = False


def select_next_pi(backlog: dict, attempted: dict) -> str | None:
    """Pure: the next eligible PI (in backlog order) not yet attempted this run.

    ``eligible`` already means startable *and* every ``blocked_by`` predecessor
    Resolved (``pm.project_backlog``), so the frontier the PM dispatches respects
    dependencies. ``attempted`` guards against re-driving a PI that paused/blocked.
    """
    for pid in backlog.get("eligible", []):
        if pid not in attempted:
            return pid
    return None


def drive_planning_item(ado_cfg: AdoRuntimeConfig) -> AdoRunReport:
    """Default per-PI driver seam: run the slice-1/2 :class:`AdoRuntime`."""
    return AdoRuntime(ado_cfg).run()


@dataclass
class ProjectRuntime:
    """Dispatches a Project's eligible PIs to the per-PI driver, in priority order."""

    config: ProjectRuntimeConfig
    pi_driver: Callable[[AdoRuntimeConfig], AdoRunReport] = drive_planning_item

    def log(self, msg: str) -> None:
        self.config.log(msg)

    def _backlog(self) -> dict:
        return dispatcher._get(
            self.config.api_base,
            f"/projects/{self.config.project}/backlog",
            self.config.engagement,
        )  # type: ignore[return-value]

    def _ado_cfg(self, pi: str) -> AdoRuntimeConfig:
        c = self.config
        return AdoRuntimeConfig(
            planning_item=pi, api_base=c.api_base, engagement=c.engagement,
            repo_root=c.repo_root, base_branch=c.base_branch,
            max_concurrent=c.max_concurrent, tier=c.tier,
            agent_timeout=c.agent_timeout, manage_api=c.manage_api, log=c.log,
        )

    def _resolve_pi(self, pi: str) -> None:
        import json
        import urllib.request

        url = f"{self.config.api_base.rstrip('/')}/planning-items/{pi}"
        data = json.dumps({"status": "Resolved"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="PATCH",
            headers={"X-Engagement": self.config.engagement,
                     "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError(f"PI resolve PATCH failed: {payload['errors']}")

    def run(self) -> ProjectRunReport:
        cfg = self.config
        report = ProjectRunReport(project=cfg.project)
        attempted: dict[str, str] = {}

        for _ in range(cfg.max_pis):
            backlog = self._backlog()
            pid = select_next_pi(backlog, attempted)
            if pid is None:
                break
            self.log(f"▶ PM: dispatching {pid}")
            pi_report = self.pi_driver(self._ado_cfg(pid))
            attempted[pid] = pi_report.status
            report.driven.append({
                "planning_item": pid, "status": pi_report.status,
                "reason": pi_report.reason,
            })
            if pi_report.status == "complete" and cfg.resolve_on_complete:
                self._resolve_pi(pid)
                self.log(f"  ✔ {pid} complete → Resolved (autonomous)")
            elif pi_report.status == "complete":
                self.log(f"  ✔ {pid} complete → In Review (awaiting resolution)")
            else:
                self.log(f"  ⏸ {pid} {pi_report.status} — {pi_report.reason}")

        final = self._backlog()
        report.eligible_remaining = final.get("eligible", [])
        report.blocked_remaining = final.get("blocked", [])
        report.all_resolved = final.get("all_resolved", False)
        return report


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="ADO orchestration driver — drive one Planning Item through "
        "its phases (scope → start → run → complete → In Review)."
    )
    p.add_argument("planning_item", help="the PI-NNN to drive")
    p.add_argument("--api-base", default="http://127.0.0.1:8765")
    p.add_argument("--engagement", default="CRMBUILDER")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--base-branch", default="main")
    p.add_argument("--max-concurrent", type=int, default=2)
    p.add_argument("--tier", default=dispatcher._DEFAULT_TIER)
    p.add_argument("--agent-timeout", type=int, default=1800)
    p.add_argument("--manage-api", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="dispatch/decompose plan only; report the next step, spawn nothing")
    args = p.parse_args(argv)

    cfg = AdoRuntimeConfig(
        planning_item=args.planning_item,
        api_base=args.api_base,
        engagement=args.engagement,
        repo_root=args.repo_root,
        base_branch=args.base_branch,
        max_concurrent=args.max_concurrent,
        tier=args.tier,
        agent_timeout=args.agent_timeout,
        manage_api=args.manage_api,
        dry_run=args.dry_run,
    )
    report = AdoRuntime(cfg).run()
    print(f"\nrun complete: {report.status}"
          + (f" — {report.reason}" if report.reason else "")
          + f"; phases completed: {report.completed_phases or '[]'}")
    return 0 if report.status in ("complete", "dry_run") else 1


def project_main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="ADO PM auto-dispatch — drive a Project's eligible Planning "
        "Items through their phases, in dependency order (slice 3)."
    )
    p.add_argument("project", help="the PRJ-NNN whose backlog to dispatch")
    p.add_argument("--api-base", default="http://127.0.0.1:8765")
    p.add_argument("--engagement", default="CRMBUILDER")
    p.add_argument("--repo-root", default=".")
    p.add_argument("--base-branch", default="main")
    p.add_argument("--max-concurrent", type=int, default=2)
    p.add_argument("--tier", default=dispatcher._DEFAULT_TIER)
    p.add_argument("--agent-timeout", type=int, default=1800)
    p.add_argument("--manage-api", action="store_true")
    p.add_argument("--resolve-on-complete", action="store_true",
                   help="autonomous: mark each completed PI Resolved so dependents "
                   "unblock (default: stop at In Review, awaiting closure)")
    args = p.parse_args(argv)

    cfg = ProjectRuntimeConfig(
        project=args.project, api_base=args.api_base, engagement=args.engagement,
        repo_root=args.repo_root, base_branch=args.base_branch,
        max_concurrent=args.max_concurrent, tier=args.tier,
        agent_timeout=args.agent_timeout, manage_api=args.manage_api,
        resolve_on_complete=args.resolve_on_complete,
    )
    report = ProjectRuntime(cfg).run()
    print(f"\nPM run complete: {len(report.driven)} PI(s) driven")
    for d in report.driven:
        print(f"  {d['planning_item']}: {d['status']}"
              + (f" — {d['reason']}" if d['reason'] else ""))
    if report.eligible_remaining:
        print(f"still eligible (paused/blocked this run): {report.eligible_remaining}")
    if report.blocked_remaining:
        print(f"blocked on unresolved dependencies: {report.blocked_remaining}")
    # success when every driven PI completed and nothing remains eligible.
    ok = all(d["status"] == "complete" for d in report.driven) and not report.eligible_remaining
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
