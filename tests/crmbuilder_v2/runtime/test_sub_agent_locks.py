"""Sub-agent file-lock coordination — PI-220 (PRJ-030), AL-6 / FL-1..6.

The dev-org lock runtime: acquire declared resources, verify the diff + release at
merge-back, detect a mis-judged cross-sub-agent overlap, reclaim a dead child — and
a no-op outside a dev-lane release. See release-pipeline-agent-layer-architecture.md
§5.4 and the PI-203 substrate.
"""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2.access import locks
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    work_tasks,
    workstreams,
)
from crmbuilder_v2.runtime import sub_agent_locks as sal

_SUMMARY = (
    "A planning item used by the sub-agent file-lock tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive-summary the "
    "planning_items repository requires on create so the scaffolding builds a valid "
    "in-scope item under a release that sits in the development lane for the test."
)


def _edge(s, st, si, rel, tt, ti):
    references.create(s, source_type=st, source_id=si, target_type=tt,
                      target_id=ti, relationship=rel)


def _dev_lane_work_task(s, *, lane=True):
    """A work task whose release is (by default) in the development lane."""
    prj = projects.create_project(s, name="P", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title="T", item_type="pending_work", executive_summary=_SUMMARY,
    )["identifier"]
    ws = workstreams.create_workstream(s, phase_type="Develop", title="Build")[
        "workstream_identifier"
    ]
    wt = work_tasks.create_work_task(s, title="do it", area="storage")[
        "work_task_identifier"
    ]
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    _edge(s, "project", prj, "project_belongs_to_release", "release", rel)
    _edge(s, "planning_item", pi, "planning_item_belongs_to_project", "project", prj)
    _edge(s, "workstream", ws, "workstream_belongs_to_planning_item",
          "planning_item", pi)
    _edge(s, "work_task", wt, "work_task_belongs_to_workstream", "workstream", ws)
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = "development" if lane else "architecture_planning"
    if lane:
        row.release_frozen_at = datetime.now(UTC)
    s.flush()
    return wt, rel, ws


# --- the no-op gate ---------------------------------------------------------


def test_noop_when_not_release_scoped(v2_env):
    with session_scope() as s:
        wt = work_tasks.create_work_task(s, title="x", area="storage")[
            "work_task_identifier"
        ]
        assert sal.dev_lane_release(s, wt) is None
        assert sal.acquire_declared(s, wt, ["foo.py"]) is None
        assert sal.verify_and_release(s, wt, ["foo.py"]) is None


def test_noop_when_release_not_in_lane(v2_env):
    with session_scope() as s:
        wt, _, _ = _dev_lane_work_task(s, lane=False)
        assert sal.dev_lane_release(s, wt) is None
        assert sal.verify_and_release(s, wt, ["foo.py"]) is None


# --- the protocol within the dev lane ---------------------------------------


def test_acquire_verify_release_in_dev_lane(v2_env):
    with session_scope() as s:
        wt, rel, _ = _dev_lane_work_task(s)
        assert sal.dev_lane_release(s, wt) == rel
        acquired = sal.acquire_declared(s, wt, ["migrations/0001_x.py", "mod.py"])
        names = {a["resource_name"] for a in acquired}
        # FL-2: file paths + the logical migration-chain resource
        assert "mod.py" in names and "migration-chain" in names
        report = sal.verify_and_release(s, wt, ["migrations/0001_x.py", "mod.py"])
        assert report["conflicts"] == []
        assert set(report["held"]) >= {"mod.py", "migration-chain"}
        # FL-5: locks released after merge-back
        assert locks.held_locks(s, holder=wt) == []


def test_verify_detects_cross_subagent_overlap(v2_env):
    with session_scope() as s:
        wt1, rel, ws = _dev_lane_work_task(s)
        # a second sub-agent in the SAME release, under the same workstream (a
        # non-membership edge, so it is fine post-freeze).
        wt2 = work_tasks.create_work_task(s, title="other", area="storage")[
            "work_task_identifier"
        ]
        _edge(s, "work_task", wt2, "work_task_belongs_to_workstream", "workstream", ws)

        sal.acquire_declared(s, wt1, ["shared.py"])
        report = sal.verify_and_release(s, wt2, ["shared.py"])
        assert any(c["resource"] == "shared.py" and c["holder"] == wt1
                   for c in report["conflicts"])


def test_reclaim_releases_dead_child(v2_env):
    with session_scope() as s:
        wt, _, _ = _dev_lane_work_task(s)
        sal.acquire_declared(s, wt, ["a.py", "b.py"])
        assert locks.held_locks(s, holder=wt)
        sal.reclaim(s, wt)
        assert locks.held_locks(s, holder=wt) == []
