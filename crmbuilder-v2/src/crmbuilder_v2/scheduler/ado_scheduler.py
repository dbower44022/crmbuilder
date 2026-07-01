"""ADO orchestration driver — the PI-level scheduler (PI-143, slices 1–2).

The L1/L2 runtime (:mod:`coordinating_scheduler`, :mod:`parallel_scheduler`) drives
the *bottom* half of the delivery loop: it finds a ``Ready`` Work Task, spawns an
agent, verifies by result, and merges. It does not drive the *top* half — turning
a dispatched Planning Item into ``Ready`` Work Tasks and advancing it phase by
phase. That orchestration was hand-operated endpoint by endpoint.

This module is the deterministic outer loop that closes that gap by *composing*
the already-built substrate with the already-built execution pool:

    dispatch (PM) → decompose → for each phase in serial order:
        scope (Architect) → start_phase (Lead) → run the pool → complete_phase
        (or, for a phase an interrupted run left ``In Progress``: resume — a
        recovery pass over the recorded Work Task states, then the same
        pool-run → complete_phase tail, PI-157)
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
import threading
import urllib.error
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import StrEnum

from crmbuilder_v2.access.classification import is_content_planning_item
from crmbuilder_v2.scheduler.task_contract import TaskStatus

from . import dispatcher, reconciliation
from .parallel_scheduler import (
    ParallelCoordinatingScheduler,
    ParallelSchedulerConfig,
    PoolRunReport,
)
from .reconciliation import GateDecision
from .repo_build_lock import BuildLockHeld, acquire_build_lock

_DEVELOP_PHASE = "Develop"
_TERMINAL_PHASE = frozenset({"Complete", "Not Applicable"})

# A PI in one of these statuses can still be dispatched (handed to a Lead).
_STARTABLE = frozenset({"Draft", "Decomposed", "Ready"})
# PI-190 / REQ-165: execution_mode gate at the per-PI runtime entry. The
# project loop already filters via backlog["eligible"], but the single-PI
# driver can be pointed at any PI directly — so it re-checks the effective mode
# and skips+logs interactive / unapproved approval-gated items rather than 409ing
# at dispatch/decompose. Rank mirrors access.vocab.EXECUTION_MODE_RANK; the
# runtime stays HTTP-only (no access import) by design.
_INTERACTIVE = "interactive"
_ADO_WITH_APPROVAL = "ado_with_approval"
_EXECUTION_MODE_RANK = {"ado": 0, "ado_with_approval": 1, "interactive": 2}
# Where the driver parks a PI once every phase is terminal: execution is done,
# final Resolved is a governance closure act (the resolves edge), not the
# driver's call.
_DONE_STATUS = "In Review"


# --------------------------------------------------------------------------
# Pure decision — the heart, unit-testable with no I/O
# --------------------------------------------------------------------------


class StepKind(StrEnum):
    SCOPE = "scope"        # a Planned phase needs scoping (an Architect agent)
    START = "start"        # start + execute this Ready phase Workstream
    RESUME = "resume"      # re-enter an In Progress phase from recorded task states
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
    ``START`` it once it is ``Ready``, ``RESUME`` it when an interrupted run left
    it ``In Progress`` (PI-157 — the driver re-enters from the recorded Work Task
    states). A phase whose predecessors are not terminal surfaces as ``BLOCKED``;
    so does a persisted ``Scoping`` phase — ``scope_workstream`` drives
    ``Planned → Scoping → Ready`` inside one call, so a ``Scoping`` row found
    *between* runs is a crash mid-scope with no recorded Work Task basis to
    resume from, and a person should look at it.
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
        if p["status"] == "In Progress":
            return AdoStep(StepKind.RESUME, workstream=wsid, phase_type=ptype)
        return AdoStep(
            StepKind.BLOCKED, workstream=wsid, phase_type=ptype,
            reason=f"phase {wsid} is {p['status']!r} (unexpected between iterations)",
        )

    return AdoStep(StepKind.DONE)


# --------------------------------------------------------------------------
# Config + report
# --------------------------------------------------------------------------


@dataclass
class AdoSchedulerConfig:
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
    # A shared repo lock, set by the PM when driving PIs in parallel so their
    # pools serialize git ops across the one repo (None → the pool's own lock).
    repo_lock: threading.Lock | None = None
    # PI-220 (PRJ-030): engage the sub-agent file-lock backstop in the pool. The
    # release-dev driver sets this True when walking a dev-lane release; default
    # off keeps a plain ADO run byte-identical.
    enable_file_locks: bool = False
    log: Callable[[str], None] = print


@dataclass
class AdoRunReport:
    planning_item: str
    status: TaskStatus = TaskStatus.IN_PROGRESS  # NEEDS_HUMAN=paused/blocked; SUCCEEDED=complete
    dry_run: bool = False
    completed_phases: list[str] = field(default_factory=list)
    reason: str | None = None


# --------------------------------------------------------------------------
# Pool seam — patchable for tests (no real agents spawned under test)
# --------------------------------------------------------------------------


def run_pool_for_workstream(cfg: AdoSchedulerConfig, workstream_id: str) -> PoolRunReport:
    """Run the L2 parallel pool over exactly one phase Workstream's Work Tasks."""
    pool_cfg = ParallelSchedulerConfig(
        api_base=cfg.api_base,
        engagement=cfg.engagement,
        repo_root=cfg.repo_root,
        base_branch=cfg.base_branch,
        tier=cfg.tier,
        target_workstream=workstream_id,
        agent_timeout=cfg.agent_timeout,
        max_concurrent=cfg.max_concurrent,
        manage_api=cfg.manage_api,
        enable_file_locks=cfg.enable_file_locks,
    )
    # `log` is a field on the runtime, not the config — pass it there.
    return ParallelCoordinatingScheduler(
        config=pool_cfg, repo_lock=cfg.repo_lock, log=cfg.log
    ).run()


# --------------------------------------------------------------------------
# Scoping-agent seam (slice 2) — patchable; spawns a real Architect under prod
# --------------------------------------------------------------------------


_PHASE_ROLE = {
    "Design": "produce the specification(s) — what to build and how it will be "
    "verified. You write specs/designs, not code or the deliverable itself.",
    "Develop": "build each Design specification into the working deliverable (code "
    "or the artifact the PI calls for).",
    "Test": "verify the built deliverable against the Design specification.",
}


