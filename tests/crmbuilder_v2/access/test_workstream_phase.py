"""Workstream (delivery-phase) entity tests — PI-112 Phase 4a."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import planning_items, references, workstreams

_EXEC = "PI-112 workstream-phase test executive summary. " * 6


def _pi(s, ident="PI-700"):
    planning_items.create(
        s, identifier=ident, title="parent", item_type="pending_work",
        status="Draft", executive_summary=_EXEC,
    )
    return ident


def test_create_autoassign_and_format(v2_env):
    with session_scope() as s:
        r = workstreams.create_workstream(
            s, phase_type="Development", title="Build the thing"
        )
        assert r["workstream_identifier"] == "WSK-001"
        assert r["workstream_status"] == "Planned"
    with session_scope() as s:
        assert workstreams.next_workstream_identifier(s) == "WSK-002"


def test_phase_type_and_status_validated(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        workstreams.create_workstream(s, phase_type="Bogus", title="t")
    with session_scope() as s, pytest.raises(UnprocessableError):
        workstreams.create_workstream(
            s, phase_type="Design", title="t", status="Nope"
        )


def test_design_phase_accepted(v2_env):
    # DEC-349: Design was added to the front of the vocabulary.
    with session_scope() as s:
        r = workstreams.create_workstream(s, phase_type="Design", title="d")
        assert r["workstream_phase_type"] == "Design"


def test_status_transitions_and_timestamps(v2_env):
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Testing", title="t", identifier="WSK-010"
        )
    with session_scope() as s:
        r = workstreams.patch_workstream(s, "WSK-010", status="In Progress")
        assert r["workstream_status"] == "In Progress"
        assert r["workstream_started_at"] is not None
    with session_scope() as s:
        r = workstreams.patch_workstream(s, "WSK-010", status="Complete")
        assert r["workstream_completed_at"] is not None
    # Complete is terminal.
    with session_scope() as s, pytest.raises(StatusTransitionError):
        workstreams.patch_workstream(s, "WSK-010", status="In Progress")


def test_blocked_side_state(v2_env):
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Deployment", title="t", identifier="WSK-020"
        )
    with session_scope() as s:
        workstreams.patch_workstream(s, "WSK-020", status="Blocked")
    with session_scope() as s:
        # Blocked can resume to In Progress.
        r = workstreams.patch_workstream(s, "WSK-020", status="In Progress")
        assert r["workstream_status"] == "In Progress"


def test_belongs_to_planning_item_edge(v2_env):
    with session_scope() as s:
        pid = _pi(s)
        workstreams.create_workstream(
            s, phase_type="Development", title="t", identifier="WSK-030",
            references=[{
                "source_type": "workstream", "source_id": "WSK-030",
                "target_type": "planning_item", "target_id": pid,
                "relationship": "workstream_belongs_to_planning_item",
            }],
        )
    with session_scope() as s:
        edges = references.list_references(
            s, source_id="WSK-030", relationship_kind="workstream_belongs_to_planning_item"
        )
        assert len(edges) == 1 and edges[0]["target_id"] == "PI-700"


def test_explicit_identifier_collision(v2_env):
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Design", title="t", identifier="WSK-040"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        workstreams.create_workstream(
            s, phase_type="Design", title="t2", identifier="WSK-040"
        )


def test_soft_delete_restore(v2_env):
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Documentation", title="t", identifier="WSK-050"
        )
    with session_scope() as s:
        workstreams.delete_workstream(s, "WSK-050")
        assert workstreams.get_workstream(s, "WSK-050") is None
    with session_scope() as s:
        workstreams.restore_workstream(s, "WSK-050")
        assert workstreams.get_workstream(s, "WSK-050") is not None
