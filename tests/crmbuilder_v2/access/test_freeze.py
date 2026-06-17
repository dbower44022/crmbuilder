"""Freeze-enforcement tests — PI-216 (PRJ-031), §9A.

Covers pi-216-freeze-enforcement-architecture.md §6: band classification,
derived requirement band, the requirement-edit gate (ungoverned vs governed amend
vs locked), and the scope-membership gate. Release statuses are set directly via
the ORM — the freeze *transitions* are exercised in test_release; here we isolate
the *enforcement* of derived frozen-ness.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import freeze
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release, Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    requirement,
)


def _link(s, src_t, src, tgt_t, tgt, rel):
    references.create(
        s,
        source_type=src_t,
        source_id=src,
        target_type=tgt_t,
        target_id=tgt,
        relationship=rel,
    )


def _set_release_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def _set_review_state(s, req, state):
    row = get_by_identifier(
        s, Requirement, Requirement.requirement_identifier, req
    )
    row.requirement_review_state = state
    s.flush()


def _scenario(s, *, release_status="preliminary_planning"):
    """release → project → PI → requirement, membership edges added while open."""
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    prj = projects.create_project(
        s, name="P", purpose="p", description="d"
    )["project_identifier"]
    pi = planning_items.create(
        s, title="PI", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    req = requirement.create_requirement(
        s, name="R1", description="d", acceptance_summary="a"
    )["requirement_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _link(s, "planning_item", pi, "requirement", req,
          "planning_item_implements_requirement")
    if release_status != "preliminary_planning":
        _set_release_status(s, rel, release_status)
    return rel, prj, pi, req


# ---------------------------------------------------------------------------
# Band classification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status,band",
    [
        ("preliminary_planning", "open"),
        ("development_planning", "open"),
        ("reconciliation", "amend_window"),
        ("architecture_planning", "amend_window"),
        ("ready", "locked"),
        ("development", "locked"),
        ("qa", "locked"),
        ("testing", "locked"),
        ("deployment", "locked"),
        ("shipped", None),
        ("cancelled", None),
        ("superseded", None),
    ],
)
def test_band_for_status(status, band):
    assert freeze.band_for_status(status) == band


def test_requirement_band_tracks_release(v2_env):
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="architecture_planning")
        assert freeze.requirement_band(s, req) == "amend_window"


def test_unscheduled_requirement_is_open(v2_env):
    with session_scope() as s:
        req = requirement.create_requirement(
            s, name="Free", description="d", acceptance_summary="a"
        )["requirement_identifier"]
        assert freeze.requirement_band(s, req) == "open"


# ---------------------------------------------------------------------------
# Requirement-edit gate
# ---------------------------------------------------------------------------


def test_edit_allowed_when_open(v2_env):
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="development_planning")
        out = requirement.patch_requirement(s, req, description="changed freely")
        assert out["requirement_description"] == "changed freely"


def test_ungoverned_edit_rejected_in_amend_window(v2_env):
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="reconciliation")
        with pytest.raises(ConflictError, match="governing decision"):
            requirement.patch_requirement(s, req, description="sneaky edit")


def test_governed_edit_allowed_in_amend_window(v2_env):
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="reconciliation")
        _set_review_state(s, req, "needs_review")  # a decision opened the gate
        out = requirement.patch_requirement(s, req, description="governed amend")
        assert out["requirement_description"] == "governed amend"


def test_edit_rejected_when_locked_even_needs_review(v2_env):
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="ready")
        _set_review_state(s, req, "needs_review")
        with pytest.raises(ConflictError, match="new release"):
            requirement.patch_requirement(s, req, description="too late")


def test_non_content_edit_not_gated(v2_env):
    """A notes-only edit (not a _CONTENT_FIELD) is not a demand change."""
    with session_scope() as s:
        _, _, _, req = _scenario(s, release_status="reconciliation")
        out = requirement.patch_requirement(s, req, notes="just a note")
        assert out["requirement_notes"] == "just a note"


# ---------------------------------------------------------------------------
# Scope-membership gate
# ---------------------------------------------------------------------------


def test_membership_add_rejected_against_frozen_release(v2_env):
    with session_scope() as s:
        rel = releases.create_release(
            s, title="Frozen", description="d"
        )["release_identifier"]
        _set_release_status(s, rel, "reconciliation")
        prj = projects.create_project(
            s, name="Late", purpose="p", description="d"
        )["project_identifier"]
        with pytest.raises(ConflictError, match="scope.*frozen"):
            _link(s, "project", prj, "release", rel, "project_belongs_to_release")


def test_membership_add_allowed_when_open(v2_env):
    with session_scope() as s:
        rel = releases.create_release(
            s, title="Open", description="d"
        )["release_identifier"]
        prj = projects.create_project(
            s, name="Early", purpose="p", description="d"
        )["project_identifier"]
        _link(s, "project", prj, "release", rel, "project_belongs_to_release")
        # no raise = pass; verify the edge exists
        assert freeze.requirement_band(s, "REQ-999") == "open"