def build_scoping_prompt(cfg: AdoSchedulerConfig, workstream_id: str, phase_type: str) -> str:
    """The scoping agent's operating protocol.

    Unlike an execution agent it writes no code and needs no worktree — it reads
    the Planning Item and the prior phases' outputs, *decides* the Work Tasks this
    phase needs (one per area the phase touches), and records them in a single
    ``scope`` call. Asserting **Not Applicable** (an empty list, §4.3) is a
    first-class, expected outcome — a phase only scopes work it genuinely adds.
    """
    api = cfg.api_base
    eng = cfg.engagement
    h = f"-H 'X-Engagement: {eng}'"
    role = _PHASE_ROLE.get(phase_type, f"do the {phase_type}-phase work")
    return (
        f"You are the {phase_type}-phase Architect for Planning Item "
        f"{cfg.planning_item}. The {phase_type} phase's job is to {role} Decide the "
        f"Work Tasks this phase (Workstream {workstream_id}) genuinely needs and "
        f"record them. You write NO code — you only decide and record. The live V2 "
        f"API is at {api}; EVERY request must send the header X-Engagement: {eng}.\n\n"
        f"Do exactly this:\n"
        f"1. Read what earlier phases already produced FIRST — `curl -s {h} {api}/"
        f"workstreams/{workstream_id}/prior-phase-outputs` — then the Planning Item "
        f"itself — `curl -s {h} {api}/planning-items/{cfg.planning_item}`.\n"
        f"2. Decide what is genuinely LEFT for the {phase_type} phase to add, given "
        f"what earlier phases already delivered. Scope only NEW, {phase_type}-"
        f"appropriate work — do NOT create tasks that merely re-do, duplicate, or "
        f"re-verify work an earlier phase already completed.\n"
        f"3. If the {phase_type} phase has nothing genuinely new to add for this "
        f"Planning Item (its work is already covered, or there is no {phase_type} "
        f"work for this PI), assert **Not Applicable** by POSTing an EMPTY list — "
        f"this is the correct, common outcome, not a failure:\n"
        f"   `curl -s -X POST {h} -H 'Content-Type: application/json' "
        f"{api}/workstreams/{workstream_id}/scope -d '{{\"work_tasks\": []}}'`\n"
        f"4. Otherwise record the new Work Tasks (one per area it touches; each a "
        f"single-area unit with a 'title', an 'area' — a valid System/Engagement "
        f"area e.g. storage, access, api, mcp, ui — and a 'description') in ONE call:\n"
        f"   `curl -s -X POST {h} -H 'Content-Type: application/json' "
        f"{api}/workstreams/{workstream_id}/scope "
        f"-d '{{\"work_tasks\": [{{\"title\": \"...\", \"area\": \"...\", "
        f"\"description\": \"...\"}}]}}'`\n"
        f"5. Confirm the Workstream is now 'Ready' (or 'Not Applicable') and exit."
    )


