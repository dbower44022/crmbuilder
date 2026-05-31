"""Work Task entity tests — PI-112 Phase 4b."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    engagement_areas,
    references,
    work_tasks,
    workstreams,
)


def _wsk(s, ident="WSK-100"):
    workstreams.create_workstream(
        s, phase_type="Development", title="ws", identifier=ident
    )
    return ident


def test_create_autoassign_with_system_area(v2_env):
    with session_scope() as s:
        r = work_tasks.create_work_task(s, title="t", area="storage")
        assert r["work_task_identifier"] == "WTK-001"
        assert r["work_task_area"] == "storage"
        assert r["work_task_status"] == "Planned"


def test_area_must_be_valid(v2_env):
    # Unknown area rejected; engagement area accepted once registered.
    with session_scope() as s, pytest.raises(UnprocessableError):
        work_tasks.create_work_task(s, title="t", area="mr")
    with session_scope() as s:
        engagement_areas.create_engagement_area(s, "mr")
    with session_scope() as s:
        r = work_tasks.create_work_task(s, title="t", area="mr")
        assert r["work_task_area"] == "mr"


def test_status_lifecycle_and_timestamps(v2_env):
    with session_scope() as s:
        work_tasks.create_work_task(s, title="t", area="api", identifier="WTK-010")
    for nxt in ("Ready", "Claimed", "In Progress", "Complete"):
        with session_scope() as s:
            r = work_tasks.patch_work_task(s, "WTK-010", status=nxt)
            assert r["work_task_status"] == nxt
    with session_scope() as s:
        r = work_tasks.get_work_task(s, "WTK-010")
        assert r["work_task_started_at"] is not None
        assert r["work_task_completed_at"] is not None
    # Complete is terminal.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        work_tasks.patch_work_task(s, "WTK-010", status="Ready")


def test_invalid_transition_rejected(v2_env):
    with session_scope() as s:
        work_tasks.create_work_task(s, title="t", area="ui", identifier="WTK-020")
    # Planned -> In Progress is not allowed (must go through Ready/Claimed).
    with session_scope() as s, pytest.raises(StatusTransitionError):
        work_tasks.patch_work_task(s, "WTK-020", status="In Progress")


def test_claim_and_release(v2_env):
    with session_scope() as s:
        work_tasks.create_work_task(s, title="t", area="mcp", identifier="WTK-030")
    with session_scope() as s:
        r = work_tasks.claim_work_task(s, "WTK-030", claimed_by="CNV-001")
        assert r["work_task_claimed_by"] == "CNV-001"
        assert r["work_task_claimed_at"] is not None
    # Idempotent for the same claimant; conflict for a different one.
    with session_scope() as s:
        work_tasks.claim_work_task(s, "WTK-030", claimed_by="CNV-001")
    with session_scope() as s, pytest.raises(ConflictError):
        work_tasks.claim_work_task(s, "WTK-030", claimed_by="CNV-999")
    with session_scope() as s:
        r = work_tasks.release_work_task(s, "WTK-030", claimed_by="CNV-001")
        assert r["work_task_claimed_by"] is None


def test_belongs_to_workstream_edge(v2_env):
    with session_scope() as s:
        wid = _wsk(s)
        work_tasks.create_work_task(
            s, title="t", area="storage", identifier="WTK-040",
            references=[{
                "source_type": "work_task", "source_id": "WTK-040",
                "target_type": "workstream", "target_id": wid,
                "relationship": "work_task_belongs_to_workstream",
            }],
        )
    with session_scope() as s:
        edges = references.list_references(
            s, source_id="WTK-040",
            relationship_kind="work_task_belongs_to_workstream",
        )
        assert len(edges) == 1 and edges[0]["target_id"] == "WSK-100"


def test_list_filter_by_area_and_soft_delete(v2_env):
    with session_scope() as s:
        work_tasks.create_work_task(s, title="a", area="storage", identifier="WTK-050")
        work_tasks.create_work_task(s, title="b", area="api", identifier="WTK-051")
    with session_scope() as s:
        rows = work_tasks.list_work_tasks(s, area="storage")
        assert [r["work_task_identifier"] for r in rows] == ["WTK-050"]
    with session_scope() as s:
        work_tasks.delete_work_task(s, "WTK-050")
        assert work_tasks.get_work_task(s, "WTK-050") is None
    with session_scope() as s:
        work_tasks.restore_work_task(s, "WTK-050")
        assert work_tasks.get_work_task(s, "WTK-050") is not None
