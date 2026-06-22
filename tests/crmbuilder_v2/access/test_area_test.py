"""Per-area blind Test + bounce — PI-248 (PRJ-041 / REQ-295), Phase 4e.

Each touched area's Tester verifies the build's behaviour against the area's
testable spec — blind (given the testable spec + Work Tasks, NOT the implementation
spec or the Developer's code, Decision 4). Areas are independent (no halt). On a
failure the bounce is recorded as a coherence finding and routed to Develop (code
bug) or Design (spec gap) — Decision 5.
"""

from __future__ import annotations

from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    area_specs,
    findings,
    planning_items,
    projects,
    references,
    releases,
)

_SUMMARY = (
    "A planning item exercised by the per-area blind Test tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive summary the "
    "planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item whose decomposed Work Tasks supply the touched areas.")


def _scaffold(s, areas, *, title="R"):
    prj = projects.create_project(s, name=f"P{title}", purpose="p", description="d")[
        "project_identifier"]
    pi = planning_items.create(
        s, title=f"PI{title}", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="interactive")["identifier"]
    rel = releases.create_release(s, title=title, description="d")["release_identifier"]
    references.create(s, source_type="project", source_id=prj, target_type="release",
                      target_id=rel, relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    orch.decompose_planning_item_direct(s, pi, [
        {"phase_type": "Develop", "title": "build",
         "work_tasks": [{"title": f"do {a}", "area": a} for a in areas]},
    ])
    return rel


def _author_specs(s, rel, areas):
    for a in areas:
        area_specs.author_spec(s, rel, a, implementation=f"impl {a}",
                               testable=f"checks {a}")


def _pass_provider(calls):
    def provider(ctx):
        calls.append(ctx)
        return {"status": "succeeded"}
    return provider


def test_blind_test_all_pass(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage", "api"])
        _author_specs(s, rel, ["storage", "api"])
        calls = []
        out = orch.run_area_test(s, rel, _pass_provider(calls))
        assert out["all_passed"] is True and out["bounced"] == []
        assert [c["area"] for c in calls] == ["storage", "api"]


def test_tester_is_blind_to_implementation(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage"])
        _author_specs(s, rel, ["storage"])
        calls = []
        orch.run_area_test(s, rel, _pass_provider(calls))
        ctx = calls[0]
        # given the testable spec ...
        assert ctx["testable_spec"] == "checks storage"
        # ... but NOT the implementation spec or the dev code (blind, Decision 4)
        assert "implementation_spec" not in ctx
        assert "prior_area_results" not in ctx


def test_failure_records_finding_and_bounces_to_develop(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage", "api"])
        _author_specs(s, rel, ["storage", "api"])
        before = len(findings.list_findings(s))

        def provider(ctx):
            if ctx["area"] == "storage":
                return {"status": "failed", "detail": "behaviour X is wrong"}
            return {"status": "succeeded"}
        out = orch.run_area_test(s, rel, provider)
        assert out["all_passed"] is False
        by_area = {b["area"]: b for b in out["bounced"]}
        assert "storage" in by_area
        assert by_area["storage"]["bounce_to"] == "develop"  # default = code bug
        assert by_area["storage"]["finding"]  # a finding was recorded
        # api is still tested (independent areas, no halt)
        assert [r["area"] for r in out["areas"]] == ["storage", "api"]
        assert len(findings.list_findings(s)) == before + 1


def test_bounce_to_design_for_a_spec_gap(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage"])
        _author_specs(s, rel, ["storage"])

        def provider(ctx):
            return {"status": "failed", "detail": "the spec is ambiguous",
                    "bounce_to": "design"}
        out = orch.run_area_test(s, rel, provider)
        assert out["bounced"][0]["bounce_to"] == "design"
        assert out["bounced"][0]["finding"]


def test_needs_human_when_a_touched_area_has_no_spec(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage", "api"])
        _author_specs(s, rel, ["storage"])  # api touched but unspecified
        out = orch.run_area_test(s, rel, _pass_provider([]))
        by_area = {r["area"]: r for r in out["areas"]}
        assert by_area["api"]["status"] == "needs_human"
