"""Per-area Develop fan-out — PI-247 (PRJ-041 / REQ-295), Phase 4d.

Gated by the Design Review (PI-246): the back half does not build until the area
specs are human-approved. Then one Develop task per touched area, in layer-rank
order, building to the approved spec via the injected (area, developer) seam, with
lower-rank merged outputs fed forward; the run halts at the first non-succeeded
area (downstream depends on it).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    area_specs,
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
)

_SUMMARY = (
    "A planning item exercised by the per-area Develop tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive summary the "
    "planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item whose decomposed Work Tasks supply the touched areas."
)


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


def _signoff(s, rel):
    release_signoffs.create_signoff(s, rel, stage="design", reviewer="r",
                                    attestation="reviewed")


def _ok_provider(calls):
    def provider(ctx):
        calls.append(ctx)
        return {"status": "succeeded"}
    return provider


def test_develop_blocked_without_fresh_design_signoff(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage"])
        _author_specs(s, rel, ["storage"])  # spec exists, but no Design Review sign-off
        with pytest.raises(ConflictError, match="Design Review"):
            orch.run_area_develop(s, rel, _ok_provider([]))


def test_develop_fans_out_in_rank_order_with_feed_forward(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["ui", "storage", "api"])
        _author_specs(s, rel, ["ui", "storage", "api"])
        _signoff(s, rel)
        calls = []
        out = orch.run_area_develop(s, rel, _ok_provider(calls))
        assert out["all_succeeded"] is True and out["halted_on"] is None
        assert [c["area"] for c in calls] == ["storage", "api", "ui"]
        # the seam gets the approved spec ...
        assert calls[1]["area"] == "api"
        assert calls[1]["implementation_spec"] == "impl api"
        assert calls[1]["testable_spec"] == "checks api"
        # ... and the lower-rank areas' results feed forward
        assert [p["area"] for p in calls[2]["prior_area_results"]] == ["storage", "api"]


def test_develop_halts_at_first_failure(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage", "api", "ui"])
        _author_specs(s, rel, ["storage", "api", "ui"])
        _signoff(s, rel)

        def provider(ctx):
            if ctx["area"] == "api":
                return {"status": "failed", "detail": "build broke"}
            return {"status": "succeeded"}
        out = orch.run_area_develop(s, rel, provider)
        assert out["halted_on"] == "api" and out["all_succeeded"] is False
        # ui (higher rank, depends on api) is never reached
        assert [r["area"] for r in out["areas"]] == ["storage", "api"]
        assert out["areas"][-1]["status"] == "failed"


def test_develop_needs_human_when_a_touched_area_has_no_spec(v2_env):
    with session_scope() as s:
        rel = _scaffold(s, ["storage", "api"])
        _author_specs(s, rel, ["storage"])  # api is touched but unspecified
        _signoff(s, rel)  # signs off over the current set {storage}
        out = orch.run_area_develop(s, rel, _ok_provider([]))
        assert out["halted_on"] == "api"
        assert out["areas"][-1]["status"] == "needs_human"
