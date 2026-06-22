"""Release-pipeline orchestration loop — PI-219 (PRJ-033), AL-4/AL-5.

The thin scheduler that *walks the release stage machine*, wrapping the
deterministic stage drivers (:mod:`crmbuilder_v2.access.release_orchestration`,
the PI-209 Option-A spine) and delegating the two judgment steps — demands
authoring and the work-task decomposition spec — to injectable **providers**. A
provider is the agent seam: a callable that, given context read from the live
records, returns structured input (a demand-set / a decomposition spec). The
default providers spawn an LLM (see :func:`anthropic_providers`); tests inject
deterministic stubs, so the whole loop is provable end-to-end without a network.

Scope of this first slice: drive a frozen release through
``reconciliation → architecture_planning → ready`` on provider-produced input.
The development lane (``ready`` onward) is the existing ADO runtime under the
release gates — out of this slice (PI-220+). The loop never reimplements
reconcile / version / gate logic (AL-5); it arranges substrate calls.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from crmbuilder_v2.access import planning
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.engagement_scope import active_engagement
from crmbuilder_v2.access.vocab import SYSTEM_AREA_RANKS as _SYSTEM_AREA_RANKS

# ---------------------------------------------------------------------------
# Provider seams (the agent boundary)
# ---------------------------------------------------------------------------

# Given {release_identifier, requirements:[{identifier,name,description,
# acceptance_summary}]} → the structured demand-set (reconcile_release shape).
DemandsProvider = Callable[[dict], list[dict]]
# Given {release_identifier, planning_item, designs:[delta_set,...]} → the
# decomposition spec consumed by decompose_planning_item_direct.
DecompositionProvider = Callable[[dict], list[dict]]
# Dev-lane seams (the development-org boundary). PiRunner delivers one in-scope PI
# (drives it to a delivered state, e.g. the ADO runtime → "In Review" under the
# file-lock gate). GateRunner runs a release-level (integration) gate ("qa" /
# "testing") and returns whether it passed.
PiRunner = Callable[[str, str], None]          # (release_identifier, planning_item)
GateRunner = Callable[[str, str], bool]        # (release_identifier, stage) -> passed
# Per-area back-half seams (PI-249 / 4f). Each is the area's (area, tier) agent: given
# the per-area context dict, returns the area's design / develop / test outcome (the
# shapes run_area_design / run_area_develop / run_area_test consume). Wiring all three
# enables the per-area dev lane for a release on back_half == "per_area".
AreaProvider = Callable[[dict], dict]          # (ctx) -> outcome


# ---------------------------------------------------------------------------
# Pure decision — unit-testable with no I/O
# ---------------------------------------------------------------------------


class StepKind(str, Enum):
    AWAIT_FREEZE = "await_freeze"        # a deliberate human/PM freeze act is owed
    AUTHOR_DEMANDS = "author_demands"    # reconciliation: no demands yet
    RESOLVE_CONFLICTS = "resolve_conflicts"  # PAUSE — governed decisions owed
    AWAIT_RECONCILIATION_REVIEW = "await_reconciliation_review"  # PAUSE — human review of the change-set owed
    ADVANCE_RECONCILIATION = "advance_reconciliation"
    PLAN = "plan"                        # author designs + decompose PIs
    AWAIT_ARCHITECTURE_REVIEW = "await_architecture_review"  # PAUSE — human review of the designs owed
    FINALIZE = "finalize"                # readiness + interactive→ado + enter ready
    # --- development lane (the dev-lane delegation) ---
    ENTER_LANE = "enter_lane"            # ready → development (single-occupancy gate)
    DEVELOP = "develop"                  # per-PI: run the next eligible in-scope PI via ADO
    # --- per-area back half (PI-249 / 4f; when release_back_half == "per_area") ---
    RUN_AREA_DESIGN = "run_area_design"  # fan out one Design task per touched area
    AWAIT_DESIGN_REVIEW = "await_design_review"  # PAUSE — consolidated human Design Review owed
    RUN_PER_AREA_DEV = "run_per_area_dev"  # Develop → blind Test → bounce loop, then → qa
    TO_QA = "to_qa"                      # all PIs delivered → development → qa
    RUN_QA = "run_qa"                    # release-level QA gate → qa_pass
    TO_TESTING = "to_testing"            # qa passed → qa → testing
    RUN_TEST = "run_test"                # release-level test gate → test_pass
    TO_DEPLOYMENT = "to_deployment"      # tests passed → testing → deployment
    AWAIT_SHIP_APPROVAL = "await_ship_approval"  # PAUSE — human Ship Approval owed (PI-260)
    SHIP = "ship"                        # deployment → shipped (ship gate: revalidations + ship sign-off)
    DONE = "done"                        # planning slice complete / release shipped
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ReleaseStep:
    kind: StepKind
    reason: str | None = None


_PRE_FREEZE = frozenset({"preliminary_planning", "development_planning"})


def decide_next(
    status: str,
    *,
    demands_present: bool,
    has_open_conflicts: bool,
    readiness_ready: bool,
    reconciliation_signed: bool = False,
    architecture_planning_signed: bool = False,
    dev_lane_enabled: bool = False,
    all_pis_delivered: bool = False,
    qa_passed: bool = False,
    test_passed: bool = False,
    back_half: str = "per_pi",
    area_specs_present: bool = False,
    design_signed: bool = False,
    ship_signed: bool = False,
) -> ReleaseStep:
    """The next step owed, from the release's status + a few derived flags.

    Pre-freeze the loop only waits (freeze is a deliberate human/PM act, FE-5).
    In ``reconciliation`` it authors demands, pauses for governed conflict
    decisions, or advances. In ``architecture_planning`` it plans then finalizes.

    ``ready`` and the lane stages are the **dev-lane delegation** (AL-4 / §5.2): a
    finished prerequisite graph is walked — each in-scope PI delivered via the ADO
    runtime under the gates, then the release-level QA / test / ship gates. Driven
    only when ``dev_lane_enabled`` (a pi_runner is wired); otherwise ``ready`` is
    the planning-slice boundary (DONE).
    """
    if status in _PRE_FREEZE:
        return ReleaseStep(
            StepKind.AWAIT_FREEZE,
            "release is not frozen yet — freeze is a deliberate human/PM act",
        )
    if status == "reconciliation":
        if not demands_present:
            return ReleaseStep(StepKind.AUTHOR_DEMANDS)
        if has_open_conflicts:
            return ReleaseStep(
                StepKind.RESOLVE_CONFLICTS,
                "open reconciliation conflict(s) need governed decisions",
            )
        if not reconciliation_signed:
            return ReleaseStep(
                StepKind.AWAIT_RECONCILIATION_REVIEW,
                "reconciled change-set needs a human review sign-off (PI-238)",
            )
        return ReleaseStep(StepKind.ADVANCE_RECONCILIATION)
    if status == "architecture_planning":
        if not readiness_ready:
            return ReleaseStep(StepKind.PLAN)
        if not architecture_planning_signed:
            return ReleaseStep(
                StepKind.AWAIT_ARCHITECTURE_REVIEW,
                "authored designs need a human review sign-off (PI-238)",
            )
        return ReleaseStep(StepKind.FINALIZE)
    # --- development lane ---
    if not dev_lane_enabled:
        return ReleaseStep(
            StepKind.DONE, f"status {status!r} — planning slice complete"
        )
    if status == "ready":
        return ReleaseStep(StepKind.ENTER_LANE)
    if status == "development":
        if back_half == "per_area":
            # The matrix back half (PI-249 / 4f): Design fan-out → consolidated Design
            # Review (human pause) → Develop → blind Test → bounce loop. The
            # RUN_PER_AREA_DEV handler advances development → qa on success, so a clean
            # run falls through to the release-level QA/test gates below (two-level).
            if not area_specs_present:
                return ReleaseStep(StepKind.RUN_AREA_DESIGN)
            if not design_signed:
                return ReleaseStep(
                    StepKind.AWAIT_DESIGN_REVIEW,
                    "per-area design specs need a consolidated human Design Review "
                    "sign-off (PI-246)",
                )
            return ReleaseStep(StepKind.RUN_PER_AREA_DEV)
        return ReleaseStep(
            StepKind.TO_QA if all_pis_delivered else StepKind.DEVELOP
        )
    if status == "qa":
        return ReleaseStep(StepKind.TO_TESTING if qa_passed else StepKind.RUN_QA)
    if status == "testing":
        return ReleaseStep(
            StepKind.TO_DEPLOYMENT if test_passed else StepKind.RUN_TEST
        )
    if status == "deployment":
        # Ship Approval is the closing human commit, symmetric to freeze (PI-260):
        # the scheduler pauses at deployment until a fresh human ship sign-off exists,
        # then performs the deployment → shipped transition (gated on revalidations +
        # that sign-off).
        if not ship_signed:
            return ReleaseStep(
                StepKind.AWAIT_SHIP_APPROVAL,
                "shippable release needs a human Ship Approval sign-off (PI-260)",
            )
        return ReleaseStep(StepKind.SHIP)
    return ReleaseStep(StepKind.DONE, f"status {status!r} (shipped / terminal)")


# ---------------------------------------------------------------------------
# Config + report
# ---------------------------------------------------------------------------


@dataclass
class ReleaseSchedulerConfig:
    release_identifier: str
    demands_provider: DemandsProvider
    decomposition_provider: DecompositionProvider
    authored_by: str = "AGP-release-planning"
    max_steps: int = 24
    # Dev-lane delegation (optional). When pi_runner is set, the loop drives past
    # `ready` through development → qa → testing → deployment → shipped; otherwise
    # it stops at `ready` (the planning slice). gate_runner runs the release-level
    # QA/test gates; when unset the loop pauses at qa for a human/release-QA agent.
    pi_runner: PiRunner | None = None
    gate_runner: GateRunner | None = None
    delivered_statuses: tuple[str, ...] = ("In Review", "Resolved")
    # Per-area back half (PI-249 / 4f). When a release is on back_half == "per_area"
    # and all three are wired, the development stage runs the per-area matrix (Design
    # fan-out → Design Review pause → Develop → blind Test → bounce) instead of the
    # per-PI pi_runner. Left None for the legacy per-PI path.
    design_provider: AreaProvider | None = None
    develop_provider: AreaProvider | None = None
    test_provider: AreaProvider | None = None
    per_area_max_rounds: int = 3


@dataclass
class ReleaseRunReport:
    release_identifier: str
    steps: list[str] = field(default_factory=list)
    final_status: str | None = None
    stopped_reason: str | None = None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class ReleaseScheduler:
    """Walks one release through the pipeline using the injected agent seams.

    Read-decide in a session, then execute outside it — the development-stage ADO
    delegation (pi_runner) and the LLM/gate seams are long-running and spawn agents
    that hit the API, so they must not hold the DB session open.
    """

    _HALTS = frozenset({
        StepKind.AWAIT_FREEZE, StepKind.RESOLVE_CONFLICTS,
        StepKind.AWAIT_RECONCILIATION_REVIEW, StepKind.AWAIT_ARCHITECTURE_REVIEW,
        StepKind.AWAIT_DESIGN_REVIEW, StepKind.AWAIT_SHIP_APPROVAL,
        StepKind.DONE, StepKind.BLOCKED,
    })

    def __init__(self, config: ReleaseSchedulerConfig):
        self.cfg = config

    def run(self) -> ReleaseRunReport:
        # Scope every in-process session_scope() write below to the engagement
        # the release actually lives in, so engagement-scoped rows
        # (release_demands, reconciliation records, …) get a non-NULL
        # engagement_id stamped by the flush hook instead of failing the NOT
        # NULL constraint. Derived from the release row itself — when it has no
        # engagement_id (unscoped data, e.g. tests) the contextvar stays None
        # and the scope filter is dormant, exactly as before. (The dev-lane ADO
        # runner is scoped separately via its X-Engagement header.)
        with active_engagement(self._release_engagement()):
            return self._run()

    def _release_engagement(self) -> str | None:
        """The release's own engagement_id (read unscoped), or None when unset."""
        from crmbuilder_v2.access.repositories import releases

        with session_scope() as s:
            rel = releases.get_release(s, self.cfg.release_identifier)
        return (rel or {}).get("engagement_id")

    def _run(self) -> ReleaseRunReport:
        rid = self.cfg.release_identifier
        report = ReleaseRunReport(release_identifier=rid)
        # The dev lane runs when the per-PI runner is wired, OR when the per-area
        # back-half seams are all wired (PI-249) — either path drives past `ready`.
        dev_lane = self.cfg.pi_runner is not None or self._per_area_seams_wired()

        for _ in range(self.cfg.max_steps):
            snap = self._read_state(rid)
            step = decide_next(
                snap["status"],
                demands_present=snap["demands_present"],
                has_open_conflicts=snap["has_open_conflicts"],
                readiness_ready=snap["readiness_ready"],
                reconciliation_signed=snap["reconciliation_signed"],
                architecture_planning_signed=snap["architecture_planning_signed"],
                ship_signed=snap["ship_signed"],
                dev_lane_enabled=dev_lane,
                all_pis_delivered=snap["all_pis_delivered"],
                qa_passed=snap["qa_passed"],
                test_passed=snap["test_passed"],
                back_half=snap["back_half"],
                area_specs_present=snap["area_specs_present"],
                design_signed=snap["design_signed"],
            )
            report.steps.append(f"{snap['status']} → {step.kind.value}")
            if step.kind in self._HALTS:
                report.final_status = snap["status"]
                report.stopped_reason = step.reason or step.kind.value
                return report
            halt = self._execute(step, rid)  # executes outside the read session
            if halt is not None:
                report.final_status = self._status(rid)
                report.stopped_reason = halt
                return report

        report.final_status = self._status(rid)
        report.stopped_reason = "max_steps reached"
        return report

    # -- step dispatch ------------------------------------------------------

    def _execute(self, step: ReleaseStep, rid: str) -> str | None:
        """Run one step's effect; return a halt reason, or None to continue."""
        k = StepKind
        if step.kind is k.AUTHOR_DEMANDS:
            self._author_demands(rid)
        elif step.kind is k.ADVANCE_RECONCILIATION:
            self._transition(rid, "architecture_planning")
        elif step.kind is k.PLAN:
            self._plan(rid)
        elif step.kind is k.FINALIZE:
            self._finalize(rid)
        elif step.kind is k.ENTER_LANE:
            self._transition(rid, "development")
        elif step.kind is k.DEVELOP:
            return self._develop_step(rid)
        elif step.kind is k.RUN_AREA_DESIGN:
            return self._run_area_design(rid)
        elif step.kind is k.RUN_PER_AREA_DEV:
            return self._run_per_area_dev(rid)
        elif step.kind is k.TO_QA:
            self._transition(rid, "qa")
        elif step.kind is k.RUN_QA:
            return self._gate(rid, "qa")
        elif step.kind is k.TO_TESTING:
            self._transition(rid, "testing")
        elif step.kind is k.RUN_TEST:
            return self._gate(rid, "testing")
        elif step.kind is k.TO_DEPLOYMENT:
            self._transition(rid, "deployment")
        elif step.kind is k.SHIP:
            self._transition(rid, "shipped")
        return None

    # -- planning handlers --------------------------------------------------

    def _author_demands(self, rid: str) -> None:
        from crmbuilder_v2.access.repositories import release_demands

        with session_scope() as s:
            reqs = _confirmed_requirements(s, rid)
        demands = self.cfg.demands_provider(
            {"release_identifier": rid, "requirements": reqs}
        )
        with session_scope() as s:
            release_demands.clear_demands(s, rid)
            if demands:
                release_demands.add_demands(s, rid, demands, self.cfg.authored_by)
            orch.run_reconciliation(s, rid)

    def _plan(self, rid: str) -> None:
        from crmbuilder_v2.access.repositories import releases

        with session_scope() as s:
            delta_sets = orch.reconciled_delta_sets(s, rid)
            orch.run_architecture_planning(s, rid, delta_sets)
            pending = [
                pi
                for prj in releases._in_scope_projects(s, rid)
                for pi in releases._in_scope_planning_items(s, prj)
                if not releases._pi_workstreams(s, pi)
            ]
        for pi in pending:  # the decomposition agent runs outside the session
            spec = self.cfg.decomposition_provider(
                {"release_identifier": rid, "planning_item": pi, "designs": delta_sets}
            )
            if spec:
                with session_scope() as s:
                    orch.decompose_planning_item_direct(s, pi, spec)

    def _finalize(self, rid: str) -> None:
        with session_scope() as s:
            orch.finalize_planning(s, rid)

    # -- development-lane handlers ------------------------------------------

    def _transition(self, rid: str, to_status: str) -> None:
        from crmbuilder_v2.access.repositories import releases

        with session_scope() as s:
            releases.transition(s, rid, to_status)

    # -- per-area back-half handlers (PI-249 / 4f) --------------------------

    def _per_area_seams_wired(self) -> bool:
        return all((self.cfg.design_provider, self.cfg.develop_provider,
                    self.cfg.test_provider))

    def _run_area_design(self, rid: str) -> str | None:
        """Fan out the per-area Design tasks (PI-245), authoring each area's spec via
        the (area, architect) seam. Loops back; the next iteration pauses for the
        consolidated Design Review."""
        with session_scope() as s:
            orch.run_area_design(s, rid, self.cfg.design_provider)
        return None

    def _run_per_area_dev(self, rid: str) -> str | None:
        """Run the per-area Develop → blind Test → bounce loop (PI-247/248/249). On a
        clean pass, advance development → qa so the next iteration hits the
        release-level QA gate (two-level testing); otherwise halt with the loop's
        status (needs_redesign / develop_blocked / needs_human)."""
        with session_scope() as s:
            out = orch.run_per_area_development(
                s, rid,
                develop_provider=self.cfg.develop_provider,
                test_provider=self.cfg.test_provider,
                max_rounds=self.cfg.per_area_max_rounds,
            )
        if out["status"] == "passed":
            self._transition(rid, "qa")
            return None
        halted = f" (halted on {out['halted_on']})" if out.get("halted_on") else ""
        return f"per-area development did not pass: {out['status']}{halted}"

    def _develop_step(self, rid: str) -> str | None:
        """Deliver the next eligible in-scope PI via the ADO runner (outside any
        session). Returns a halt reason if nothing is eligible or the PI does not
        reach a delivered state."""
        from crmbuilder_v2.access.repositories import planning_items

        with session_scope() as s:
            pi = self._next_eligible_pi(s, rid)
        if pi is None:
            return ("development blocked: no eligible in-scope planning item "
                    "(unmet dependencies among the in-scope items)")
        self.cfg.pi_runner(rid, pi)  # long; spawns ADO agents under the file lock
        with session_scope() as s:
            status = planning_items.get(s, pi)["status"]
        if status not in self.cfg.delivered_statuses:
            return (f"planning item {pi} did not reach a delivered state "
                    f"(status {status!r}); needs attention")
        return None

    def _gate(self, rid: str, stage: str) -> str | None:
        """Run a release-level (integration) QA/test gate via the gate runner, then
        stamp the pass. No runner wired → pause for a human / release-QA agent."""
        from crmbuilder_v2.access.repositories import releases

        if self.cfg.gate_runner is None:
            return (f"release-level {stage} gate owed — wire a gate runner or run it "
                    f"and stamp the pass, then relaunch")
        if not self.cfg.gate_runner(rid, stage):
            return f"release-level {stage} gate failed"
        with session_scope() as s:
            if stage == "qa":
                releases.qa_pass(s, rid)
            else:
                releases.test_pass(s, rid)
        return None

    # -- state reads --------------------------------------------------------

    def _read_state(self, rid: str) -> dict:
        from crmbuilder_v2.access.repositories import (
            area_specs,
            release_demands,
            release_signoffs,
            releases,
        )
        from crmbuilder_v2.access.repositories import reconciliation as recon

        with session_scope() as s:
            rel = releases.get_release(s, rid)
            in_scope = self._in_scope_pis(s, rid)
            delivered = self._delivered_pis(s, in_scope)
            return {
                "status": rel["release_status"],
                "demands_present": bool(release_demands.list_demands(s, rid)),
                "has_open_conflicts": recon.has_open_conflicts(s, rid),
                "readiness_ready": planning.planning_readiness(s, rid)["ready"],
                # Front-half human-review gates (PI-238): a *fresh* sign-off whose
                # fingerprint still matches the current stage output.
                "reconciliation_signed": release_signoffs.fresh_signoff(
                    s, rid, "reconciliation") is not None,
                "architecture_planning_signed": release_signoffs.fresh_signoff(
                    s, rid, "architecture_planning") is not None,
                # Per-area back half (PI-249 / 4f): the mode + the Design-stage flags.
                "back_half": rel.get("release_back_half", "per_pi"),
                "area_specs_present": bool(area_specs.current_specs(s, rid)),
                "design_signed": release_signoffs.fresh_signoff(
                    s, rid, "design") is not None,
                # Closing human commit (PI-260): a fresh ship sign-off whose
                # fingerprint still matches the current shippable state.
                "ship_signed": release_signoffs.fresh_signoff(
                    s, rid, "ship") is not None,
                "all_pis_delivered": bool(in_scope) and delivered == set(in_scope),
                "qa_passed": rel.get("release_qa_passed_at") is not None,
                "test_passed": rel.get("release_test_passed_at") is not None,
            }

    def _status(self, rid: str) -> str:
        from crmbuilder_v2.access.repositories import releases

        with session_scope() as s:
            return releases.get_release(s, rid)["release_status"]

    def _in_scope_pis(self, session, rid: str) -> list[str]:
        from crmbuilder_v2.access.repositories import releases

        return [
            pi
            for prj in releases._in_scope_projects(session, rid)
            for pi in releases._in_scope_planning_items(session, prj)
        ]

    def _delivered_pis(self, session, pis: list[str]) -> set[str]:
        from crmbuilder_v2.access.repositories import planning_items

        out: set[str] = set()
        for pi in pis:
            try:
                if planning_items.get(session, pi)["status"] in self.cfg.delivered_statuses:
                    out.add(pi)
            except Exception:
                continue
        return out

    def _next_eligible_pi(self, session, rid: str) -> str | None:
        """An undelivered in-scope PI whose in-scope blockers are all delivered
        (the finished prerequisite graph is walked in dependency order, §5.2)."""
        from crmbuilder_v2.access.repositories import _governance as gov

        in_scope = self._in_scope_pis(session, rid)
        delivered = self._delivered_pis(session, in_scope)
        in_scope_set = set(in_scope)
        for pi in in_scope:
            if pi in delivered:
                continue
            blockers = {
                e.target_id
                for e in gov.outbound_edges(
                    session, source_type="planning_item", source_id=pi,
                    relationship="blocked_by", target_type="planning_item",
                )
            } & in_scope_set
            if blockers <= delivered:
                return pi
        return None


