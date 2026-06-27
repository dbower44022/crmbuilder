"""Manual-release execution mode — PI-294 / PI-295 (PRJ-051, REQ-331/332/333).

A release carries an ``execution_mode`` of ``automated`` (default — the agent
pipeline) or ``manual`` (a human driver). For a manual release the post-freeze
gates relax: the planned-completely gate needs only the freeze scope and skips
the per-item decomposition (REQ-331); the qa/test stages advance on the driver's
recorded pass stamps via the existing qa_pass/test_pass endpoints (REQ-332); and
ship approval auto-records once every in-scope Planning Item resolves (REQ-333).
The freeze scope gate and the reconciliation/architecture human reviews still
apply either way.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, UnprocessableError
from crmbuilder_v2.access.models import PlanningItem, Release, Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
    requirement,
    workstreams,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _confirm_req(s, req):
    row = get_by_identifier(s, Requirement, Requirement.requirement_identifier, req)
    row.requirement_status = "confirmed"
    s.flush()


def _resolve_pi(s, pi):
    row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pi)
    row.status = "Resolved"
    s.flush()


def _scope_release(s, *, execution_mode, with_workstream, title="R"):
    """A frozen-able release with one in-scope project + PI + confirmed requirement.

    Returns ``(release_id, pi_id)``. When ``with_workstream`` the PI is decomposed
    (an automated release needs it to pass planned-completely); a manual release
    leaves it undecomposed.
    """
    rel = releases.create_release(
        s, title=title, description="d", execution_mode=execution_mode
    )["release_identifier"]
    prj = projects.create_project(
        s, name=f"P{title}", purpose="p", description="d"
    )["project_identifier"]
    pi = planning_items.create(
        s, title=f"PI{title}", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    req = requirement.create_requirement(
        s, name=f"REQ{title}", description="d", acceptance_summary="a"
    )["requirement_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _link(s, "planning_item", pi, "requirement", req,
          "planning_item_implements_requirement")
    _confirm_req(s, req)
    if with_workstream:
        ws = workstreams.create_workstream(
            s, phase_type="Develop", title=f"WS{title}"
        )["workstream_identifier"]
        _link(s, "workstream", ws, "planning_item", pi,
              "workstream_belongs_to_planning_item")
    return rel, pi


def _freeze_and_review(s, rel):
    """Drive a scoped release through freeze + the two human reviews to ready."""
    releases.transition(s, rel, "development_planning")
    releases.transition(s, rel, "reconciliation")
    release_signoffs.create_signoff(
        s, rel, stage="reconciliation", reviewer="t", attestation="ok")
    releases.transition(s, rel, "architecture_planning")
    release_signoffs.create_signoff(
        s, rel, stage="architecture_planning", reviewer="t", attestation="ok")
    releases.transition(s, rel, "ready")


# ---------------------------------------------------------------------------
# execution_mode column — default, create, patch, lock
# ---------------------------------------------------------------------------


def test_execution_mode_defaults_to_automated(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="A", description="d")
    assert rel["release_execution_mode"] == "automated"


def test_create_manual_release(v2_env):
    with session_scope() as s:
        rel = releases.create_release(
            s, title="M", description="d", execution_mode="manual"
        )
    assert rel["release_execution_mode"] == "manual"


def test_create_rejects_unknown_mode(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        releases.create_release(
            s, title="X", description="d", execution_mode="semi"
        )


def test_patch_flips_mode_pre_lane(v2_env):
    with session_scope() as s:
        rel = releases.create_release(s, title="P", description="d")[
            "release_identifier"
        ]
    with session_scope() as s:
        out = releases.patch_release(s, rel, execution_mode="manual")
    assert out["release_execution_mode"] == "manual"


def test_patch_mode_locked_in_lane(v2_env):
    with session_scope() as s:
        rel = get_by_identifier(
            s, Release, Release.release_identifier,
            releases.create_release(s, title="L", description="d")[
                "release_identifier"
            ],
        )
        rel.release_status = "development"
        s.flush()
        ident = rel.release_identifier
    with session_scope() as s, pytest.raises(ConflictError, match="locked"):
        releases.patch_release(s, ident, execution_mode="manual")


# ---------------------------------------------------------------------------
# REQ-331 — manual release reaches ready without decomposition
# ---------------------------------------------------------------------------


def test_manual_release_planned_completely_without_decomposition(v2_env):
    with session_scope() as s:
        rel, _pi = _scope_release(
            s, execution_mode="manual", with_workstream=False
        )
        _freeze_and_review(s, rel)  # reaches ready through the real gates
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
    assert row.release_status == "ready"


def test_automated_release_still_requires_decomposition(v2_env):
    with session_scope() as s:
        rel, _pi = _scope_release(
            s, execution_mode="automated", with_workstream=False
        )
        releases.transition(s, rel, "development_planning")
        releases.transition(s, rel, "reconciliation")
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="t", attestation="ok")
        releases.transition(s, rel, "architecture_planning")
        release_signoffs.create_signoff(
            s, rel, stage="architecture_planning", reviewer="t", attestation="ok")
        with pytest.raises(ConflictError, match="not decomposed"):
            releases.transition(s, rel, "ready")


def test_manual_release_still_needs_freeze_scope(v2_env):
    # An empty manual release (no in-scope PIs) cannot be planned-completely —
    # the freeze scope gate still applies.
    with session_scope() as s:
        rel = releases.create_release(
            s, title="E", description="d", execution_mode="manual"
        )["release_identifier"]
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        from datetime import UTC, datetime
        row.release_status = "architecture_planning"
        row.release_frozen_at = datetime.now(UTC)
        s.flush()
        release_signoffs.create_signoff(
            s, rel, stage="architecture_planning", reviewer="t", attestation="ok")
        with pytest.raises(ConflictError, match="no in-scope"):
            releases.transition(s, rel, "ready")


# ---------------------------------------------------------------------------
# REQ-332 + REQ-333 — manual release ships on driver stamps + auto ship approval
# ---------------------------------------------------------------------------


def test_manual_release_ships_on_driver_stamps_and_auto_approval(v2_env):
    with session_scope() as s:
        rel, pi = _scope_release(
            s, execution_mode="manual", with_workstream=False, title="S"
        )
        _freeze_and_review(s, rel)
        releases.transition(s, rel, "development")
        releases.transition(s, rel, "qa")
        # REQ-332 — the driver records the qa/test outcomes via the same endpoints.
        releases.qa_pass(s, rel)
        releases.transition(s, rel, "testing")
        releases.test_pass(s, rel)
        releases.transition(s, rel, "deployment")
        # REQ-333 — all in-scope PIs resolved → ship approval auto-records.
        _resolve_pi(s, pi)
        releases.transition(s, rel, "shipped")
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        assert row.release_status == "shipped"
        # the auto-recorded ship sign-off exists
        signoffs = release_signoffs.list_signoffs(s, rel, stage="ship")
        assert len(signoffs) == 1
        assert signoffs[0]["signoff_reviewer"] == "manual-release"


def test_manual_release_unresolved_pis_blocks_auto_approval(v2_env):
    with session_scope() as s:
        rel, _pi = _scope_release(
            s, execution_mode="manual", with_workstream=False, title="U"
        )
        _freeze_and_review(s, rel)
        releases.transition(s, rel, "development")
        releases.transition(s, rel, "qa")
        releases.qa_pass(s, rel)
        releases.transition(s, rel, "testing")
        releases.test_pass(s, rel)
        releases.transition(s, rel, "deployment")
        # PI not resolved → no auto approval, ship still blocked.
        with pytest.raises(ConflictError, match="no current human ship approval"):
            releases.transition(s, rel, "shipped")


def test_automated_release_still_needs_explicit_ship_signoff(v2_env):
    with session_scope() as s:
        rel, pi = _scope_release(
            s, execution_mode="automated", with_workstream=True, title="A2"
        )
        _freeze_and_review(s, rel)
        releases.transition(s, rel, "development")
        releases.transition(s, rel, "qa")
        releases.qa_pass(s, rel)
        releases.transition(s, rel, "testing")
        releases.test_pass(s, rel)
        releases.transition(s, rel, "deployment")
        _resolve_pi(s, pi)  # resolving does NOT auto-approve an automated release
        with pytest.raises(ConflictError, match="no current human ship approval"):
            releases.transition(s, rel, "shipped")
