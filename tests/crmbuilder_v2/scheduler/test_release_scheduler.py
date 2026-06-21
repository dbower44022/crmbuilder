"""Release-pipeline orchestration loop tests — PI-219 (PRJ-033).

decide_next (pure, no I/O) + an end-to-end loop driving one release from
reconciliation to ready with deterministic stub providers (proving the substrate
runs on agent-produced input without a network). See
release-pipeline-agent-layer-architecture.md §5.
"""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
)
from crmbuilder_v2.scheduler import release_scheduler as rr

_SUMMARY = (
    "A planning item exercised by the release-pipeline orchestration-loop tests; it "
    "carries enough audience-facing text to satisfy the 200-800 character executive "
    "summary requirement the planning_items repository enforces on create so the "
    "scaffolding builds a valid in-scope item that the readiness gate accepts cleanly."
)


# --- pure decision -----------------------------------------------------------


def test_decide_next_pre_freeze_awaits():
    step = rr.decide_next(
        "development_planning", demands_present=False,
        has_open_conflicts=False, readiness_ready=False,
    )
    assert step.kind is rr.StepKind.AWAIT_FREEZE


def test_decide_next_reconciliation_authors_then_advances():
    assert rr.decide_next(
        "reconciliation", demands_present=False,
        has_open_conflicts=False, readiness_ready=False,
    ).kind is rr.StepKind.AUTHOR_DEMANDS
    assert rr.decide_next(
        "reconciliation", demands_present=True,
        has_open_conflicts=True, readiness_ready=False,
    ).kind is rr.StepKind.RESOLVE_CONFLICTS
    assert rr.decide_next(
        "reconciliation", demands_present=True,
        has_open_conflicts=False, readiness_ready=False,
    ).kind is rr.StepKind.ADVANCE_RECONCILIATION


def test_decide_next_planning_then_finalize_then_done():
    assert rr.decide_next(
        "architecture_planning", demands_present=True,
        has_open_conflicts=False, readiness_ready=False,
    ).kind is rr.StepKind.PLAN
    assert rr.decide_next(
        "architecture_planning", demands_present=True,
        has_open_conflicts=False, readiness_ready=True,
    ).kind is rr.StepKind.FINALIZE
    assert rr.decide_next(
        "ready", demands_present=True,
        has_open_conflicts=False, readiness_ready=True,
    ).kind is rr.StepKind.DONE


# --- end-to-end loop with stub providers ------------------------------------


def _scaffold_frozen_reconciliation(s):
    """A frozen release in 'reconciliation' with one in-scope interactive PI."""
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
        execution_mode="interactive",
    )["identifier"]
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    references.create(s, source_type="project", source_id=prj,
                      target_type="release", target_id=rel,
                      relationship="project_belongs_to_release")
    references.create(s, source_type="planning_item", source_id=pi,
                      target_type="project", target_id=prj,
                      relationship="planning_item_belongs_to_project")
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = "reconciliation"
    row.release_frozen_at = datetime.now(UTC)
    s.flush()
    return rel, pi


def test_loop_drives_reconciliation_to_ready(v2_env):
    with session_scope() as s:
        rel, pi = _scaffold_frozen_reconciliation(s)

    demands = [{
        "requirement_identifier": "REQ-1", "artifact_type": "entity",
        "artifact_identifier": "ENT-1", "field": "email", "facet": "required",
        "op": "set", "value": True,
    }]
    decomposition = [{
        "phase_type": "Develop", "title": "Build it",
        "work_tasks": [{"title": "add field", "area": "storage"}],
    }]

    cfg = rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda ctx: demands,
        decomposition_provider=lambda ctx: decomposition,
    )
    report = rr.ReleaseScheduler(cfg).run()

    assert report.final_status == "ready"
    with session_scope() as s:
        # the loop authored demands, planned, decomposed, flipped the PI, advanced.
        assert planning_items.get(s, pi)["execution_mode"] == "ado"
        assert releases._pi_workstreams(s, pi)  # decomposed


def test_loop_pauses_on_conflict(v2_env):
    with session_scope() as s:
        rel, pi = _scaffold_frozen_reconciliation(s)

    # two contradictory demands on the same facet → an open conflict → PAUSE.
    conflicting = [
        {"requirement_identifier": "REQ-1", "artifact_type": "entity",
         "artifact_identifier": "ENT-1", "field": "email", "facet": "required",
         "op": "set", "value": True},
        {"requirement_identifier": "REQ-2", "artifact_type": "entity",
         "artifact_identifier": "ENT-1", "field": "email", "facet": "required",
         "op": "set", "value": False},
    ]
    cfg = rr.ReleaseSchedulerConfig(
        release_identifier=rel,
        demands_provider=lambda ctx: conflicting,
        decomposition_provider=lambda ctx: [],
    )
    report = rr.ReleaseScheduler(cfg).run()
    assert report.final_status == "reconciliation"
    assert "conflict" in (report.stopped_reason or "")