# ---------------------------------------------------------------------------
# Real LLM providers (the agent seam) + CLI
# ---------------------------------------------------------------------------

_MODEL = "claude-opus-4-8"  # per the project's default model (claude-api skill)

# The valid System areas, as a Literal so the decomposition agent's structured
# output is forced to a real area (it otherwise emits friendly names like
# "Data Model"). Built at module scope so Pydantic resolves the annotation.
_AREA_LITERAL = Literal[tuple(sorted(_SYSTEM_AREA_RANKS))]  # type: ignore[valid-type]


# --- the agents' structured-output schemas (module-level so they are testable) ---
# Literal enums + a JSON-typed value union so Anthropic structured output FORCES
# valid values — the LLM otherwise emits plausible-but-invalid ones (op "ensure",
# area "Data Model", bare untyped `value`) that the access layer then rejects.
class _Demand(BaseModel):
    requirement_identifier: str
    artifact_type: Literal["entity", "field", "persona", "process", "association"]
    artifact_identifier: str
    field: str = ""
    facet: str | None = None
    op: Literal["set", "add", "remove"]
    value: str | int | float | bool | list[str] | None = None


class _DemandSet(BaseModel):
    demands: list[_Demand]


class _WorkTask(BaseModel):
    title: str
    area: _AREA_LITERAL  # forced to a valid System area
    description: str | None = None


