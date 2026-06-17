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

from crmbuilder_v2.access import planning
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope

# ---------------------------------------------------------------------------
# Provider seams (the agent boundary)
# ---------------------------------------------------------------------------

# Given {release_identifier, requirements:[{identifier,name,description,
# acceptance_summary}]} → the structured demand-set (reconcile_release shape).
DemandsProvider = Callable[[dict], list[dict]]
# Given {release_identifier, planning_item, designs:[delta_set,...]} → the
# decomposition spec consumed by decompose_planning_item_direct.
DecompositionProvider = Callable[[dict], list[dict]]


# ---------------------------------------------------------------------------
# Pure decision — unit-testable with no I/O
# ---------------------------------------------------------------------------


class StepKind(str, Enum):
    AWAIT_FREEZE = "await_freeze"        # a deliberate human/PM freeze act is owed
    AUTHOR_DEMANDS = "author_demands"    # reconciliation: no demands yet
    RESOLVE_CONFLICTS = "resolve_conflicts"  # PAUSE — governed decisions owed
    ADVANCE_RECONCILIATION = "advance_reconciliation"
    PLAN = "plan"                        # author designs + decompose PIs
    FINALIZE = "finalize"                # readiness + interactive→ado + enter ready
    DONE = "done"                        # planning slice complete (status ready+)
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
) -> ReleaseStep:
    """The next step owed, from the release's status + a few derived flags.

    Pre-freeze the loop only waits (freeze is a deliberate human/PM act, FE-5).
    In ``reconciliation`` it authors demands, pauses for governed conflict
    decisions, or advances. In ``architecture_planning`` it plans then finalizes.
    ``ready`` and beyond are the development lane — out of the planning slice.
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
        return ReleaseStep(StepKind.ADVANCE_RECONCILIATION)
    if status == "architecture_planning":
        if not readiness_ready:
            return ReleaseStep(StepKind.PLAN)
        return ReleaseStep(StepKind.FINALIZE)
    return ReleaseStep(StepKind.DONE, f"status {status!r} is beyond the planning slice")


# ---------------------------------------------------------------------------
# Config + report
# ---------------------------------------------------------------------------


@dataclass
class ReleaseRuntimeConfig:
    release_identifier: str
    demands_provider: DemandsProvider
    decomposition_provider: DecompositionProvider
    authored_by: str = "AGP-release-planning"
    max_steps: int = 24


@dataclass
class ReleaseRunReport:
    release_identifier: str
    steps: list[str] = field(default_factory=list)
    final_status: str | None = None
    stopped_reason: str | None = None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------


class ReleaseRuntime:
    """Walks one release through the planning slice using the injected providers."""

    def __init__(self, config: ReleaseRuntimeConfig):
        self.cfg = config

    def run(self) -> ReleaseRunReport:
        from crmbuilder_v2.access.repositories import reconciliation as recon
        from crmbuilder_v2.access.repositories import (
            release_demands,
            releases,
        )

        rid = self.cfg.release_identifier
        report = ReleaseRunReport(release_identifier=rid)
        # Stops that need an external actor (human / governed decision) or are done.
        _HALTS = {
            StepKind.AWAIT_FREEZE,
            StepKind.RESOLVE_CONFLICTS,
            StepKind.DONE,
            StepKind.BLOCKED,
        }

        for _ in range(self.cfg.max_steps):
            with session_scope() as s:
                status = releases.get_release(s, rid)["release_status"]
                demands_present = bool(release_demands.list_demands(s, rid))
                has_open = recon.has_open_conflicts(s, rid)
                readiness = planning.planning_readiness(s, rid)
                step = decide_next(
                    status,
                    demands_present=demands_present,
                    has_open_conflicts=has_open,
                    readiness_ready=readiness["ready"],
                )
                report.steps.append(f"{status} → {step.kind.value}")

                if step.kind in _HALTS:
                    report.final_status = status
                    report.stopped_reason = step.reason or step.kind.value
                    return report

                if step.kind is StepKind.AUTHOR_DEMANDS:
                    self._author_demands(s, rid)
                elif step.kind is StepKind.ADVANCE_RECONCILIATION:
                    releases.transition(s, rid, "architecture_planning")
                elif step.kind is StepKind.PLAN:
                    self._plan(s, rid)
                elif step.kind is StepKind.FINALIZE:
                    orch.finalize_planning(s, rid)

        with session_scope() as s:
            from crmbuilder_v2.access.repositories import releases

            report.final_status = releases.get_release(s, rid)["release_status"]
        report.stopped_reason = "max_steps reached"
        return report

    # -- handlers -----------------------------------------------------------

    def _author_demands(self, session, rid: str) -> None:
        from crmbuilder_v2.access.repositories import release_demands

        context = {
            "release_identifier": rid,
            "requirements": _confirmed_requirements(session, rid),
        }
        demands = self.cfg.demands_provider(context)
        release_demands.clear_demands(session, rid)
        if demands:
            release_demands.add_demands(session, rid, demands, self.cfg.authored_by)
        orch.run_reconciliation(session, rid)

    def _plan(self, session, rid: str) -> None:
        from crmbuilder_v2.access.repositories import releases

        delta_sets = orch.reconciled_delta_sets(session, rid)
        orch.run_architecture_planning(session, rid, delta_sets)
        for prj in releases._in_scope_projects(session, rid):
            for pi in releases._in_scope_planning_items(session, prj):
                if releases._pi_workstreams(session, pi):
                    continue  # already decomposed
                spec = self.cfg.decomposition_provider({
                    "release_identifier": rid,
                    "planning_item": pi,
                    "designs": delta_sets,
                })
                if spec:
                    orch.decompose_planning_item_direct(session, pi, spec)


# ---------------------------------------------------------------------------
# Real LLM providers (the agent seam) + CLI
# ---------------------------------------------------------------------------

_MODEL = "claude-opus-4-8"  # per the project's default model (claude-api skill)

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


def anthropic_providers(model: str = _MODEL):
    """The real agent seam: LLM-backed demands + decomposition providers.

    Uses the Anthropic SDK structured-output path (``messages.parse``) so the
    model returns validated JSON. Imported lazily so the runtime core (and its
    tests) carry no anthropic dependency. Not unit-tested — exercised live.
    """
    import anthropic
    from pydantic import BaseModel

    class _Demand(BaseModel):
        requirement_identifier: str
        artifact_type: str
        artifact_identifier: str
        field: str = ""
        facet: str | None = None
        op: str
        value: object | None = None

    class _DemandSet(BaseModel):
        demands: list[_Demand]

    class _WorkTask(BaseModel):
        title: str
        area: str
        description: str | None = None

    class _Workstream(BaseModel):
        phase_type: str
        title: str
        description: str | None = None
        work_tasks: list[_WorkTask]

    class _Decomposition(BaseModel):
        workstreams: list[_Workstream]

    client = anthropic.Anthropic()

    def _parse(system, user, schema):
        resp = client.messages.parse(
            model=model, max_tokens=16000,
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            system=system, messages=[{"role": "user", "content": user}],
            output_format=schema,
        )
        return resp.parsed_output

    def demands_provider(context: dict) -> list[dict]:
        out = _parse(
            _DEMANDS_SYSTEM,
            "Author the demand-set for release "
            f"{context['release_identifier']} from these confirmed requirements:\n"
            + json.dumps(context["requirements"], indent=2),
            _DemandSet,
        )
        return [d.model_dump() for d in out.demands]

    def decomposition_provider(context: dict) -> list[dict]:
        out = _parse(
            _DECOMPOSE_SYSTEM,
            f"Decompose planning item {context['planning_item']} of release "
            f"{context['release_identifier']}. The versioned design deltas:\n"
            + json.dumps(context["designs"], indent=2),
            _Decomposition,
        )
        return [w.model_dump() for w in out.workstreams]

    return demands_provider, decomposition_provider


def main(argv: list[str] | None = None) -> int:
    """CLI: drive one release through the planning slice (reconciliation -> ready)."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="crmbuilder-v2-release",
        description="Drive a release through the planning slice with the agent layer.",
    )
    parser.add_argument("release_identifier", help="REL-NNN")
    parser.add_argument("--authored-by", default="AGP-release-planning")
    parser.add_argument("--max-steps", type=int, default=24)
    args = parser.parse_args(argv)

    demands_provider, decomposition_provider = anthropic_providers()
    report = ReleaseRuntime(ReleaseRuntimeConfig(
        release_identifier=args.release_identifier,
        demands_provider=demands_provider,
        decomposition_provider=decomposition_provider,
        authored_by=args.authored_by,
        max_steps=args.max_steps,
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
