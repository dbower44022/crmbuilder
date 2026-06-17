"""Release-level QA/test gate runner — PI-223 (PRJ-033), §8.

The deterministic core of the Release Lead gate: context gathering (requirements +
authored designs + delivered work), the fail-closed floor (nothing to verify
against / nothing verified → no pass), and the verdict→bool mapping. The LLM judge
is injected as a stub so this is deterministic; the real Anthropic judge is the seam.
See release-pipeline-agent-layer-architecture.md §6 and PRD §8.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Requirement
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    planning_items,
    projects,
    references,
    releases,
    work_tasks,
    workstreams,
)
from crmbuilder_v2.runtime import release_gate

_SUMMARY = (
    "A planning item used by the release-gate tests; it carries enough audience-facing "
    "text to satisfy the 200-800 character executive-summary the planning_items "
    "repository enforces on create, so the scaffolding builds a valid in-scope item the "
    "release-level QA/test gate can verify the assembled design and delivered work for."
)


def _edge(s, st, si, rel, tt, ti):
    references.create(s, source_type=st, source_id=si, target_type=tt, target_id=ti,
                      relationship=rel)


def _scaffold(s, *, with_design=True, confirmed=True):
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"]
    req = Requirement(requirement_identifier="REQ-950",
                      requirement_name="Email required", requirement_description="d",
                      requirement_acceptance_summary="email.required=true",
                      requirement_priority="must",
                      requirement_status="confirmed" if confirmed else "candidate",
                      requirement_origin="human_defined", requirement_review_state="current")
    s.add(req)
    s.flush()
    pi = planning_items.create(s, title="T", item_type="pending_work",
                               executive_summary=_SUMMARY, execution_mode="ado")["identifier"]
    ws = workstreams.create_workstream(s, phase_type="Develop", title="B")[
        "workstream_identifier"]
    wt = work_tasks.create_work_task(s, title="x", area="storage")["work_task_identifier"]
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    _edge(s, "project", prj, "project_belongs_to_release", "release", rel)
    _edge(s, "planning_item", pi, "planning_item_belongs_to_project", "project", prj)
    _edge(s, "planning_item", pi, "planning_item_implements_requirement", "requirement", "REQ-950")
    _edge(s, "workstream", ws, "workstream_belongs_to_planning_item", "planning_item", pi)
    _edge(s, "work_task", wt, "work_task_belongs_to_workstream", "workstream", ws)
    if with_design:
        artifact_versions.snapshot(
            s, artifact_type="entity", artifact_identifier="ENT-Contact",
            release_identifier=rel,
            snapshot={"fields": {"email": {"required": True}}, "attributes": {}})
    return rel


# --- context gathering ------------------------------------------------------


def test_context_gathers_requirements_designs_and_delivered(v2_env):
    with session_scope() as s:
        rel = _scaffold(s)
    ctx = release_gate.release_gate_context(rel, "qa")
    assert ctx["stage"] == "qa"
    assert [r["identifier"] for r in ctx["requirements"]] == ["REQ-950"]
    assert ctx["designs"] and ctx["designs"][0]["artifact_identifier"] == "ENT-Contact"
    assert ctx["delivered"] and "storage" in ctx["delivered"][0]["areas"]


def test_context_excludes_unconfirmed_requirements(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, confirmed=False)
    ctx = release_gate.release_gate_context(rel, "qa")
    assert ctx["requirements"] == []


# --- fail-closed floor + verdict mapping (LLM judge stubbed) ----------------


def test_gate_fails_closed_without_designs(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, with_design=False)
    calls = []
    gate = release_gate.make_gate_runner(lambda ctx: calls.append(ctx) or {"passed": True},
                                         log=lambda m: None)
    assert gate(rel, "qa") is False
    assert calls == []  # judge never consulted — the floor fails first


def test_gate_fails_closed_without_requirements(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, confirmed=False)  # design exists, but no confirmed req
    gate = release_gate.make_gate_runner(lambda ctx: {"passed": True}, log=lambda m: None)
    assert gate(rel, "testing") is False


def test_gate_maps_judge_verdict(v2_env):
    with session_scope() as s:
        rel = _scaffold(s)
    seen = {}

    def judge(ctx):
        seen.update(ctx)
        return {"passed": True, "summary": "coheres", "findings": []}

    gate = release_gate.make_gate_runner(judge, log=lambda m: None)
    assert gate(rel, "qa") is True
    # the judge was grounded in the real records
    assert seen["requirements"] and seen["designs"] and seen["delivered"]

    fail_gate = release_gate.make_gate_runner(
        lambda ctx: {"passed": False, "summary": "REQ-950 unaddressed",
                     "findings": [{"requirement_identifier": "REQ-950",
                                   "issue": "no email field", "severity": "blocker"}]},
        log=lambda m: None)
    assert fail_gate(rel, "testing") is False
