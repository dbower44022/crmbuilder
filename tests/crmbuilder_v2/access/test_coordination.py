"""Coordination tests — PI-204 (PRJ-029), §6/§7.1/§7.2.

Covers pi-204-coordination-architecture.md §6: the lane_holder read, the
single-owner-per-area gate on the Work Task claim path (REQ-191), and the
no-release no-op. Single-occupancy (REQ-188) is enforced + tested by PI-205
(test_release); affirmed here via lane_holder.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import coordination
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    work_tasks,
    workstreams,
)


def _link(s, st, sid, tt, tid, rel):
    references.create(
        s, source_type=st, source_id=sid, target_type=tt, target_id=tid,
        relationship=rel,
    )


def _set_status(s, rel, status):
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    s.flush()


def _dev_release_with_tasks(s, *, areas, link_release=True):
    """An (optionally release-scoped) PI→workstream with one Ready Work Task per
    entry in ``areas``. Membership edges are added while open, then the release is
    set to development. Returns (release_id|None, [work_task_ids])."""
    rel = None
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    if link_release:
        rel = releases.create_release(s, title="R", description="d")[
            "release_identifier"
        ]
        _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    pi = planning_items.create(
        s, title="PI", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    ws = workstreams.create_workstream(s, phase_type="Develop", title="WS")[
        "workstream_identifier"
    ]
    _link(s, "workstream", ws, "planning_item", pi,
          "workstream_belongs_to_planning_item")
    wt_ids = []
    for i, area in enumerate(areas):
        wt = work_tasks.create_work_task(
            s, title=f"WT{i}", area=area, status="Ready"
        )["work_task_identifier"]
        _link(s, "work_task", wt, "workstream", ws, "work_task_belongs_to_workstream")
        wt_ids.append(wt)
    if link_release:
        _set_status(s, rel, "development")
    return rel, wt_ids


# ---------------------------------------------------------------------------
# lane_holder (REQ-188 affirmation)
# ---------------------------------------------------------------------------


def test_lane_holder_none_when_empty(v2_env):
    with session_scope() as s:
        releases.create_release(s, title="Idle", description="d")
        assert coordination.lane_holder(s) is None


def test_lane_holder_reports_in_lane_release(v2_env):
    with session_scope() as s:
        rel, _ = _dev_release_with_tasks(s, areas=["storage"])
        holder = coordination.lane_holder(s)
        assert holder is not None
        assert holder["release_identifier"] == rel


# ---------------------------------------------------------------------------
# single-owner-per-area (REQ-191)
# ---------------------------------------------------------------------------


def test_area_claimed_by_second_agent_refused(v2_env):
    with session_scope() as s:
        rel, (wt1, wt2) = _dev_release_with_tasks(s, areas=["storage", "storage"])
        work_tasks.claim_work_task(s, wt1, claimed_by="agent-1")
        with pytest.raises(ConflictError, match="single owner"):
            work_tasks.claim_work_task(s, wt2, claimed_by="agent-2")


def test_area_owner_can_claim_more_in_its_area(v2_env):
    with session_scope() as s:
        rel, (wt1, wt2) = _dev_release_with_tasks(s, areas=["storage", "storage"])
        work_tasks.claim_work_task(s, wt1, claimed_by="agent-1")
        out = work_tasks.claim_work_task(s, wt2, claimed_by="agent-1")
        assert out["work_task_claimed_by"] == "agent-1"
        assert coordination.area_owner(s, rel, "storage") == "agent-1"


def test_different_areas_have_independent_owners(v2_env):
    with session_scope() as s:
        rel, (wt1, wt2) = _dev_release_with_tasks(s, areas=["storage", "access"])
        work_tasks.claim_work_task(s, wt1, claimed_by="agent-1")
        work_tasks.claim_work_task(s, wt2, claimed_by="agent-2")
        assert coordination.area_ownership(s, rel) == {
            "storage": "agent-1",
            "access": "agent-2",
        }


def test_no_release_is_unaffected(v2_env):
    with session_scope() as s:
        _, (wt1, wt2) = _dev_release_with_tasks(
            s, areas=["storage", "storage"], link_release=False
        )
        # No release context → single-owner-per-area does not apply; per-task
        # claims by different agents are fine (existing ADO behaviour).
        work_tasks.claim_work_task(s, wt1, claimed_by="agent-1")
        out = work_tasks.claim_work_task(s, wt2, claimed_by="agent-2")
        assert out["work_task_claimed_by"] == "agent-2"
