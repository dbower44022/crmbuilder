"""Per-area back-half scheduler routing — PI-249 (PRJ-041 / REQ-295), Phase 4f part 2.

When a release is on back_half == "per_area" and the (area, architect|developer|tester)
seams are wired, the release scheduler's development stage runs the matrix back half:
Design fan-out → consolidated Design Review (human pause) → Develop → blind Test →
bounce loop → release-level QA gate (two-level). decide_next stays a pure decision;
the loop is proven end-to-end with stub seams.
"""

from __future__ import annotations

from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    area_specs,
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
)
from crmbuilder_v2.scheduler import release_scheduler as rr

_SUMMARY = (
    "A planning item exercised by the per-area scheduler-routing tests; it carries "
    "enough audience-facing text to satisfy the 200-800 character executive summary "
    "the planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item whose decomposed Work Tasks supply the touched areas.")


def _dev_release(s, areas, *, title="R"):
    """A per_area release sitting in `development` with decomposed area Work Tasks."""
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
         "work_tasks": [{"title": f"do {a}", "area": a} for a in areas]}])
    releases.set_back_half(s, rel, "per_area")
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = "development"
    s.flush()
    return rel


# --- decide_next (pure) -----------------------------------------------------


def test_decide_next_per_area_development_stages():
    base = {"demands_present": True, "has_open_conflicts": False,
            "readiness_ready": True, "dev_lane_enabled": True}
    # no specs yet → fan out Design
    assert rr.decide_next("development", back_half="per_area",
                          area_specs_present=False, **base).kind is rr.StepKind.RUN_AREA_DESIGN
    # specs authored, not yet reviewed → pause for the Design Review
    assert rr.decide_next("development", back_half="per_area", area_specs_present=True,
                          design_signed=False, **base).kind is rr.StepKind.AWAIT_DESIGN_REVIEW
    # reviewed → run the per-area develop/test loop
    assert rr.decide_next("development", back_half="per_area", area_specs_present=True,
                          design_signed=True, **base).kind is rr.StepKind.RUN_PER_AREA_DEV
    # per_pi is unchanged
    assert rr.decide_next("development", back_half="per_pi",
                          all_pis_delivered=False, **base).kind is rr.StepKind.DEVELOP


# --- end-to-end loop --------------------------------------------------------


def _design(ctx):
    return {"implementation": f"impl {ctx['area']}", "testable": f"checks {ctx['area']}"}


def _ok(ctx):
    return {"status": "succeeded"}


def _cfg(rel, **seams):
    return rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda c: [], decomposition_provider=lambda c: [],
        design_provider=seams.get("design", _design),
        develop_provider=seams.get("develop", _ok),
        test_provider=seams.get("test", _ok),
    )


def test_loop_pauses_for_design_review_then_advances_to_qa(v2_env):
    with session_scope() as s:
        rel = _dev_release(s, ["storage", "api"])

    # run 1: fan out Design, then halt awaiting the consolidated Design Review
    r1 = rr.ReleaseScheduler(_cfg(rel)).run()
    assert r1.final_status == "development"
    assert "Design Review" in (r1.stopped_reason or "")
    with session_scope() as s:
        assert area_specs.current_specs(s, rel)  # the area specs were authored
        release_signoffs.create_signoff(s, rel, stage="design", reviewer="r",
                                        attestation="reviewed all area specs")

    # run 2: design signed → Develop + blind Test pass → advance to the release QA gate
    r2 = rr.ReleaseScheduler(_cfg(rel)).run()
    assert r2.final_status == "qa"
    with session_scope() as s:
        assert releases.get_release(s, rel)["release_status"] == "qa"


def test_loop_handles_a_seeded_defect_via_the_bounce_loop(v2_env):
    """End-to-end through the scheduler: a seeded defect in `api` is caught by the
    blind Tester, bounced, fixed next round, and the release reaches qa."""
    with session_scope() as s:
        rel = _dev_release(s, ["storage", "api"])
    rr.ReleaseScheduler(_cfg(rel)).run()  # → AWAIT_DESIGN_REVIEW
    with session_scope() as s:
        release_signoffs.create_signoff(s, rel, stage="design", reviewer="r",
                                        attestation="ok")
    seen: set[str] = set()

    def flaky_test(ctx):
        a = ctx["area"]
        if a == "api" and a not in seen:
            seen.add(a)
            return {"status": "failed", "detail": "seeded defect", "bounce_to": "develop"}
        return {"status": "succeeded"}
    r = rr.ReleaseScheduler(_cfg(rel, test=flaky_test)).run()
    assert r.final_status == "qa"
    with session_scope() as s:
        assert releases.get_release(s, rel)["release_status"] == "qa"