class _Workstream(BaseModel):
    phase_type: Literal["Design", "Develop", "Test"]
    title: str
    description: str | None = None
    work_tasks: list[_WorkTask]


class _Decomposition(BaseModel):
    workstreams: list[_Workstream]

_DEMANDS_SYSTEM = """\
You are the model-area Reconciliation Agent for a multi-agent release pipeline. \
You read a release's confirmed requirements and express each as structured \
requirement->design deltas ("demands") against the data model. Each demand names \
the artifact it changes and the single (field, facet) it sets, adds to, or removes. \
Author the smallest faithful set of demands that satisfies the requirements; never \
invent changes a requirement does not call for. Use op "set" for a scalar facet, \
"add" for a set-valued facet (e.g. enum options), "remove" to drop a field. Use \
field "" for an artifact-level attribute. artifact_type is one of \
entity|field|persona|process|association."""

_DECOMPOSE_SYSTEM = """\
You are the Architect Planning Agent for a multi-agent release pipeline. Given the \
versioned design deltas for one planning item, produce the workstreams and work \
tasks that implement them, sequenced as Design -> Develop -> Test. Each work task \
covers ONE system area (storage, access, api, mcp, ui, or an engagement area). Keep \
the decomposition minimal and buildable; the work tasks are what the release is \
later tested against."""


