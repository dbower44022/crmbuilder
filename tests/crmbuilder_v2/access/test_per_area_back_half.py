"""Per-area back half end-to-end + the back-half flag — PI-249 (PRJ-041 / REQ-295), 4f.

Covers the release_back_half switch (Decision 3) and run_per_area_development — the
post-Design-Review Develop → blind Test → bounce loop (4d + 4e). The headline proof
(the Phase 4 acceptance): a seeded defect is caught by the blind Tester, bounces to
Develop, the next round fixes it, and the release passes.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, ValidationError
from crmbuilder_v2.access.repositories import (
    area_specs,
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
)

_SUMMARY = (
    "A planning item exercised by the per-area back-half tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive summary the "
    "planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item whose decomposed Work Tasks supply the touched areas.")


def _ready_release(s, areas, *, title="R"):
    """A release whose areas are decomposed, spec'd, and Design-Review-signed."""
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
    for a in areas:
        area_specs.author_spec(s, rel, a, implementation=f"impl {a}",
                               testable=f"checks {a}")
    release_signoffs.create_signoff(s, rel, stage="design", reviewer="r",
                                    attestation="reviewed")
    return rel


def _ok(ctx):
    return {"status": "succeeded"}


# --- the back-half flag (Decision 3) ----------------------------------------


def test_back_half_defaults_per_pi_and_is_switchable(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"]
        assert releases.get_release(s, rel)["release_back_half"] == "per_pi"
        out = releases.set_back_half(s, rel, "per_area")
        assert out["release_back_half"] == "per_area"


def test_back_half_rejects_unknown_mode(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"]
        with pytest.raises(ValidationError):
            releases.set_back_half(s, rel, "sideways")


# --- run_per_area_development -----------------------------------------------


def test_develop_gate_requires_design_review(v2_env):
    with session_scope() as s:
        # built + spec'd but NOT design-signed
        prj = projects.create_project(s, name="P", purpose="p", description="d")[
            "project_identifier"]
        pi = planning_items.create(s, title="T", item_type="pending_work",
                                   executive_summary=_SUMMARY,
                                   execution_mode="interactive")["identifier"]
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"]
        references.create(s, source_type="project", source_id=prj,
                          target_type="release", target_id=rel,
                          relationship="project_belongs_to_release")
        references.create(s, source_type="planning_item", source_id=pi,
                          target_type="project", target_id=prj,
                          relationship="planning_item_belongs_to_project")
        orch.decompose_planning_item_direct(s, pi, [
            {"phase_type": "Develop", "title": "b",
             "work_tasks": [{"title": "do storage", "area": "storage"}]}])
        area_specs.author_spec(s, rel, "storage", implementation="i", testable="t")
        with pytest.raises(ConflictError, match="Design Review"):
            orch.run_per_area_development(s, rel, develop_provider=_ok, test_provider=_ok)


def test_passes_in_one_round_when_clean(v2_env):
    with session_scope() as s:
        rel = _ready_release(s, ["storage", "api"])
        out = orch.run_per_area_development(s, rel, develop_provider=_ok, test_provider=_ok)
        assert out["status"] == "passed"
        assert len(out["rounds"]) == 1


def test_seeded_defect_bounces_then_passes(v2_env):
    """Phase 4 acceptance: the blind Tester catches a seeded defect in `api`, bounces
    it to Develop; the next round's Develop fixes it and the release passes."""
    with session_scope() as s:
        rel = _ready_release(s, ["storage", "api"])
        seen: set[str] = set()

        def test_provider(ctx):
            a = ctx["area"]
            if a == "api" and a not in seen:  # the seeded defect, caught once
                seen.add(a)
                return {"status": "failed", "detail": "api behaviour wrong",
                        "bounce_to": "develop"}
            return {"status": "succeeded"}
        out = orch.run_per_area_development(
            s, rel, develop_provider=_ok, test_provider=test_provider)
        assert out["status"] == "passed"
        assert len(out["rounds"]) == 2  # round 1 bounced, round 2 clean
        # round 1's Test recorded the api bounce ...
        r1_test = out["rounds"][0]["test"]
        assert any(b["area"] == "api" and b["bounce_to"] == "develop"
                   for b in r1_test["bounced"])
        # ... round 2's Test is clean
        assert out["rounds"][1]["test"]["all_passed"] is True


def test_spec_gap_bounce_returns_needs_redesign(v2_env):
    with session_scope() as s:
        rel = _ready_release(s, ["storage"])

        def test_provider(ctx):
            return {"status": "failed", "detail": "spec ambiguous",
                    "bounce_to": "design"}
        out = orch.run_per_area_development(
            s, rel, develop_provider=_ok, test_provider=test_provider)
        assert out["status"] == "needs_redesign"


def test_develop_block_halts_the_loop(v2_env):
    with session_scope() as s:
        rel = _ready_release(s, ["storage", "api"])

        def develop_provider(ctx):
            if ctx["area"] == "storage":
                return {"status": "failed", "detail": "cannot build storage"}
            return {"status": "succeeded"}
        out = orch.run_per_area_development(
            s, rel, develop_provider=develop_provider, test_provider=_ok)
        assert out["status"] == "develop_blocked" and out["halted_on"] == "storage"


def test_needs_human_after_max_rounds(v2_env):
    with session_scope() as s:
        rel = _ready_release(s, ["storage"])

        def always_fail(ctx):
            return {"status": "failed", "detail": "persistent code bug",
                    "bounce_to": "develop"}
        out = orch.run_per_area_development(
            s, rel, develop_provider=_ok, test_provider=always_fail, max_rounds=2)
        assert out["status"] == "needs_human"
        assert len(out["rounds"]) == 2
