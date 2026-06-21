"""Release-pipeline dev-lane delegation tests — PI-219 extension (PRJ-033).

decide_next over the lane stages (pure) + an end-to-end loop driving a release from
`ready` through development → qa → testing → deployment → shipped with deterministic
stub seams (a pi_runner that delivers a PI, a gate_runner that passes), proving the
whole pipeline runs on agent-produced input without a network. See
release-pipeline-agent-layer-architecture.md §5.2.
"""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import PlanningItem, Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    work_tasks,
    workstreams,
)
from crmbuilder_v2.scheduler import release_scheduler as rr

_SUMMARY = (
    "A planning item exercised by the release dev-lane delegation tests; it carries "
    "enough audience-facing text to satisfy the 200-800 character executive-summary "
    "the planning_items repository enforces on create so the scaffolding builds a "
    "valid in-scope item under a release that walks the development lane in the test."
)


# --- pure decision over the lane -------------------------------------------


def _d(status, **kw):
    base = {"demands_present": True, "has_open_conflicts": False,
            "readiness_ready": True}
    base.update(kw)
    return rr.decide_next(status, **base).kind


def test_decide_next_ready_is_planning_boundary_without_dev_lane():
    assert _d("ready", dev_lane_enabled=False) is rr.StepKind.DONE
    assert _d("development", dev_lane_enabled=False) is rr.StepKind.DONE


def test_decide_next_walks_the_lane():
    K = rr.StepKind
    assert _d("ready", dev_lane_enabled=True) is K.ENTER_LANE
    assert _d("development", dev_lane_enabled=True, all_pis_delivered=False) is K.DEVELOP
    assert _d("development", dev_lane_enabled=True, all_pis_delivered=True) is K.TO_QA
    assert _d("qa", dev_lane_enabled=True, qa_passed=False) is K.RUN_QA
    assert _d("qa", dev_lane_enabled=True, qa_passed=True) is K.TO_TESTING
    assert _d("testing", dev_lane_enabled=True, test_passed=False) is K.RUN_TEST
    assert _d("testing", dev_lane_enabled=True, test_passed=True) is K.TO_DEPLOYMENT
    assert _d("deployment", dev_lane_enabled=True) is K.SHIP
    assert _d("shipped", dev_lane_enabled=True) is K.DONE


# --- end-to-end loop through the lane ---------------------------------------


def _scaffold(s, *, status="ready", pi_status="Decomposed"):
    """A release at `status` with one in-scope, decomposed PI (delivered? per
    pi_status). Edges wired before the freeze stamp so FE-3 admits them."""
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="ado",
    )["identifier"]
    ws = workstreams.create_workstream(s, phase_type="Develop", title="B")[
        "workstream_identifier"
    ]
    wt = work_tasks.create_work_task(s, title="x", area="storage")[
        "work_task_identifier"
    ]
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    references.create(s, source_type="workstream", source_id=ws,
                      target_type="planning_item", target_id=pi,
                      relationship="workstream_belongs_to_planning_item")
    references.create(s, source_type="work_task", source_id=wt,
                      target_type="workstream", target_id=ws,
                      relationship="work_task_belongs_to_workstream")
    rel_row = get_by_identifier(s, Release, Release.release_identifier, rel)
    rel_row.release_status = status
    rel_row.release_frozen_at = datetime.now(UTC)
    rel_row.release_planned_completely_at = datetime.now(UTC)
    pi_row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pi)
    pi_row.status = pi_status
    s.flush()
    return rel, pi


def _deliver_runner(deliver=True):
    """A stub pi_runner that drives the PI to In Review (ORM, bypassing transition
    rules — it stands in for the ADO runtime)."""
    def _run(rid, pi):
        if not deliver:
            return
        with session_scope() as s:
            row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pi)
            row.status = "In Review"
            s.flush()
    return _run


def test_loop_drives_ready_to_shipped(v2_env):
    with session_scope() as s:
        rel, pi = _scaffold(s, status="ready")
    cfg = rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda ctx: [],
        decomposition_provider=lambda ctx: [],
        pi_runner=_deliver_runner(),
        gate_runner=lambda rid, stage: True,
    )
    report = rr.ReleaseScheduler(cfg).run()
    assert report.final_status == "shipped", report.stopped_reason
    with session_scope() as s:
        assert planning_items.get(s, pi)["status"] == "In Review"


def test_loop_pauses_when_no_gate_runner(v2_env):
    with session_scope() as s:
        # already in qa with the PI delivered, so the loop owes only the QA gate
        rel, _ = _scaffold(s, status="qa", pi_status="In Review")
    cfg = rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda ctx: [],
        decomposition_provider=lambda ctx: [],
        pi_runner=_deliver_runner(),
        gate_runner=None,
    )
    report = rr.ReleaseScheduler(cfg).run()
    assert report.final_status == "qa"
    assert "gate owed" in (report.stopped_reason or "")


def test_loop_halts_when_pi_not_delivered(v2_env):
    with session_scope() as s:
        rel, _ = _scaffold(s, status="development", pi_status="Decomposed")
    cfg = rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda ctx: [],
        decomposition_provider=lambda ctx: [],
        pi_runner=_deliver_runner(deliver=False),  # leaves the PI undelivered
        gate_runner=lambda rid, stage: True,
    )
    report = rr.ReleaseScheduler(cfg).run()
    assert report.final_status == "development"
    assert "did not reach a delivered state" in (report.stopped_reason or "")
