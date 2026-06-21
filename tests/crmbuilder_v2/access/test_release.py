"""Release repository tests — PI-205 (PRJ-031), the release pipeline keystone.

Covers pi-205-release-entity-architecture.md §9: schema shape, identifier
format + auto-assign, the guarded transition state machine (legal moves, illegal
rejects, rework bounce-backs), the three gated transitions (freeze,
planned-completely, single-occupancy), lane order / blocked_by, composition
single-membership, and the patch-excludes-status rule.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import PlanningItem, Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
    requirement,
    workstreams,
)
from sqlalchemy import inspect

_EXPECTED_COLUMNS = {
    "release_identifier",
    "release_title",
    "release_status",
    "release_description",
    "release_notes",
    "release_lane_order",
    "release_frozen_at",
    "release_planned_completely_at",
    "release_qa_passed_at",
    "release_test_passed_at",
    "release_shipped_at",
    "release_created_at",
    "release_updated_at",
    "release_deleted_at",
    "release_cancelled_at",
    "release_superseded_at",
    "engagement_id",
}


def _make(s, title="Release 23"):
    return releases.create_release(s, title=title, description="d")


def _link(s, src_t, src, tgt_t, tgt, rel):
    references.create(
        s,
        source_type=src_t,
        source_id=src,
        target_type=tgt_t,
        target_id=tgt,
        relationship=rel,
    )


def _confirm_requirement(s, req_id):
    row = get_by_identifier(
        s, Requirement, Requirement.requirement_identifier, req_id
    )
    row.requirement_status = "confirmed"
    s.flush()


def _scoped_release(s, *, title="R", confirmed=True, decomposed=True):
    """Build a release with one project, one PI, one requirement, optionally
    confirmed and decomposed. Returns (release_id, pi_id, req_id)."""
    rel = _make(s, title=title)["release_identifier"]
    prj = projects.create_project(
        s, name=f"P-{title}", purpose="p", description="d"
    )["project_identifier"]
    pi = planning_items.create(
        s,
        title=f"PI-{title}",
        item_type="pending_work",
        executive_summary="x" * 250,
        area=["storage"],
    )["identifier"]
    req = requirement.create_requirement(
        s, name=f"REQ {title}", description="d", acceptance_summary="a"
    )["requirement_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _link(s, "planning_item", pi, "requirement", req,
          "planning_item_implements_requirement")
    if confirmed:
        _confirm_requirement(s, req)
    if decomposed:
        ws = workstreams.create_workstream(
            s, phase_type="Develop", title=f"WS-{title}"
        )["workstream_identifier"]
        _link(s, "workstream", ws, "planning_item", pi,
              "workstream_belongs_to_planning_item")
    return rel, pi, req


def _signoff(s, rel, stage):
    """Record a human review sign-off for a front-half stage (PI-238 gate)."""
    release_signoffs.create_signoff(
        s, rel, stage=stage, reviewer="tester", attestation="reviewed",
    )


def _drive_to_ready(s, rel):
    releases.transition(s, rel, "development_planning")
    releases.transition(s, rel, "reconciliation")  # freeze
    _signoff(s, rel, "reconciliation")  # PI-238 review gate
    releases.transition(s, rel, "architecture_planning")
    _signoff(s, rel, "architecture_planning")  # PI-238 review gate
    releases.transition(s, rel, "ready")  # planned-completely


def _drive_to_shipped(s, rel):
    _drive_to_ready(s, rel)
    releases.transition(s, rel, "development")
    releases.transition(s, rel, "qa")
    releases.qa_pass(s, rel)
    releases.transition(s, rel, "testing")
    releases.test_pass(s, rel)
    releases.transition(s, rel, "deployment")
    releases.transition(s, rel, "shipped")


def _set_pi_status(s, pi_id, status):
    row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pi_id)
    row.status = status
    s.flush()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


def test_table_shape(v2_env):
    inspector = inspect(get_engine())
    assert "releases" in inspector.get_table_names()
    cols = {c["name"] for c in inspector.get_columns("releases")}
    assert cols == _EXPECTED_COLUMNS
    pk = inspector.get_pk_constraint("releases")
    assert pk["constrained_columns"] == ["release_identifier", "engagement_id"]


def test_identifier_autoassign_and_format(v2_env):
    with session_scope() as s:
        r = _make(s)
        assert r["release_identifier"] == "REL-001"
        assert r["release_status"] == "preliminary_planning"
    with session_scope() as s, pytest.raises(UnprocessableError):
        releases.create_release(s, title="Bad", description="d", identifier="R-1")


# ---------------------------------------------------------------------------
# Lifecycle / transitions
# ---------------------------------------------------------------------------


def test_illegal_transition_rejected(v2_env):
    with session_scope() as s:
        rel = _make(s)["release_identifier"]
        # preliminary_planning -> reconciliation is not a legal edge.
        with pytest.raises(StatusTransitionError):
            releases.transition(s, rel, "reconciliation")


def test_rework_bounceback_allowed(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="RW")
        _drive_to_ready(s, rel)
        releases.transition(s, rel, "development")
        releases.transition(s, rel, "qa")
        # qa -> development is a legal rework bounce-back; lane stays held.
        out = releases.transition(s, rel, "development")
        assert out["release_status"] == "development"


# ---------------------------------------------------------------------------
# Freeze gate
# ---------------------------------------------------------------------------


def test_freeze_rejected_when_scope_empty(v2_env):
    with session_scope() as s:
        rel = _make(s)["release_identifier"]
        releases.transition(s, rel, "development_planning")
        with pytest.raises(ConflictError, match="no release-scoped"):
            releases.transition(s, rel, "reconciliation")


def test_freeze_rejected_when_requirement_unconfirmed(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="UC", confirmed=False)
        releases.transition(s, rel, "development_planning")
        with pytest.raises(ConflictError, match="not confirmed"):
            releases.transition(s, rel, "reconciliation")


def test_freeze_succeeds_and_stamps(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="FZ")
        releases.transition(s, rel, "development_planning")
        out = releases.transition(s, rel, "reconciliation")
        assert out["release_status"] == "reconciliation"
        assert out["release_frozen_at"] is not None


# ---------------------------------------------------------------------------
# Planned-completely gate
# ---------------------------------------------------------------------------


def test_planned_completely_rejected_when_undecomposed(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="ND", decomposed=False)
        releases.transition(s, rel, "development_planning")
        releases.transition(s, rel, "reconciliation")
        _signoff(s, rel, "reconciliation")
        releases.transition(s, rel, "architecture_planning")
        _signoff(s, rel, "architecture_planning")
        # planned-completely fails before the review check (undecomposed PI)
        with pytest.raises(ConflictError, match="not decomposed"):
            releases.transition(s, rel, "ready")


def test_planned_completely_succeeds_and_stamps(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="PC")
        releases.transition(s, rel, "development_planning")
        releases.transition(s, rel, "reconciliation")
        _signoff(s, rel, "reconciliation")
        releases.transition(s, rel, "architecture_planning")
        _signoff(s, rel, "architecture_planning")
        out = releases.transition(s, rel, "ready")
        assert out["release_status"] == "ready"
        assert out["release_planned_completely_at"] is not None


# ---------------------------------------------------------------------------
# Single-occupancy gate
# ---------------------------------------------------------------------------


def test_single_occupancy_blocks_second_release(v2_env):
    with session_scope() as s:
        a, _, _ = _scoped_release(s, title="A")
        b, _, _ = _scoped_release(s, title="B")
        _drive_to_ready(s, a)
        _drive_to_ready(s, b)
        releases.transition(s, a, "development")
        with pytest.raises(ConflictError, match="already holds it"):
            releases.transition(s, b, "development")


def test_lane_freed_after_ship(v2_env):
    with session_scope() as s:
        a, _, _ = _scoped_release(s, title="A2")
        b, _, _ = _scoped_release(s, title="B2")
        _drive_to_ready(s, a)
        _drive_to_ready(s, b)
        releases.transition(s, a, "development")
        releases.transition(s, a, "qa")
        releases.qa_pass(s, a)
        releases.transition(s, a, "testing")
        releases.test_pass(s, a)
        releases.transition(s, a, "deployment")
        releases.transition(s, a, "shipped")
        out = releases.transition(s, b, "development")
        assert out["release_status"] == "development"


def test_blocked_by_unshipped_release_cannot_enter_lane(v2_env):
    with session_scope() as s:
        a, _, _ = _scoped_release(s, title="A3")
        b, _, _ = _scoped_release(s, title="B3")
        _drive_to_ready(s, a)
        _drive_to_ready(s, b)
        _link(s, "release", b, "release", a, "blocked_by")
        with pytest.raises(ConflictError, match="blocked by"):
            releases.transition(s, b, "development")


# ---------------------------------------------------------------------------
# Composition / patch
# ---------------------------------------------------------------------------


def test_project_belongs_to_one_release(v2_env):
    with session_scope() as s:
        r1 = _make(s, title="One")["release_identifier"]
        r2 = _make(s, title="Two")["release_identifier"]
        prj = projects.create_project(
            s, name="Shared", purpose="p", description="d"
        )["project_identifier"]
        _link(s, "project", prj, "release", r1, "project_belongs_to_release")
        with pytest.raises(UnprocessableError, match="already belongs"):
            _link(s, "project", prj, "release", r2, "project_belongs_to_release")


def test_patch_rejects_status(v2_env):
    with session_scope() as s:
        rel = _make(s)["release_identifier"]
        with pytest.raises(UnprocessableError, match="unknown patchable"):
            releases.patch_release(s, rel, status="development")


# ---------------------------------------------------------------------------
# Ship completes fully-delivered projects (PI-227)
# ---------------------------------------------------------------------------


def test_ship_completes_in_flight_project_with_no_active_pi(v2_env):
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="DONE")
        prj = releases._in_scope_projects(s, rel)[0]
        projects.patch_project(s, prj, status="in_flight")
        _set_pi_status(s, pi, "Resolved")  # terminal disposition
        _drive_to_shipped(s, rel)
        assert projects.get_project(s, prj)["project_status"] == "complete"


def test_ship_completes_project_whose_pi_is_deferred(v2_env):
    # Deferred is a decided disposition (not pending work), so it still completes.
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="DEF")
        prj = releases._in_scope_projects(s, rel)[0]
        projects.patch_project(s, prj, status="in_flight")
        _set_pi_status(s, pi, "Deferred")
        _drive_to_shipped(s, rel)
        assert projects.get_project(s, prj)["project_status"] == "complete"


def test_ship_leaves_project_with_active_pi_in_flight(v2_env):
    # A still-active PI (Ready) means unfinished work — the project is NOT
    # force-completed; it stays in_flight (moves to a new project per the rule).
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="OPEN")
        prj = releases._in_scope_projects(s, rel)[0]
        projects.patch_project(s, prj, status="in_flight")
        _set_pi_status(s, pi, "Ready")
        _drive_to_shipped(s, rel)
        assert projects.get_project(s, prj)["project_status"] == "in_flight"


def test_ship_leaves_planned_project_untouched(v2_env):
    # Only in_flight projects auto-complete (planned -> complete is not a legal
    # project transition); a planned project is left as-is.
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="PLN")
        prj = releases._in_scope_projects(s, rel)[0]
        _set_pi_status(s, pi, "Resolved")
        # project left at its create-default "planned"
        _drive_to_shipped(s, rel)
        assert projects.get_project(s, prj)["project_status"] == "planned"


# ---------------------------------------------------------------------------
# Planning-item status counts (REQ-242 / WTK-178)
# ---------------------------------------------------------------------------


def _add_pi(s, prj, *, title, status):
    """Create a planning item, scope it to ``prj``, set its status."""
    pi = planning_items.create(
        s,
        title=title,
        item_type="pending_work",
        executive_summary="x" * 250,
        area=["storage"],
    )["identifier"]
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _set_pi_status(s, pi, status)
    return pi


def test_status_counts_groups_in_scope_pis_by_status(v2_env):
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="CNT")
        prj = releases._in_scope_projects(s, rel)[0]
        _set_pi_status(s, pi, "Draft")
        _add_pi(s, prj, title="PI-cnt-2", status="Ready")
        _add_pi(s, prj, title="PI-cnt-3", status="Ready")
        _add_pi(s, prj, title="PI-cnt-4", status="Resolved")
        out = releases.planning_item_status_counts(s, rel)
        assert out["release_identifier"] == rel
        assert out["status_counts"] == {"Draft": 1, "Ready": 2, "Resolved": 1}
        assert out["total"] == 4


def test_status_counts_omits_absent_statuses_and_orders_by_lifecycle(v2_env):
    # Only statuses actually present appear (no zeros), in lifecycle order even
    # when inserted out of order.
    with session_scope() as s:
        rel, pi, _ = _scoped_release(s, title="ORD")
        prj = releases._in_scope_projects(s, rel)[0]
        _set_pi_status(s, pi, "Resolved")
        _add_pi(s, prj, title="PI-ord-2", status="Draft")
        _add_pi(s, prj, title="PI-ord-3", status="In Progress")
        out = releases.planning_item_status_counts(s, rel)
        assert list(out["status_counts"]) == ["Draft", "In Progress", "Resolved"]
        assert "Ready" not in out["status_counts"]


def test_status_counts_empty_when_no_in_scope_pis(v2_env):
    with session_scope() as s:
        rel = _make(s, title="EMPTY")["release_identifier"]
        out = releases.planning_item_status_counts(s, rel)
        assert out == {
            "release_identifier": rel,
            "status_counts": {},
            "total": 0,
        }


def test_status_counts_unknown_release_404(v2_env):
    from crmbuilder_v2.access.exceptions import NotFoundError

    with session_scope() as s:
        with pytest.raises(NotFoundError):
            releases.planning_item_status_counts(s, "REL-999")
