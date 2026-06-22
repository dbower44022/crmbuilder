"""Ship Approval gate — PI-260 (PRJ-041 / REQ-299), Phase 2.

The closing human commit, **symmetric to freeze**: ``deployment → shipped`` requires
the reopen-cascade revalidations complete (RW4, PI-213) **and** a fresh human ship
sign-off. The sign-off is freshness-checked against the shippable state — the QA +
test pass stamps plus the set of artifact versions the release introduced — so any
change after approval (a bounce that re-stamps the gates, or a re-authored design that
bumps a version) voids it and re-opens approval.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release, Requirement
from crmbuilder_v2.access.repositories import (
    artifact_versions,
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


def _front_half_signoff(s, rel, stage):
    release_signoffs.create_signoff(
        s, rel, stage=stage, reviewer="t", attestation="ok")


def _at_deployment(s, title="R"):
    """Build a scoped release and drive it through the real gates to deployment
    (QA + test passed), the state from which Ship Approval is owed."""
    rel = releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]
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
    row = get_by_identifier(s, Requirement, Requirement.requirement_identifier, req)
    row.requirement_status = "confirmed"
    s.flush()
    ws = workstreams.create_workstream(s, phase_type="Develop", title=f"WS{title}")[
        "workstream_identifier"
    ]
    _link(s, "workstream", ws, "planning_item", pi,
          "workstream_belongs_to_planning_item")
    releases.transition(s, rel, "development_planning")
    releases.transition(s, rel, "reconciliation")
    _front_half_signoff(s, rel, "reconciliation")
    releases.transition(s, rel, "architecture_planning")
    _front_half_signoff(s, rel, "architecture_planning")
    releases.transition(s, rel, "ready")
    releases.transition(s, rel, "development")
    releases.transition(s, rel, "qa")
    releases.qa_pass(s, rel)
    releases.transition(s, rel, "testing")
    releases.test_pass(s, rel)
    releases.transition(s, rel, "deployment")
    return rel


def _ship_signoff(s, rel):
    return release_signoffs.create_signoff(
        s, rel, stage="ship", reviewer="release-lead",
        attestation="approved for ship")


def test_ship_gate_blocks_until_approved(v2_env):
    with session_scope() as s:
        rel = _at_deployment(s)
        # no ship sign-off yet — the gate blocks (revalidations are clear, so the
        # block is specifically the missing human approval).
        with pytest.raises(ConflictError, match="ship"):
            releases.transition(s, rel, "shipped")
        _ship_signoff(s, rel)
        assert (
            releases.transition(s, rel, "shipped")["release_status"] == "shipped"
        )


def test_ship_signoff_fresh_then_stale_on_new_artifact_version(v2_env):
    with session_scope() as s:
        rel = _at_deployment(s)
        _ship_signoff(s, rel)
        assert release_signoffs.fresh_signoff(s, rel, "ship") is not None
        # a new artifact version the release introduces changes the shippable
        # state — the approval goes stale and the gate re-blocks.
        artifact_versions.snapshot(
            s, artifact_type="entity", artifact_identifier="Account",
            release_identifier=rel, snapshot={"v": 1})
        assert release_signoffs.fresh_signoff(s, rel, "ship") is None
        with pytest.raises(ConflictError, match="ship"):
            releases.transition(s, rel, "shipped")


def test_ship_fingerprint_tracks_pass_stamps(v2_env):
    with session_scope() as s:
        rel = _at_deployment(s)
        before = release_signoffs.stage_fingerprint(s, rel, "ship")
        # clearing a pass stamp (what a rework bounce does) changes the fingerprint.
        row = get_by_identifier(s, Release, Release.release_identifier, rel)
        row.release_test_passed_at = None
        s.flush()
        after = release_signoffs.stage_fingerprint(s, rel, "ship")
        assert before != after


def test_ship_signoff_status(v2_env):
    with session_scope() as s:
        rel = _at_deployment(s)
        assert (
            release_signoffs.signoff_status(s, rel, "ship")["is_signed_fresh"]
            is False
        )
        _ship_signoff(s, rel)
        assert (
            release_signoffs.signoff_status(s, rel, "ship")["is_signed_fresh"]
            is True
        )
