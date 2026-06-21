"""Release-level QA / test gate runner — the Release Lead judge (PI-223, PRJ-033).

The dev-lane delegation (PI-222) drives a release to its release-level (integration)
QA and test gates and asks a ``gate_runner`` whether each passed. This is the real
implementation of that seam (§8): an LLM **Release Lead** (area=release, tier=
pi_lead) judges the *assembled* release against its confirmed requirements, the
authored vN+1 designs, and the delivered work — grounded in the real records, not a
rubber stamp.

The gate has two parts:

- a **deterministic fail-closed floor** (``release_gate_context`` + the guard): there
  must be confirmed in-scope requirements to verify against and authored designs to
  verify — "nothing required goes unverified" (§8). No requirements / no designs →
  the gate cannot pass.
- an **LLM judgment** on top: QA = does the assembled design *conform* to and fully
  *cover* every requirement with no cross-area contradiction; Testing = do the key
  processes / requirements hold *end-to-end* across areas (a green per-area unit is
  not a working cross-area process).

The judge is an injectable callable so the floor + context + verdict-mapping are
deterministic and testable; ``anthropic_gate_runner`` supplies the real Anthropic
(structured-output) judge, resolving the Release Lead prompt from the registry
(AGP-005) with an inline fallback.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import BaseModel

from crmbuilder_v2.access.db import session_scope

# The judge: given the grounded gate context, return {passed, summary, findings}.
GateJudge = Callable[[dict], dict]

_MODEL = "claude-opus-4-8"


# The Release Lead verdict schema (module-level so it is testable for Anthropic
# structured-output compatibility, like the planning-agent schemas).
class _Finding(BaseModel):
    requirement_identifier: str | None = None
    issue: str
    severity: str = "major"


class _Verdict(BaseModel):
    passed: bool
    summary: str
    findings: list[_Finding] = []

_GATE_SYSTEM = """\
You are the Release Lead for a multi-agent release pipeline, performing a \
release-level (integration) gate on the ASSEMBLED release — not a per-area unit \
check. You are given the release's confirmed requirements, the authored vN+1 \
designs, and the delivered work (planning items + the areas they touched). Judge \
whether the gate passes and report any finding that should block the release or \
feed rework. The bar: nothing required goes unverified, and a green per-area unit \
is NOT a working cross-area process."""

_STAGE_INSTRUCTION = {
    "qa": "QA (conformance): does the assembled design CONFORM to the quality specs "
    "and fully COVER every confirmed requirement, with no contradiction across "
    "areas? Fail if any requirement is unaddressed or two areas' designs conflict.",
    "testing": "Testing (integration function): do the key processes and requirements "
    "hold END-TO-END across areas (e.g. UI -> API -> business logic -> data)? Fail if "
    "a key process cannot be traced through the delivered work across the areas it "
    "needs, even when each area looks individually complete.",
}


def release_gate_context(release_identifier: str, stage: str) -> dict:
    """Gather the grounding for a release-level gate (deterministic, no LLM).

    Returns ``{stage, requirements, designs, delivered, missing_designs}`` — the
    confirmed in-scope requirements (id/name/acceptance), the authored vN+1 designs
    (artifact + snapshot), the delivered in-scope planning items + the areas they
    touched, and the requirements with no authored design covering them.
    """
    from crmbuilder_v2.access._helpers import get_by_identifier
    from crmbuilder_v2.access.models import Requirement
    from crmbuilder_v2.access.repositories import (
        artifact_versions,
        planning_items,
        releases,
        work_tasks,
    )

    with session_scope() as s:
        requirements: list[dict] = []
        delivered: list[dict] = []
        seen_req: set[str] = set()
        for prj in releases._in_scope_projects(s, release_identifier):
            for pi in releases._in_scope_planning_items(s, prj):
                row = planning_items.get(s, pi)
                areas: set[str] = set()
                for ws in releases._pi_workstreams(s, pi):
                    for wt in releases._ws_work_tasks(s, ws):
                        area = work_tasks.get_work_task(s, wt).get("work_task_area")
                        if area:
                            areas.add(area)
                delivered.append(
                    {"planning_item": pi, "status": row["status"],
                     "areas": sorted(areas)}
                )
                for req in releases._in_scope_requirements(s, pi):
                    if req in seen_req:
                        continue
                    seen_req.add(req)
                    rr = get_by_identifier(
                        s, Requirement, Requirement.requirement_identifier, req
                    )
                    if rr is None or rr.requirement_status != "confirmed":
                        continue
                    requirements.append({
                        "identifier": req,
                        "name": rr.requirement_name,
                        "acceptance": rr.requirement_acceptance_summary,
                    })
        designs = [
            {"artifact_type": v["artifact_type"],
             "artifact_identifier": v["artifact_identifier"],
             "version": v["version_number"], "snapshot": v["snapshot"]}
            for v in artifact_versions.versions_for_release(s, release_identifier)
        ]
    return {
        "release_identifier": release_identifier,
        "stage": stage,
        "requirements": requirements,
        "designs": designs,
        "delivered": delivered,
    }


def make_gate_runner(judge: GateJudge, *, log: Callable[[str], None] = print):
    """The gate runner core: gather context, enforce the fail-closed floor, then ask
    the judge. Returns a ``(release_identifier, stage) -> bool`` gate runner."""
    def _gate(release_identifier: str, stage: str) -> bool:
        ctx = release_gate_context(release_identifier, stage)
        # Fail-closed floor: nothing to verify against / nothing verified -> no pass.
        if not ctx["requirements"]:
            log(f"  [release gate:{stage}] FAIL — no confirmed requirements to verify")
            return False
        if not ctx["designs"]:
            log(f"  [release gate:{stage}] FAIL — no authored designs to verify")
            return False
        verdict = judge(ctx)
        passed = bool(verdict.get("passed"))
        log(f"  [release gate:{stage}] {'PASS' if passed else 'FAIL'} — "
            f"{verdict.get('summary', '')}")
        for f in verdict.get("findings") or []:
            log(f"      finding [{f.get('severity', '?')}] "
                f"{f.get('requirement_identifier') or ''}: {f.get('issue', '')}")
        return passed

    return _gate


def anthropic_gate_runner(model: str = _MODEL, *, log: Callable[[str], None] = print):
    """The real Release Lead gate: an Anthropic structured-output judge over the
    assembled release. Imported lazily so the runtime core carries no dependency."""
    def _judge(ctx: dict) -> dict:
        import anthropic

        from crmbuilder_v2.scheduler.release_scheduler import _registry_system_prompt

        system = _registry_system_prompt("release", "pi_lead") or _GATE_SYSTEM
        instruction = _STAGE_INSTRUCTION.get(ctx["stage"], _STAGE_INSTRUCTION["qa"])
        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=model, max_tokens=16000,
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
            system=system,
            messages=[{"role": "user", "content":
                       f"Release-level gate for {ctx['release_identifier']}.\n\n"
                       f"{instruction}\n\nThe assembled release:\n"
                       + json.dumps({k: ctx[k] for k in
                                     ("requirements", "designs", "delivered")}, indent=2)}],
            output_format=_Verdict,
        )
        return resp.parsed_output.model_dump()

    return make_gate_runner(_judge, log=log)