def _registry_system_prompt(area: str, tier: str) -> str | None:
    """The composed system prompt for an (area, tier) system profile from the
    registry (PI-221), or None if no such profile exists or the registry is
    unreachable — letting the runtime drive the durable, learnable registry
    prompts (AL-7) with the inline constants as a fallback.
    """
    try:
        from sqlalchemy import select

        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.models import AgentProfileRow
        from crmbuilder_v2.access.repositories import registry_resolver

        with session_scope() as s:
            row = s.scalars(
                select(AgentProfileRow).where(
                    AgentProfileRow.area == area,
                    AgentProfileRow.tier == tier,
                    AgentProfileRow.engagement_id.is_(None),
                    AgentProfileRow.status == "active",
                )
            ).first()
            if row is None:
                return None
            return registry_resolver.resolve_contract(s, row.identifier)["system_prompt"]
    except Exception:
        return None


def anthropic_providers(model: str = _MODEL):
    """The real agent seam: LLM-backed demands + decomposition providers.

    Uses the Anthropic SDK structured-output path (``messages.parse``) so the
    model returns validated JSON. Imported lazily so the runtime core (and its
    tests) carry no anthropic dependency. Not unit-tested — exercised live.
    """
    import anthropic

    client = anthropic.Anthropic()
    # Prefer the durable registry prompts (PI-221) over the inline fallbacks.
    demands_system = _registry_system_prompt("model", "architect") or _DEMANDS_SYSTEM
    decompose_system = (
        _registry_system_prompt("planning", "architect") or _DECOMPOSE_SYSTEM
    )

    def _parse(system, user, schema, *, stage, **attribution):
        resp = client.messages.parse(
            model=model, max_tokens=16000,
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            system=system, messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        # Record the call's spend (best-effort; relies on the scheduler's ambient
        # active-engagement context — PI-264).
        from crmbuilder_v2.scheduler import cost_capture

        cost_capture.record_sdk_usage(
            getattr(resp, "usage", None), model, stage=stage, **attribution
        )
        return resp.parsed_output

    def demands_provider(context: dict) -> list[dict]:
        out = _parse(
            demands_system,
            "Author the demand-set for release "
            f"{context['release_identifier']} from these confirmed requirements:\n"
            + json.dumps(context["requirements"], indent=2),
            _DemandSet,
            stage="demands",
            release_identifier=context.get("release_identifier"),
        )
        return [d.model_dump() for d in out.demands]

    def decomposition_provider(context: dict) -> list[dict]:
        out = _parse(
            decompose_system,
            f"Decompose planning item {context['planning_item']} of release "
            f"{context['release_identifier']}. The versioned design deltas:\n"
            + json.dumps(context["designs"], indent=2),
            _Decomposition,
            stage="decomposition",
            release_identifier=context.get("release_identifier"),
            planning_item=context.get("planning_item"),
        )
        return [w.model_dump() for w in out.workstreams]

    return demands_provider, decomposition_provider


def ado_pi_runner(
    *,
    api_base: str = "http://127.0.0.1:8765",
    engagement: str = "CRMBUILDER",
    repo_root: str = ".",
    base_branch: str = "main",
    max_concurrent: int = 2,
    agent_timeout: int = 1800,
) -> PiRunner:
    """The real dev-org delegation seam: deliver one in-scope PI by running the ADO
    runtime over its phases with the file-lock backstop engaged (PI-220). The PI is
    driven to ``In Review``; the release loop reads its status to confirm delivery.
    """
    def _run(release_identifier: str, planning_item: str) -> None:
        from crmbuilder_v2.scheduler.ado_scheduler import (
            AdoScheduler,
            AdoSchedulerConfig,
        )

        AdoScheduler(AdoSchedulerConfig(
            planning_item=planning_item, api_base=api_base, engagement=engagement,
            repo_root=repo_root, base_branch=base_branch,
            max_concurrent=max_concurrent, agent_timeout=agent_timeout,
            enable_file_locks=True,
        )).run()

    return _run


def main(argv: list[str] | None = None) -> int:
    """CLI: drive a release with the agent layer. Default = the planning slice
    (reconciliation -> ready); ``--dev-lane`` continues through the development lane
    to shipped, delegating each in-scope PI to the ADO runtime under the file lock.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-release",
        description="Drive a release through the pipeline with the agent layer.",
    )
    parser.add_argument("release_identifier", help="REL-NNN")
    parser.add_argument("--authored-by", default="AGP-release-planning")
    parser.add_argument("--max-steps", type=int, default=24)
    parser.add_argument("--dev-lane", action="store_true",
                        help="continue past 'ready' through the development lane "
                        "(delegates each in-scope PI to the ADO runtime)")
    parser.add_argument("--manual-gates", action="store_true",
                        help="with --dev-lane, pause at the release QA/test gates for "
                        "a human instead of running the LLM Release Lead judge")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base-branch", default="main")
    parser.add_argument("--max-concurrent", type=int, default=2)
    parser.add_argument("--engagement", default="CRMBUILDER",
                        help="engagement identifier (ENG-NNN) or code the release "
                        "lives in; scopes the loop's in-process writes")
    args = parser.parse_args(argv)

    demands_provider, decomposition_provider = anthropic_providers()
    pi_runner = ado_pi_runner(
        repo_root=args.repo_root, base_branch=args.base_branch,
        max_concurrent=args.max_concurrent, engagement=args.engagement,
    ) if args.dev_lane else None
    gate_runner = None
    if args.dev_lane and not args.manual_gates:
        from crmbuilder_v2.scheduler.release_gate import anthropic_gate_runner

        gate_runner = anthropic_gate_runner()
    report = ReleaseScheduler(ReleaseSchedulerConfig(
        release_identifier=args.release_identifier,
        demands_provider=demands_provider,
        decomposition_provider=decomposition_provider,
        authored_by=args.authored_by,
        max_steps=args.max_steps,
        pi_runner=pi_runner,
        gate_runner=gate_runner,
    )).run()
    print(json.dumps({
        "release": report.release_identifier,
        "steps": report.steps,
        "final_status": report.final_status,
        "stopped_reason": report.stopped_reason,
    }, indent=2))
    return 0


def _confirmed_requirements(session, rid: str) -> list[dict]:
    """The release's in-scope, confirmed requirements (the demands agent's input)."""
    from crmbuilder_v2.access._helpers import get_by_identifier
    from crmbuilder_v2.access.models import Requirement
    from crmbuilder_v2.access.repositories import releases

    out: list[dict] = []
    seen: set[str] = set()
    for prj in releases._in_scope_projects(session, rid):
        for pi in releases._in_scope_planning_items(session, prj):
            for req in releases._in_scope_requirements(session, pi):
                if req in seen:
                    continue
                seen.add(req)
                row = get_by_identifier(
                    session, Requirement, Requirement.requirement_identifier, req
                )
                if row is None or row.requirement_status != "confirmed":
                    continue
                out.append({
                    "identifier": req,
                    "name": row.requirement_name,
                    "description": row.requirement_description,
                    "acceptance_summary": row.requirement_acceptance_summary,
                })
    return out
