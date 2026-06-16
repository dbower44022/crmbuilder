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
from crmbuilder_v2.access.models import Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
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


def _drive_to_ready(s, rel):
    releases.transition(s, rel, "development_planning")
    releases.transition(s, rel, "reconciliation")  # freeze
    releases.transition(s, rel, "architecture_planning")
    releases.transition(s, rel, "ready")  # planned-completely


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
        releases.transition(s, rel, "architecture_planning")
        with pytest.raises(ConflictError, match="not decomposed"):
            releases.transition(s, rel, "ready")


def test_planned_completely_succeeds_and_stamps(v2_env):
    with session_scope() as s:
        rel, _, _ = _scoped_release(s, title="PC")
        releases.transition(s, rel, "development_planning")
        releases.transition(s, rel, "reconciliation")
        releases.transition(s, rel, "architecture_planning")
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
        for st in ("qa", "testing", "deployment", "shipped"):
            releases.transition(s, a, st)
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