def spawn_scoping_agent(prompt: str, *, timeout: int = 1800):
    """Spawn one real Claude agent for an API-only step (scope / reconcile / review).

    No worktree — these agents only read and write governance records via the API.
    Degrades gracefully: an overrun (subprocess kills the agent at the deadline) or
    a spawn failure returns ``None`` rather than raising, because every caller
    **verifies by result** (the phase reaching Ready/Not Applicable, the PI reaching
    Resolved) — a crashed agent must never tear down the driver (DEC-396 in spirit).
    """
    import subprocess
    import tempfile

    from crmbuilder_v2 import agent_secrets

    workdir = tempfile.mkdtemp(prefix="ado-scope-")
    try:
        return subprocess.run(
            ["claude", "-p", prompt, "--permission-mode", "bypassPermissions",
             "--add-dir", workdir],
            cwd=workdir, capture_output=True, text=True, timeout=timeout,
            env=agent_secrets.resolved_agent_env(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def scope_phase_agent(cfg: AdoSchedulerConfig, workstream_id: str, phase_type: str) -> None:
    """Default scope_runner: spawn an Architect to scope ``workstream_id``.

    Success is verified by the caller *by result* (the phase reaching ``Ready`` or
    ``Not Applicable``), not by this agent's exit — consistent with the runtime's
    verify-by-result rule (DEC-396).
    """
    prompt = build_scoping_prompt(cfg, workstream_id, phase_type)
    spawn_scoping_agent(prompt, timeout=cfg.agent_timeout)


# --------------------------------------------------------------------------
# Reconcile-agent seam (item 1) — raises findings over a completed Design phase
# --------------------------------------------------------------------------


def build_reconcile_prompt(cfg: AdoSchedulerConfig, design_workstream_id: str) -> str:
    """The reconciliation reviewer's operating protocol.

    Runs once the Design phase's per-area specs (Work Tasks) exist. It reviews
    them *across areas* for coherence and raises a ``finding`` for each problem;
    a coherent design raises nothing. The findings it raises are what the Develop
    gate (:func:`develop_gate_open`) then reads — a *blocking* finding holds the
    build until it is resolved (REQ-027/033). It writes no code and uses no
    worktree — it only reads specs and records findings.
    """
    api = cfg.api_base
    eng = cfg.engagement
    h = f"-H 'X-Engagement: {eng}'"
    return (
        f"You are the reconciliation reviewer for the Design phase of Planning "
        f"Item {cfg.planning_item} (Workstream {design_workstream_id}). Your one "
        f"job: check the per-area design specs against each other for coherence, "
        f"and record any problems as findings. You write NO code. The live V2 API "
        f"is at {api}; EVERY request must send X-Engagement: {eng}.\n\n"
        f"Do exactly this:\n"
        f"1. Read the Design phase's Work Tasks (the per-area specs) — "
        f"`curl -s {h} {api}/workstreams/{design_workstream_id}/prior-phase-outputs` "
        f"and the Work Tasks belonging to {design_workstream_id}.\n"
        f"2. Compare them across areas. Look for: a conflict (two specs are "
        f"mutually incompatible), a gap (a spec assumes something no other spec "
        f"provides), a dependency (one spec relies on another), or an overlap "
        f"(two specs do the same work).\n"
        f"3. For each problem, raise a finding:\n"
        f"   `curl -s -X POST {h} -H 'Content-Type: application/json' "
        f"{api}/findings -d '{{\"finding_type\": \"conflict|gap|dependency|"
        f"overlap\", \"finding_severity\": \"blocking|advisory\", "
        f"\"finding_summary\": \"...\", \"finding_description\": \"...\", "
        f"\"references\": [{{\"source_type\": \"finding\", \"target_type\": "
        f"\"workstream\", \"target_id\": \"{design_workstream_id}\", "
        f"\"relationship\": \"finding_relates_to\"}}]}}'`\n"
        f"   Use 'blocking' only for a problem that must be fixed before building "
        f"(a true conflict, or a coherence-breaking gap); use 'advisory' otherwise.\n"
        f"4. If the specs are coherent, raise NOTHING and exit. Raising zero "
        f"findings is the correct, common outcome."
    )


def reconcile_phase_agent(cfg: AdoSchedulerConfig, design_workstream_id: str) -> None:
    """Default reconcile_runner: spawn a reviewer to raise findings over Design.

    Best-effort — a coherent design raises no findings, so there is nothing to
    verify by result; the Develop gate is what *enforces* any blocking finding.
    """
    prompt = build_reconcile_prompt(cfg, design_workstream_id)
    spawn_scoping_agent(prompt, timeout=cfg.agent_timeout)


# --------------------------------------------------------------------------
# Develop reconciliation-gate seam (slice 2) — proactive, phase-level
# --------------------------------------------------------------------------


def develop_gate_open(cfg: AdoSchedulerConfig, workstream_id: str) -> GateDecision:
    """Phase-level Develop-gate consult, reusing :mod:`reconciliation`.

    The pool already enforces the gate per Work Task at dispatch
    (``coordinating_scheduler`` → ``reconciliation.develop_gate``); this lets the
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
    # Filter to the work-task membership edges client-side too (REQ-427):
    # belt-and-suspenders for the references-filter alias. A sibling
    # ``blocked_by`` phase-chain edge also targets this workstream, and taking
    # its source (another workstream) as a Work Task id used to 404 and crash
    # the whole project run.
    wt_ids = (
        [
            e["source_id"]
            for e in edges
            if isinstance(e, dict)
            and e.get("relationship") == "work_task_belongs_to_workstream"
        ]
        if isinstance(edges, list)
        else []
    )
    if not wt_ids:
        return GateDecision(True, "no Work Tasks scoped yet")
    try:
        work_task = dispatcher._get(
            cfg.api_base, f"/work-tasks/{wt_ids[0]}", cfg.engagement
        )
    except (urllib.error.URLError, RuntimeError) as exc:
        # A failed Work Task lookup is gate-not-ready, never a crash (REQ-427):
        # pause this phase and surface it rather than aborting the project run.
        code = getattr(exc, "code", None)
        return GateDecision(
            False,
            f"Work Task {wt_ids[0]} lookup failed"
            + (f" (HTTP {code})" if code is not None else "")
            + "; gate not ready",
        )
    return reconciliation.develop_gate(cfg.api_base, cfg.engagement, work_task)


# --------------------------------------------------------------------------
# Rollback-residue seam (PI-157 §2.6) — detects a PI-145 un-merged Complete task
# --------------------------------------------------------------------------


def task_branch_unmerged(cfg: AdoSchedulerConfig, work_task_id: str) -> bool:
    """Whether a Complete task's ``ado/<wtk-id>`` branch is un-merged (PI-145 residue).

    Under PI-145 a failed phase rolls back every sibling merge, but the
    rolled-back siblings' Work Task rows stay ``Complete``. Detection-only: the
    branch still exists *and* carries commits not reachable from
    ``cfg.base_branch`` means the task's verified work was un-merged by a
    rollback. A task whose branch is absent or fully merged passes silently —
    two fast local git reads per Complete task.
    """
    import subprocess

    branch = f"ado/{work_task_id.lower()}"
    probe = subprocess.run(
        ["git", "-C", cfg.repo_root, "rev-parse", "--verify", "--quiet", branch],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        return False  # branch absent → nothing un-merged
    count = subprocess.run(
        ["git", "-C", cfg.repo_root, "rev-list", "--count",
         f"{cfg.base_branch}..{branch}"],
        capture_output=True, text=True,
    )
    try:
        return int(count.stdout.strip()) > 0
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Content-work execution lane (PI-202 / REQ-187, DEC-763/764)
# --------------------------------------------------------------------------
#
# Content/authoring (methodology-*) Planning Items produce governance RECORDS,
# not git commits, so their Develop/Test phases do NOT run through the
# verify-by-commit + pytest pool (``run_pool_for_workstream``). Develop's agents
# AUTHOR the records the Design called for (DB writes via the API); Test is an
# independent Tester review of those records against the Design's acceptance
# criteria (DEC-763) — pass advances the phase, a finding blocks it. Both reuse
# the API-only agent spawner (``spawn_scoping_agent``); neither touches git, and
# the content branch is kept off the git-residue/branch checks. The human sign-off
# in the Review panel remains the final gate (DEC-763).


_CONTENT_PHASE_ROLE = {
    "Design": "decide WHAT records to author and the explicit acceptance criteria "
    "the Test step will check them against.",
    "Develop": "AUTHOR the governance records the Design called for (requirements, "
    "topics, decisions, rules, glossary entries, or document sections) via the API "
    "— DB writes, not code or commits.",
    "Test": "VERIFY the authored records are correct and complete against the "
    "Design's acceptance criteria — a review, not a test suite.",
}


def build_content_work_prompt(
    cfg: AdoSchedulerConfig, workstream_id: str, phase_type: str
) -> str:
    """The content agent's operating protocol for one phase Workstream (REQ-187).

    Develop = author the records; Test = the independent Tester review against the
    Design's acceptance criteria (DEC-763/764). API-only — no worktree, no commits.
    """
    api = cfg.api_base
    eng = cfg.engagement
    h = f"-H 'X-Engagement: {eng}'"
    role = _CONTENT_PHASE_ROLE.get(
        phase_type, f"do the {phase_type}-phase content work."
    )
    tester = phase_type == "Test"
    step2 = (
        "2. For each Work Task, REVIEW the records the Develop phase authored "
        "against the Design's acceptance criteria — completeness (nothing the "
        "Design called for is missing), correctness (accurate, consistent, traced "
        "to source, no contradictions), conformance (recording rules + identifier "
        "discipline). If a Work Task's records pass, claim it and mark it Complete; "
        "if not, raise a finding and mark the task Blocked, leaving the phase for a "
        "person. Do NOT sign off — the human Review-panel sign-off is the final "
        "gate.\n"
        if tester else
        "2. For each Work Task, AUTHOR the records the Design called for via the "
        "API (POST /requirements, /topics, /decisions, /references, etc. — include "
        "provenance), then claim the Work Task and mark it Complete. Author "
        "records, never code or commits.\n"
    )
    return (
        f"You are the {phase_type}-phase {'Tester' if tester else 'agent'} for "
        f"content Planning Item {cfg.planning_item}. Content work produces "
        f"governance RECORDS, not code — make API calls only, no git, no worktree. "
        f"Your job: {role} The live V2 API is at {api}; EVERY request must send "
        f"X-Engagement: {eng}.\n\n"
        f"Do exactly this:\n"
        f"1. Read the phase's Work Tasks and prior phases' outputs — "
        f"`curl -s {h} {api}/workstreams/{workstream_id}/prior-phase-outputs` — and "
        f"the Planning Item — `curl -s {h} {api}/planning-items/{cfg.planning_item}`.\n"
        f"{step2}"
        f"3. Confirm every Work Task in {workstream_id} is Complete (or Blocked with "
        f"a finding) and exit."
    )


def run_content_pool_for_workstream(
    cfg: AdoSchedulerConfig, workstream_id: str, phase_type: str
) -> PoolRunReport:
    """Default content execution lane for one phase Workstream (REQ-187).

    Spawns a single API-only content agent (author for Develop, Tester for Test)
    that drives the phase's Work Tasks to a terminal state (Complete, or Blocked on
    a finding) by authoring/reviewing records — no git pool, no commits. Verified
    by result: returns a paused report if any Work Task is still non-terminal after
    the agent, so the driver pauses for a person; otherwise the driver's
    ``complete-phase`` call closes the phase.
    """
    prompt = build_content_work_prompt(cfg, workstream_id, phase_type)
    spawn_scoping_agent(prompt, timeout=cfg.agent_timeout)
    edges = dispatcher._get(
        cfg.api_base,
        f"/references?target_id={workstream_id}"
        "&relationship=work_task_belongs_to_workstream",
        cfg.engagement,
    )
    wt_ids = [
        e["source_id"]
        for e in (edges or [])
        if isinstance(e, dict) and e.get("source_type") == "work_task"
    ]
    pending: list[str] = []
    for wtid in wt_ids:
        row = dispatcher._get(cfg.api_base, f"/work-tasks/{wtid}", cfg.engagement)
        status = row.get("work_task_status") if isinstance(row, dict) else None
        if status not in ("Complete", "Blocked"):
            pending.append(wtid)
    if pending:
        return PoolRunReport(
            paused=True,
            pause_reason=(
                f"content phase {workstream_id}: {len(pending)} Work Task(s) not "
                f"terminal after the content agent ({', '.join(pending)})"
            ),
        )
    return PoolRunReport(paused=False)


# --------------------------------------------------------------------------
# The driver
# --------------------------------------------------------------------------


@dataclass
class AdoScheduler:
    """Drives one Planning Item through its phases to ``In Review`` (or a pause)."""

    config: AdoSchedulerConfig
    # Injected for tests; defaults hit the live API / real pool / real agents.
    pool_runner: Callable[[AdoSchedulerConfig, str], PoolRunReport] = run_pool_for_workstream
    scope_runner: Callable[[AdoSchedulerConfig, str, str], None] = scope_phase_agent
    gate_checker: Callable[[AdoSchedulerConfig, str], GateDecision] = develop_gate_open
    reconcile_runner: Callable[[AdoSchedulerConfig, str], None] = reconcile_phase_agent
    unmerged_check: Callable[[AdoSchedulerConfig, str], bool] = task_branch_unmerged
    # PI-202 / REQ-187: content (methodology-*) PIs run Develop/Test through the
    # review lane, not the git pool. Injected for tests like the others.
    content_pool_runner: Callable[
        [AdoSchedulerConfig, str, str], PoolRunReport
    ] = run_content_pool_for_workstream

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

    def _patch(self, path: str, body: dict) -> object:
        return dispatcher._patch(
            self.config.api_base, path, self.config.engagement, body
        )

    def _pi(self) -> dict:
        return self._get(f"/planning-items/{self.config.planning_item}")  # type: ignore[return-value]

    def _is_content(self) -> bool:
        """Whether this PI is content/authoring work (REQ-185) — routes its
        Develop/Test phases off the git pool onto the review lane (REQ-187)."""
        pi = self._pi()
        return isinstance(pi, dict) and is_content_planning_item(pi)

    def _project_mode(self) -> str:
        """The parent Project's execution_mode, via the belongs-to-project edge.
        The references list endpoint ignores the relationship filter, so the
        edges are filtered client-side. Fails open to ``ado`` on any read error:
        this runtime guard is a convenience over the access-layer gates, which
        remain the real enforcement, so a missed project read never lets an
        interactive PI actually be worked (dispatch/decompose still 409)."""
        try:
            edges = self._get(
                f"/references?source_id={self.config.planning_item}"
                "&relationship=planning_item_belongs_to_project"
            )
            proj_id = None
            if isinstance(edges, list):
                for e in edges:
                    if (e.get("relationship") == "planning_item_belongs_to_project"
                            and e.get("target_type") == "project"):
                        proj_id = e.get("target_id")
                        break
            if not proj_id:
                return "ado"
            proj = self._get(f"/projects/{proj_id}")
            mode = proj.get("project_execution_mode") if isinstance(proj, dict) else None
            return mode or "ado"
        except Exception:
            return "ado"

    def _effective_mode(self, pi: dict) -> str:
        """The PI's effective execution_mode — the more restrictive of its own
        value and its Project's (mirrors pm._effective_mode)."""
        pi_mode = pi.get("execution_mode") or "ado"
        return max((pi_mode, self._project_mode()),
                   key=lambda m: _EXECUTION_MODE_RANK.get(m, 0))

    def _execution_gate(self, pi: dict) -> tuple[TaskStatus, str] | None:
        """Return ``(status, message)`` if this PI is not the ADO's to run
        (PI-190 / REQ-165), else ``None``. Both cases resolve to
        ``NEEDS_HUMAN`` (the run-outcome vocabulary); the message carries which
        case it is. Interactive items are never run; ado_with_approval items wait
        for a human approve-dispatch signal."""
        mode = self._effective_mode(pi)
        pid = self.config.planning_item
        if mode == _INTERACTIVE:
            return (TaskStatus.NEEDS_HUMAN, f"⏸ {pid} is execution_mode 'interactive' — "
                    f"left for a human; the ADO does not run it.")
        if mode == _ADO_WITH_APPROVAL and not pi.get("dispatch_approved"):
            return (TaskStatus.NEEDS_HUMAN, f"⏸ {pid} is 'ado_with_approval' and not "
                    f"yet approved — left pending a human approve-dispatch.")
        return None

    def _overview(self) -> dict:
        return self._get(
            f"/planning-items/{self.config.planning_item}/phase-overview"
        )  # type: ignore[return-value]

    def _phase_work_tasks(self, workstream_id: str) -> list[dict]:
        """The phase's Work Task rows, in identifier order (the edge query
        ``develop_gate_open``/``_workstream_members`` already use)."""
        edges = self._get(
            f"/references?target_id={workstream_id}"
            "&relationship=work_task_belongs_to_workstream"
        )
        ids = (
            [e["source_id"] for e in edges if e.get("source_type") == "work_task"]
            if isinstance(edges, list)
            else []
        )
        return [self._get(f"/work-tasks/{wtid}") for wtid in sorted(ids)]  # type: ignore[misc]

    # --- the loop -------------------------------------------------------

    def run(self) -> AdoRunReport:
        cfg = self.config
        pi = cfg.planning_item
        report = AdoRunReport(planning_item=pi)

        # 0. execution_mode gate (PI-190 / REQ-165): if this PI is interactive or
        # an unapproved approval-gated item, the ADO must not run it — skip
        # cleanly and tell the operator (the access-layer gates would otherwise
        # 409 at dispatch/decompose).
        pi_record = self._pi()
        gate = self._execution_gate(pi_record)
        if gate is not None:
            report.status, report.reason = gate
            self.log(gate[1])
            return report

        # 1. ensure dispatched (idempotent: only a startable PI is dispatched).
        status = pi_record["status"]
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
            report.status = TaskStatus.NOT_STARTED
            report.dry_run = True
            report.reason = step.reason
            return report

        # 3. drive phases serially until done / paused / blocked. Each phase can
        # take two iterations (scope, then execute), so budget accordingly.
        # (A RESUME consumes an iteration exactly as START does — a
        # resume-after-pause is a fresh run, so the formula is unchanged.)
        for _ in range(cfg.max_phases * 2 + 1):
            ov = self._overview()
            step = decide_next(ov)

            if step.kind is StepKind.DONE:
                # advance the PI out of In Progress (execution complete).
                self._patch_pi_status(_DONE_STATUS)
                self.log(f"✔ {pi}: all phases terminal → {_DONE_STATUS}")
                report.status = TaskStatus.SUCCEEDED
                return report

            if step.kind is StepKind.PAUSE:
                self.log(f"⏸ {pi}: paused — {step.reason}")
                report.status = TaskStatus.NEEDS_HUMAN
                report.reason = step.reason
                return report

            if step.kind is StepKind.BLOCKED:
                self.log(f"⏹ {pi}: blocked — {step.reason}")
                report.status = TaskStatus.NEEDS_HUMAN
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
                    # Per-agent retry: a scoping agent that exits leaving the
                    # phase 'Planned' is most often a transient agent
                    # incompletion, not an unscopable phase — re-spawn once
                    # before pausing for a person.
                    self.log(
                        f"  {ws} still {after!r} after scoping — retrying once"
                    )
                    self.scope_runner(cfg, ws, step.phase_type or "")
                    after = self._phase_status(ws)
                if after not in ("Ready", "Not Applicable"):
                    report.status = TaskStatus.NEEDS_HUMAN
                    report.reason = (
                        f"scoping did not complete phase {ws} (still {after!r}); "
                        f"a person needs to scope it"
                    )
                    self.log(f"⏸ {pi}: {report.reason}")
                    return report
                self.log(f"  {ws} scoped → {after}")
                continue

            # RESUME (PI-157): recover an In Progress phase from its recorded
            # Work Task states, then re-enter the shared execution tail.
            if step.kind is StepKind.RESUME:
                if not self._resume_phase(report, ws, step.phase_type):
                    return report
                continue

            # START: open the phase and run the shared execution tail.
            if not self._execute_phase(report, ws, step.phase_type, open_phase=True):
                return report

        report.status = TaskStatus.NEEDS_HUMAN
        report.reason = f"exceeded the phase budget ({cfg.max_phases}) without finishing"
        self.log(f"⚠ {pi}: {report.reason}")
        return report

    def _execute_phase(
        self, report: AdoRunReport, ws: str, phase_type: str | None,
        *, open_phase: bool,
    ) -> bool:
        """The shared START/RESUME execution tail (PI-157).

        A Develop phase first clears the reconciliation gate (re-checked on
        RESUME too — a blocking finding may have been raised between the
        original start and the resume). START opens the phase
        (``start-execution``); RESUME skips that call — ``start_phase``
        requires ``Ready`` and would 409 on an ``In Progress`` Workstream.
        Then the pool runs, the phase completes, and a completed Design phase
        is reconciled. Returns True to continue the driver loop, False when
        ``report`` is finalized (a pause) and the loop should return it.
        """
        cfg = self.config
        pi = cfg.planning_item

        if phase_type == _DEVELOP_PHASE:
            gate = self.gate_checker(cfg, ws)
            if not gate.allow:
                report.status = TaskStatus.NEEDS_HUMAN
                report.reason = (
                    f"Develop gate held on {ws}: {gate.reason} — reconcile the "
                    f"Design before building"
                )
                self.log(f"⏸ {pi}: {report.reason}")
                return False

        if open_phase:
            self._post(f"/workstreams/{ws}/start-execution")
            self.log(f"▶ {pi}: started phase {ws} → running pool")
        else:
            self.log(f"▶ {pi}: resuming phase {ws} → running pool")

        # PI-202 / REQ-187: content PIs author/verify records through the review
        # lane; software PIs run the verify-by-commit + pytest pool.
        if self._is_content():
            pool_report = self.content_pool_runner(cfg, ws, phase_type or "")
        else:
            pool_report = self.pool_runner(cfg, ws)
        if pool_report.paused:
            self.log(f"⏸ {pi}: execution paused in phase {ws}")
            report.status = TaskStatus.NEEDS_HUMAN
            report.reason = f"execution paused in {ws}"
            return False

        # REQ-422: complete-phase requires *every* Work Task Complete, else it
        # 409s. The pool drained without pausing, so a non-Complete task now is
        # an anomaly (e.g. a task reverted out-of-band by a concurrent runtime).
        # An uncaught 409 here propagates out of run() and crashes the whole
        # multi-PI build — so catch it and halt THIS planning item gracefully
        # (the 409 body names the unfinished tasks), leaving the run and the
        # other PIs intact.
        try:
            self._post(f"/workstreams/{ws}/complete-phase")
        except urllib.error.HTTPError as exc:
            if exc.code != 409:
                raise
            try:
                detail = exc.read().decode("utf-8")[:300]
            except Exception:
                detail = ""
            report.status = TaskStatus.NEEDS_HUMAN
            report.reason = (
                f"phase {ws} cannot complete — not all Work Tasks are Complete; "
                f"halting this planning item, not the run. {detail}".strip()
            )
            self.log(f"⏸ {pi}: {report.reason}")
            return False
        self.log(f"✔ {pi}: phase {ws} complete "
                 f"({len(pool_report.merged)} task(s) merged)")
        report.completed_phases.append(ws)

        # A completed Design phase is reconciled across areas: the reviewer
        # raises findings; the Develop gate (above) then enforces blocking ones.
        if phase_type == "Design":
            self.log(f"▶ {pi}: reconciling Design ({ws}) — checking coherence")
            self.reconcile_runner(cfg, ws)
        return True

    def _resume_phase(
        self, report: AdoRunReport, ws: str, phase_type: str | None
    ) -> bool:
        """Recovery pass over an ``In Progress`` phase's recorded task states (PI-157).

        Reconciles each Work Task by its recorded state — skip ``Complete``
        (subject to the PI-145 rollback-residue guard), release stale claims
        (a claim observed at resume time is stale by definition: one runtime
        per PI, and agents are synchronous children of the dead run), and
        rewind stale statuses along legal lifecycle transitions only. The
        Workstream status itself is never rewound — the phase stays
        ``In Progress`` throughout, which is truthful. Re-runnable: release is
        idempotent when unclaimed and every PATCH is conditional on the
        observed state. Returns True to continue the loop, False when
        ``report`` is finalized.
        """
        cfg = self.config
        pi = cfg.planning_item
        self.log(f"▶ {pi}: resuming phase {ws} ({phase_type}) — recovery pass")

        tasks = self._phase_work_tasks(ws)
        blocked: list[str] = []
        residue: list[str] = []
        for task in tasks:
            wtid = task["work_task_identifier"]
            status = task.get("work_task_status")
            claimant = task.get("work_task_claimed_by")
            if status == "Complete":
                # PI-202 / REQ-187: content tasks have no git branch — the
                # unmerged-residue check is a software-lane concern only.
                if not self._is_content() and self.unmerged_check(cfg, wtid):
                    residue.append(wtid)
                continue
            if status == "Blocked":
                # A person parked it; RESUME must not override human judgment.
                blocked.append(wtid)
                continue
            if claimant:
                # Echo the row's recorded claimant — release rejects a mismatch,
                # and a registry-profile agent may claim under another identity.
                self._post(f"/work-tasks/{wtid}/release", {"claimed_by": claimant})
                self.log(f"  {wtid}: released stale claim ({claimant})")
            if status == "Claimed":
                self._patch(f"/work-tasks/{wtid}", {"work_task_status": "Ready"})
            elif status == "In Progress":
                # No legal In Progress → Ready transition: Failed records the
                # dead attempt, then Failed → Ready is the vocab's retry path.
                self._patch(f"/work-tasks/{wtid}", {"work_task_status": "Failed"})
                self._patch(f"/work-tasks/{wtid}", {"work_task_status": "Ready"})
            elif status in ("Failed", "Planned"):
                # Failed → Ready is the retry path; a Planned task scoped after
                # the phase started was never readied (mirrors start_phase).
                self._patch(f"/work-tasks/{wtid}", {"work_task_status": "Ready"})
            # "Ready" (now unclaimed): leave — the pool will dispatch it.

        if residue:
            report.status = TaskStatus.NEEDS_HUMAN
            report.reason = (
                f"resume: {ws} has Complete task(s) {residue} whose branch is "
                f"not merged into {cfg.base_branch} (PI-145 rollback residue) — "
                f"re-merge or re-open them, then relaunch"
            )
            self.log(f"⏸ {pi}: {report.reason}")
            return False

        if blocked:
            report.status = TaskStatus.NEEDS_HUMAN
            report.reason = (
                f"resume: {ws} has Blocked task(s) {blocked}; a person parked "
                f"them — unblock or fail them, then relaunch"
            )
            self.log(f"⏸ {pi}: {report.reason}")
            return False

        if tasks and all(t.get("work_task_status") == "Complete" for t in tasks):
            # The PI-153/WSK-072 shape: the previous run finished every task but
            # exited before issuing complete-phase. No pool run, no start.
            self._post(f"/workstreams/{ws}/complete-phase")
            self.log(f"✔ {pi}: phase {ws} resumed — all tasks already complete")
            report.completed_phases.append(ws)
            return True

        return self._execute_phase(report, ws, phase_type, open_phase=False)

    def _patch_pi_status(self, status: str) -> None:
        # The update endpoint is PATCH; dispatcher only has GET/POST, so go
        # through urllib directly with the same envelope/header contract.
        import json
        import urllib.request

        from crmbuilder_v2.scheduler import runtime_auth

        url = f"{self.config.api_base.rstrip('/')}/planning-items/{self.config.planning_item}"
        data = json.dumps({"status": status}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="PATCH",
            headers=runtime_auth.auth_headers(self.config.engagement, content_type=True),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError(f"PI status PATCH failed: {payload['errors']}")


# --------------------------------------------------------------------------
# Slice 3 — PM auto-dispatch over a Project's backlog
# --------------------------------------------------------------------------


def build_review_prompt(api_base: str, engagement: str, pi: str) -> str:
    """The review/closure reviewer's operating protocol for an In-Review PI."""
    h = f"-H 'X-Engagement: {engagement}'"
    return (
        f"You are the closure reviewer for Planning Item {pi} (now 'In Review'). "
        f"This is a quick close-out check, NOT a deep audit — make exactly the few "
        f"API calls below, decide, and exit promptly. The live V2 API is at "
        f"{api_base}; EVERY request must send X-Engagement: {engagement}.\n\n"
        f"Do exactly this and nothing more:\n"
        f"1. `curl -s {h} {api_base}/planning-items/{pi}/phase-overview` — the PI is "
        f"satisfied if every phase is 'Complete' or 'Not Applicable' (look at each "
        f"phase's status and that its Work Tasks are complete).\n"
        f"2. If satisfied, resolve it and STOP: `curl -s -X PATCH {h} -H "
        f"'Content-Type: application/json' {api_base}/planning-items/{pi} "
        f"-d '{{\"status\": \"Resolved\"}}'`.\n"
        f"3. If NOT satisfied, do nothing (leave it 'In Review' for a person) and "
        f"exit. Do not read files, inspect git, or analyze further — decide from the "
        f"phase-overview alone."
    )


def review_close_pi(cfg: ProjectSchedulerConfig, pi: str) -> bool:
    """Default closure_runner: spawn a reviewer that resolves the PI if satisfied.

    Verified by result — returns True iff the PI reached ``Resolved``. A reviewer
    that declines leaves the PI ``In Review`` (the PM then flags it for a person).
    """
    prompt = build_review_prompt(cfg.api_base, cfg.engagement, pi)
    spawn_scoping_agent(prompt, timeout=cfg.agent_timeout)
    pi_row = dispatcher._get(cfg.api_base, f"/planning-items/{pi}", cfg.engagement)
    return isinstance(pi_row, dict) and pi_row.get("status") == "Resolved"


@dataclass
class ProjectSchedulerConfig:
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
    # Item 3: spawn a review/closure agent for each completed PI that resolves it
    # only if the work satisfies the PI (governance-faithful, with judgment). Takes
    # precedence over the blunt resolve_on_complete; a declined review leaves the PI
    # In Review and is flagged. This lets chains flow without the blunt lever.
    review_on_complete: bool = False
    # Item 2: how many *independent* eligible PIs to drive at once. All eligible
    # PIs are mutually independent (eligible ⇒ every blocked_by is Resolved ⇒ no
    # eligible PI blocks another), so the eligible set is a safe parallel batch;
    # their pools share one repo lock so cross-PI git merges serialize. 1 = serial.
    max_parallel_pis: int = 1
    max_pis: int = 50  # backstop against a non-advancing PM loop
    # REQ-423 / PI-364 — exclusive per-project build claim (heartbeat lease). When
    # on, the runtime claims the project before driving it and refuses to start if
    # another runtime holds a fresh lease, so concurrent runtimes cannot corrupt
    # each other's in-flight work-task states. The runtime heartbeats the lease
    # every ``heartbeat_seconds``; a claim older than ``claim_stale_seconds`` (a
    # crashed runtime) is reclaimable. ``runtime_id`` identifies this runtime as
    # the claimant (auto-generated when empty).
    enforce_run_lock: bool = True
    claim_stale_seconds: float = 300.0
    heartbeat_seconds: float = 60.0
    runtime_id: str = ""
    log: Callable[[str], None] = print


@dataclass
class ProjectRunReport:
    project: str
    driven: list[dict] = field(default_factory=list)   # [{planning_item, status, reason}]
    eligible_remaining: list[str] = field(default_factory=list)
    blocked_remaining: list[str] = field(default_factory=list)
    all_resolved: bool = False
    # REQ-423: True when the run did not start because another runtime already
    # holds a fresh build-run claim on this project.
    refused: bool = False


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


def eligible_batch(backlog: dict, attempted: dict, cap: int) -> list[str]:
    """Pure: up to ``cap`` eligible PIs not yet attempted — the parallel batch.

    Every eligible PI is mutually independent (eligible ⇒ all ``blocked_by``
    Resolved ⇒ none blocks another), so the whole eligible-not-attempted set is
    safe to drive concurrently; ``cap`` bounds how many at once.
    """
    fresh = [pid for pid in backlog.get("eligible", []) if pid not in attempted]
    return fresh[: max(1, cap)]


def drive_planning_item(ado_cfg: AdoSchedulerConfig) -> AdoRunReport:
    """Default per-PI driver seam: run the slice-1/2 :class:`AdoScheduler`."""
    return AdoScheduler(ado_cfg).run()


@dataclass
class ProjectScheduler:
    """Dispatches a Project's eligible PIs to the per-PI driver, in priority order."""

    config: ProjectSchedulerConfig
    pi_driver: Callable[[AdoSchedulerConfig], AdoRunReport] = drive_planning_item
    closure_runner: Callable[[ProjectSchedulerConfig, str], bool] = review_close_pi

    def log(self, msg: str) -> None:
        self.config.log(msg)

    def _backlog(self) -> dict:
        return dispatcher._get(
            self.config.api_base,
            f"/projects/{self.config.project}/backlog",
            self.config.engagement,
        )  # type: ignore[return-value]

    # --- REQ-423: exclusive build-run claim (heartbeat lease) ---------------

    @property
    def _runtime_id(self) -> str:
        if self.config.runtime_id:
            return self.config.runtime_id
        rid = getattr(self, "_rid", "")
        if not rid:
            import uuid

            rid = f"projsched-{self.config.project}-{uuid.uuid4().hex[:12]}"
            self._rid = rid
        return rid

    def _acquire_run_lock(self) -> bool:
        """Claim this project's build run. True on success, False when a different
        runtime holds a fresh lease (the refuse path)."""
        cfg = self.config
        try:
            dispatcher._post(
                cfg.api_base, f"/projects/{cfg.project}/claim", cfg.engagement,
                {"claimed_by": self._runtime_id,
                 "stale_seconds": cfg.claim_stale_seconds},
            )
            return True
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                return False
            raise

    def _heartbeat_once(self) -> None:
        cfg = self.config
        dispatcher._post(
            cfg.api_base, f"/projects/{cfg.project}/heartbeat", cfg.engagement,
            {"claimed_by": self._runtime_id},
        )

    def _release_run_lock(self) -> None:
        cfg = self.config
        try:
            dispatcher._post(
                cfg.api_base, f"/projects/{cfg.project}/release", cfg.engagement,
                {"claimed_by": self._runtime_id},
            )
        except Exception:  # best-effort — a lost/expired lease needs no release
            pass

    def _heartbeat_loop(self, stop: threading.Event) -> None:
        while not stop.wait(self.config.heartbeat_seconds):
            try:
                self._heartbeat_once()
            except Exception:  # transient error / lost lease — the run's own
                pass           # writes will surface a genuine loss

    def _ado_cfg(self, pi: str, repo_lock: threading.Lock | None = None) -> AdoSchedulerConfig:
        c = self.config
        return AdoSchedulerConfig(
            planning_item=pi, api_base=c.api_base, engagement=c.engagement,
            repo_root=c.repo_root, base_branch=c.base_branch,
            max_concurrent=c.max_concurrent, tier=c.tier,
            agent_timeout=c.agent_timeout, manage_api=c.manage_api,
            repo_lock=repo_lock, log=c.log,
        )

    def _resolve_pi(self, pi: str) -> None:
        import json
        import urllib.request

        from crmbuilder_v2.scheduler import runtime_auth

        url = f"{self.config.api_base.rstrip('/')}/planning-items/{pi}"
        data = json.dumps({"status": "Resolved"}).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="PATCH",
            headers=runtime_auth.auth_headers(self.config.engagement, content_type=True),
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        if payload.get("errors"):
            raise RuntimeError(f"PI resolve PATCH failed: {payload['errors']}")

    def _close_out(self, pid: str, pi_report: AdoRunReport) -> None:
        """Resolve / review / log one completed (or paused) PI's outcome."""
        cfg = self.config
        if pi_report.status is TaskStatus.SUCCEEDED and cfg.review_on_complete:
            if self.closure_runner(cfg, pid):
                self.log(f"  ✔ {pid} complete → reviewed → Resolved")
            else:
                self.log(f"  ⏸ {pid} complete → review declined → In Review "
                         f"(needs a person)")
        elif pi_report.status is TaskStatus.SUCCEEDED and cfg.resolve_on_complete:
            self._resolve_pi(pid)
            self.log(f"  ✔ {pid} complete → Resolved (autonomous)")
        elif pi_report.status is TaskStatus.SUCCEEDED:
            self.log(f"  ✔ {pid} complete → In Review (awaiting resolution)")
        else:
            self.log(f"  ⏸ {pid} {pi_report.status.value} — {pi_report.reason}")

    def run(self) -> ProjectRunReport:
        cfg = self.config
        report = ProjectRunReport(project=cfg.project)

        # REQ-423: claim the project's build run before driving it. If another
        # runtime holds a fresh lease, refuse — do not corrupt its in-flight work.
        if cfg.enforce_run_lock and not self._acquire_run_lock():
            report.refused = True
            self.log(
                f"⏸ project {cfg.project} is already being driven by another "
                f"runtime (fresh build-run claim) — refusing to start a second"
            )
            return report

        stop_heartbeat = threading.Event()
        hb_thread: threading.Thread | None = None
        if cfg.enforce_run_lock:
            hb_thread = threading.Thread(
                target=self._heartbeat_loop, args=(stop_heartbeat,), daemon=True
            )
            hb_thread.start()

        try:
            attempted: dict[str, TaskStatus] = {}
            # One repo lock shared by every PI's pool this run, so when PIs run in
            # parallel their worktree/merge git ops still serialize across the repo.
            shared_lock = threading.Lock()

            for _ in range(cfg.max_pis):
                backlog = self._backlog()
                batch = eligible_batch(backlog, attempted, cfg.max_parallel_pis)
                if not batch:
                    break
                self.log(f"▶ PM: dispatching {batch}")

                if len(batch) == 1:
                    results = {batch[0]: self.pi_driver(self._ado_cfg(batch[0]))}
                else:
                    results = {}
                    with ThreadPoolExecutor(max_workers=len(batch)) as ex:
                        futs = {
                            ex.submit(self.pi_driver, self._ado_cfg(pid, repo_lock=shared_lock)): pid
                            for pid in batch
                        }
                        for fut in as_completed(futs):
                            results[futs[fut]] = fut.result()

                # process in stable (batch) order for deterministic close-out.
                for pid in batch:
                    pi_report = results[pid]
                    attempted[pid] = pi_report.status
                    report.driven.append({
                        "planning_item": pid, "status": pi_report.status,
                        "reason": pi_report.reason,
                    })
                    self._close_out(pid, pi_report)

            final = self._backlog()
            report.eligible_remaining = final.get("eligible", [])
            report.blocked_remaining = final.get("blocked", [])
            report.all_resolved = final.get("all_resolved", False)
            return report
        finally:
            stop_heartbeat.set()
            if hb_thread is not None:
                hb_thread.join(timeout=2)
            if cfg.enforce_run_lock:
                self._release_run_lock()


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

    cfg = AdoSchedulerConfig(
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
    # REQ-441 / PI-380: one builder per working copy. A dry-run does no git ops,
    # so it does not contend; a real run refuses if another driver holds the lock.
    if cfg.dry_run:
        report = AdoScheduler(cfg).run()
    else:
        try:
            with acquire_build_lock(cfg.repo_root, label=f"ado {cfg.planning_item}"):
                report = AdoScheduler(cfg).run()
        except BuildLockHeld as exc:
            print(f"\n⏸ refused — {exc}")
            return 2
    print(f"\nrun complete: {report.status}"
          + (f" — {report.reason}" if report.reason else "")
          + f"; phases completed: {report.completed_phases or '[]'}")
    return 0 if report.status is TaskStatus.SUCCEEDED or report.dry_run else 1


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
    p.add_argument("--review-on-complete", action="store_true",
                   help="spawn a closure agent that reviews each completed PI and "
                   "resolves it only if the work satisfies it (judgment + faithful)")
    p.add_argument("--max-parallel-pis", type=int, default=1,
                   help="drive up to N independent eligible PIs at once (1 = serial)")
    args = p.parse_args(argv)

    cfg = ProjectSchedulerConfig(
        project=args.project, api_base=args.api_base, engagement=args.engagement,
        repo_root=args.repo_root, base_branch=args.base_branch,
        max_concurrent=args.max_concurrent, tier=args.tier,
        agent_timeout=args.agent_timeout, manage_api=args.manage_api,
        resolve_on_complete=args.resolve_on_complete,
        review_on_complete=args.review_on_complete,
        max_parallel_pis=args.max_parallel_pis,
    )
    # REQ-441 / PI-380: one builder per working copy — refuse a second concurrent
    # driver against the same checkout (the PM shares one repo_lock internally,
    # but two PM/ado processes do not serialize against each other).
    try:
        with acquire_build_lock(cfg.repo_root, label=f"ado-pm {cfg.project}"):
            report = ProjectScheduler(cfg).run()
    except BuildLockHeld as exc:
        print(f"\n⏸ refused — {exc}")
        return 2
    print(f"\nPM run complete: {len(report.driven)} PI(s) driven")
    for d in report.driven:
        print(f"  {d['planning_item']}: {d['status']}"
              + (f" — {d['reason']}" if d['reason'] else ""))
    if report.eligible_remaining:
        print(f"still eligible (paused/blocked this run): {report.eligible_remaining}")
    if report.blocked_remaining:
        print(f"blocked on unresolved dependencies: {report.blocked_remaining}")
    # success when every driven PI completed and nothing remains eligible.
    ok = all(d["status"] is TaskStatus.SUCCEEDED for d in report.driven) and not report.eligible_remaining
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
