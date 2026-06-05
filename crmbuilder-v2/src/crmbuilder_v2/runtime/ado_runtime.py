"""ADO orchestration driver — the PI-level scheduler (PI-143, slice 1).

The L1/L2 runtime (:mod:`coordinating_runtime`, :mod:`parallel_runtime`) drives
the *bottom* half of the delivery loop: it finds a ``Ready`` Work Task, spawns an
agent, verifies by result, and merges. It does not drive the *top* half — turning
a dispatched Planning Item into ``Ready`` Work Tasks and advancing it phase by
phase. That orchestration was hand-operated endpoint by endpoint.

This module is the deterministic outer loop that closes that gap by *composing*
the already-built substrate with the already-built execution pool:

    dispatch (PM) → decompose → for each phase in serial order:
        start_phase (Lead) → run the parallel pool over the phase → complete_phase (Lead)
    → advance the Planning Item to ``In Review``

**Slice 1 (this build) supplies phase scoping** — the Work Tasks of each phase are
created beforehand (by hand, or by an external step), so the driver only needs the
phase to be ``Ready``. Spawning Architect/phase-specialist agents that *decide* a
phase's Work Tasks from the registry contract is slice 2; PM auto-dispatch from the
project backlog is slice 3.

Like the rest of the runtime, the **decision** (:func:`decide_next`) is a pure
function of the PI's recorded state, separated from the HTTP/pool I/O, so the loop
is unit-testable without a server, a worktree, or a real agent. The driver is
DB-backed-stateless: every iteration re-reads ``phase-overview`` and continues from
wherever the records say things stand, so it is fully resumable (§4.4).
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

from . import dispatcher
from .parallel_runtime import (
    ParallelCoordinatingRuntime,
    ParallelRuntimeConfig,
    PoolRunReport,
)

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
    START = "start"        # start + execute this phase Workstream
    DONE = "done"          # every phase terminal — advance the PI
    PAUSE = "pause"        # a phase needs a human (needs_attention)
    BLOCKED = "blocked"    # nothing executable and not done (unscoped phase, etc.)


@dataclass(frozen=True)
class AdoStep:
    kind: StepKind
    workstream: str | None = None
    reason: str | None = None


def decide_next(overview: dict) -> AdoStep:
    """Decide the next orchestration step from a ``phase-overview`` payload.

    Precedence: a human-attention flag stops everything; then "all phases
    terminal" is done; then the next executable phase is started; otherwise the
    PI is stuck (a phase is not yet ``Ready`` — in slice 1 scoping is supplied,
    so an unscoped phase is a blocked, human-visible state).
    """
    attention = overview.get("needs_attention") or []
    if attention:
        return AdoStep(StepKind.PAUSE, reason=f"needs_attention on {attention}")
    if overview.get("all_terminal"):
        return AdoStep(StepKind.DONE)
    nxt = overview.get("next_executable")
    if nxt:
        return AdoStep(StepKind.START, workstream=nxt)
    return AdoStep(
        StepKind.BLOCKED,
        reason="no executable phase — a phase is not Ready (unscoped) or its "
        "predecessors are not terminal",
    )


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
# The driver
# --------------------------------------------------------------------------


@dataclass
class AdoRuntime:
    """Drives one Planning Item through its phases to ``In Review`` (or a pause)."""

    config: AdoRuntimeConfig
    # Injected for tests; defaults hit the live API / real pool.
    pool_runner: Callable[[AdoRuntimeConfig, str], PoolRunReport] = run_pool_for_workstream

    def log(self, msg: str) -> None:
        self.config.log(msg)

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

        # 3. drive phases serially until done / paused / blocked.
        for _ in range(cfg.max_phases):
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

            # START: open the phase, run the pool over it, then complete it.
            ws = step.workstream
            assert ws is not None
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
        report.reason = f"exceeded max_phases ({cfg.max_phases}) without finishing"
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
# CLI
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="ADO orchestration driver — drive one Planning Item through "
        "its phases (slice 1: scoping supplied)."
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


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
