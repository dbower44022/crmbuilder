"""In-lane area-reopen tests — PI-212 (PRJ-034), RW2/RW3.

Covers pi-212-area-reopen-architecture.md §6: the reopen record (dev-lane gate,
spine-area requirement, double-open rejection), downstream pause via
SYSTEM_AREA_RANKS, the claim guard, and re-freeze/resume.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reopen
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
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


def _dev_release(s, status="development"):
    rel = releases.create_release(s, title="R", description="d")["release_identifier"]
    if status != "preliminary_planning":
        _set_status(s, rel, status)
    return rel


def _work_task(s, rel, area):
    """A Ready Work Task in `area`, wired up to `rel` (membership added while the
    release is open, then status restored)."""
    prior = get_by_identifier(s, Release, Release.release_identifier, rel)
    saved = prior.release_status
    prior.release_status = "preliminary_planning"
    s.flush()
    prj = projects.create_project(
        s, name=f"P{area}", purpose="p", description="d"
    )["project_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    pi = planning_items.create(
        s, title=f"PI{area}", item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    ws = workstreams.create_workstream(s, phase_type="Develop", title=f"W{area}")[
        "workstream_identifier"
    ]
    _link(s, "workstream", ws, "planning_item", pi,
          "workstream_belongs_to_planning_item")
    wt = work_tasks.create_work_task(s, title=f"T{area}", area=area, status="Ready")[
        "work_task_identifier"
    ]
    _link(s, "work_task", wt, "workstream", ws, "work_task_belongs_to_workstream")
    prior.release_status = saved
    s.flush()
    return wt


# ---------------------------------------------------------------------------
# downstream_areas
# ---------------------------------------------------------------------------


def test_downstream_by_rank():
    assert "access" in reopen.downstream_areas("storage")
    assert "ui" in reopen.downstream_areas("storage")
    assert reopen.downstream_areas("ui") == frozenset()  # top rank
    assert reopen.downstream_areas("methodology-process") == frozenset()  # unranked


# ---------------------------------------------------------------------------
# reopen_area gating
# ---------------------------------------------------------------------------


def test_reopen_requires_dev_lane(v2_env):
    with session_scope() as s:
        rel = _dev_release(s, status="reconciliation")
        with pytest.raises(ConflictError, match="development lane"):
            reopen.reopen_area(s, rel, "storage", "need")


def test_reopen_rejects_non_spine_area(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        with pytest.raises(ConflictError, match="dependency-spine"):
            reopen.reopen_area(s, rel, "methodology-process", "need")


def test_reopen_rejects_double_open(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        reopen.reopen_area(s, rel, "storage", "need")
        with pytest.raises(ConflictError, match="already has an open reopen"):
            reopen.reopen_area(s, rel, "storage", "again")


# ---------------------------------------------------------------------------
# pause / resume
# ---------------------------------------------------------------------------


def test_downstream_paused_and_resumed(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        api_task = _work_task(s, rel, "api")  # api is downstream of storage
        reopen.reopen_area(s, rel, "storage", "Contact entity insufficient")
        assert "api" in reopen.paused_areas(s, rel)
        # claiming downstream work is refused while the upstream is thawing.
        with pytest.raises(ConflictError, match="paused"):
            work_tasks.claim_work_task(s, api_task, claimed_by="agent-1")
        # re-freeze → downstream resumes.
        reopen.refreeze_area(s, rel, "storage")
        assert reopen.paused_areas(s, rel) == set()
        out = work_tasks.claim_work_task(s, api_task, claimed_by="agent-1")
        assert out["work_task_claimed_by"] == "agent-1"


def test_non_downstream_area_unaffected(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        storage_task = _work_task(s, rel, "storage")
        # reopen api (rank 3) — storage (rank 1) is upstream, not paused.
        reopen.reopen_area(s, rel, "api", "need")
        assert "storage" not in reopen.paused_areas(s, rel)
        out = work_tasks.claim_work_task(s, storage_task, claimed_by="agent-1")
        assert out["work_task_claimed_by"] == "agent-1"


def test_refreeze_without_open_reopen_404(v2_env):
    with session_scope() as s:
        rel = _dev_release(s)
        with pytest.raises(NotFoundError):
            reopen.refreeze_area(s, rel, "storage")
