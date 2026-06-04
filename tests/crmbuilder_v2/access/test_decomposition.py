"""ADO structural decomposer tests — WTK-002 (design §3.2.1 / §4.1).

The decomposer turns a Planning Item into its three work-step Workstreams
(Design, Develop, Test — PI-129 / DEC-392), chained by serial ``blocked_by``
gates. These cover the happy path (all steps created in order, all edges wired),
the once-only guard, and the not-found case.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import decomposition, planning_items, references

_EXEC = "ADO decomposer test executive summary, well over the floor. " * 5


def _pi(s, ident="PI-800", title="Build the thing"):
    planning_items.create(
        s, identifier=ident, title=title, item_type="pending_work",
        status="Draft", executive_summary=_EXEC,
    )
    return ident


def test_decompose_creates_three_phases_in_order(v2_env):
    with session_scope() as s:
        pid = _pi(s)
        created = decomposition.decompose_planning_item(s, pid)
    assert [w["workstream_phase_type"] for w in created] == list(
        decomposition.PHASE_SEQUENCE
    )
    assert all(w["workstream_status"] == "Planned" for w in created)
    # Titles carry the phase + the PI title.
    assert created[0]["workstream_title"] == "Design — Build the thing"


def test_decompose_wires_belongs_and_blocked_by_chain(v2_env):
    with session_scope() as s:
        pid = _pi(s, ident="PI-801")
        created = decomposition.decompose_planning_item(s, pid)
        ids = [w["workstream_identifier"] for w in created]

    with session_scope() as s:
        # Every phase belongs to the PI.
        belongs = references.list_references(
            s, target_type="planning_item", target_id="PI-801",
            relationship_kind="workstream_belongs_to_planning_item",
        )
        assert sorted(e["source_id"] for e in belongs) == sorted(ids)

        # Serial blocked_by chain: phase N blocked_by phase N-1 (5 edges).
        blocked = references.list_references(
            s, source_type="workstream", target_type="workstream",
            relationship_kind="blocked_by",
        )
        pairs = {(e["source_id"], e["target_id"]) for e in blocked}
        expected = {(ids[i], ids[i - 1]) for i in range(1, len(ids))}
        assert pairs == expected
        assert len(blocked) == len(decomposition.PHASE_SEQUENCE) - 1


def test_decompose_is_once_only(v2_env):
    with session_scope() as s:
        pid = _pi(s, ident="PI-802")
        decomposition.decompose_planning_item(s, pid)
    with session_scope() as s, pytest.raises(ConflictError):
        decomposition.decompose_planning_item(s, "PI-802")


def test_existing_phase_workstreams_reports_decomposition(v2_env):
    with session_scope() as s:
        pid = _pi(s, ident="PI-803")
        assert decomposition.existing_phase_workstreams(s, pid) == []
        created = decomposition.decompose_planning_item(s, pid)
        ids = {w["workstream_identifier"] for w in created}
    with session_scope() as s:
        assert set(decomposition.existing_phase_workstreams(s, "PI-803")) == ids


def test_decompose_unknown_pi_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        decomposition.decompose_planning_item(s, "PI-999")
