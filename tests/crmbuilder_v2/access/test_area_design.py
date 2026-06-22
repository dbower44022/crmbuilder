"""Per-area Design fan-out — PI-245 (PRJ-041 / REQ-295), Phase 4b.

touched_areas re-aggregates the release's in-scope area-tagged Work Tasks by area
in layer-rank order (Decision 2); run_area_design fans out one Design task per area
(via an injected architect seam), persisting each area's implementation + testable
spec as the next area_spec version and feeding lower-rank areas' specs forward.
"""

from __future__ import annotations

from crmbuilder_v2.access import release_orchestration as orch
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    area_specs,
    planning_items,
    projects,
    references,
    releases,
)

_SUMMARY = (
    "A planning item exercised by the per-area Design fan-out tests; it carries "
    "enough audience-facing text to satisfy the 200-800 character executive summary "
    "the planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item whose decomposed Work Tasks supply the touched areas."
)


def _scaffold(s, areas, *, title="R"):
    """A release with one in-scope PI decomposed into one Develop Work Task per area."""
    prj = projects.create_project(s, name=f"P{title}", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title=f"PI{title}", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="interactive")["identifier"]
    rel = releases.create_release(s, title=title, description="d")["release_identifier"]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    orch.decompose_planning_item_direct(s, pi, [
        {"phase_type": "Develop", "title": "build",
         "work_tasks": [{"title": f"do {a}", "area": a} for a in areas]},
    ])
    return rel, pi


def _fake_provider(calls):
    """A design seam that records its context and returns a spec derived from the area."""
    def provider(ctx):
        calls.append(ctx)
        a = ctx["area"]
        return {"implementation": f"impl for {a}", "testable": f"checks for {a}",
                "change_reason": "initial design", "trigger_kind": "initial"}
    return provider


# --- touched_areas ----------------------------------------------------------


def test_touched_areas_distinct_in_layer_rank_order(v2_env):
    with session_scope() as s:
        # created out of order; storage(1) < api(3) < ui(4)
        rel, _ = _scaffold(s, ["ui", "storage", "api"])
        assert orch.touched_areas(s, rel) == ["storage", "api", "ui"]


def test_touched_areas_empty_when_no_work(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="E", description="d")[
            "release_identifier"]
        assert orch.touched_areas(s, rel) == []


# --- run_area_design --------------------------------------------------------


def test_fan_out_persists_one_spec_per_area_in_rank_order(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, ["ui", "storage", "api"])
        calls = []
        out = orch.run_area_design(s, rel, _fake_provider(calls))
        # the driver visited areas in rank order ...
        assert [c["area"] for c in calls] == ["storage", "api", "ui"]
        assert [a["area"] for a in out["areas"]] == ["storage", "api", "ui"]
        # ... persisted a v1 spec for each, with the provider's content
        cur = {d["area"]: d for d in area_specs.current_specs(s, rel)}
        assert set(cur) == {"storage", "api", "ui"}
        assert cur["api"]["spec_version"] == 1
        assert cur["api"]["spec_implementation"] == "impl for api"


def test_lower_rank_specs_feed_forward(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, ["storage", "api", "ui"])
        calls = []
        orch.run_area_design(s, rel, _fake_provider(calls))
        by_area = {c["area"]: c for c in calls}
        # storage (rank 1) sees nothing upstream
        assert by_area["storage"]["prior_area_specs"] == []
        # api (rank 3) sees storage
        assert [p["area"] for p in by_area["api"]["prior_area_specs"]] == ["storage"]
        # ui (rank 4) sees storage + api (both lower rank)
        assert [p["area"] for p in by_area["ui"]["prior_area_specs"]] == ["storage", "api"]


def test_same_rank_areas_do_not_feed_each_other(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, ["mcp", "ui"])  # both rank 4
        calls = []
        orch.run_area_design(s, rel, _fake_provider(calls))
        by_area = {c["area"]: c for c in calls}
        # neither rank-4 area feeds the other; mcp sorts before ui
        assert by_area["mcp"]["prior_area_specs"] == []
        assert by_area["ui"]["prior_area_specs"] == []


def test_rerun_appends_a_new_version_per_area(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, ["storage"])
        orch.run_area_design(s, rel, _fake_provider([]))

        def provider_v2(ctx):
            return {"implementation": "impl v2", "testable": "checks v2",
                    "change_reason": "re-designed", "trigger_kind": "revision"}
        orch.run_area_design(s, rel, provider_v2)
        hist = area_specs.spec_history(s, rel, "storage")
        assert [h["spec_version"] for h in hist] == [1, 2]
        assert hist[1]["spec_implementation"] == "impl v2"
        assert hist[1]["spec_trigger_kind"] == "revision"
        assert area_specs.current_spec(s, rel, "storage")["spec_version"] == 2


def test_area_work_tasks_scoped_to_area(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, ["storage", "api"])
        wts = orch.area_work_tasks(s, rel, "storage")
        assert wts and all(
            (w.get("work_task_area") or w.get("area")) == "storage" for w in wts)
