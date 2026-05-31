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
            s, phase_type="Architecture", title="t", status="Nope"
        )


def test_architecture_phase_accepted_design_rejected(v2_env):
    # WTK-001 / design §5: DEC-349's `Design` was renamed `Architecture`.
    with session_scope() as s:
        r = workstreams.create_workstream(s, phase_type="Architecture", title="a")
        assert r["workstream_phase_type"] == "Architecture"
    # The old `Design` value is no longer admitted.
    with session_scope() as s, pytest.raises(UnprocessableError):
        workstreams.create_workstream(s, phase_type="Design", title="d")


def test_full_gate_lifecycle_and_timestamps(v2_env):
    # WTK-001 / design §5: Planned → Scoping → Ready → In Progress → Complete.
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Testing", title="t", identifier="WSK-010"
        )
    for status in ("Scoping", "Ready"):
        with session_scope() as s:
            r = workstreams.patch_workstream(s, "WSK-010", status=status)
            assert r["workstream_status"] == status
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


def test_planned_cannot_skip_to_in_progress(v2_env):
    # The gate model forbids jumping past Scoping/Ready.
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Testing", title="t", identifier="WSK-011"
        )
    with session_scope() as s, pytest.raises(StatusTransitionError):
        workstreams.patch_workstream(s, "WSK-011", status="In Progress")


def test_not_applicable_is_terminal(v2_env):
    # Scoping can resolve to Not Applicable, which is terminal.
    with session_scope() as s:
        workstreams.create_workstream(
            s, phase_type="Testing", title="t", identifier="WSK-012"
        )
    with session_scope() as s:
        workstreams.patch_workstream(s, "WSK-012", status="Scoping")
    with session_scope() as s:
        r = workstreams.patch_workstream(s, "WSK-012", status="Not Applicable")
        assert r["workstream_status"] == "Not Applicable"
    with session_scope() as s, pytest.raises(StatusTransitionError):
        workstreams.patch_workstream(s, "WSK-012", status="In Progress")


def test_needs_attention_flag(v2_env):
    # DEC-359: orthogonal human-escape flag, set/cleared independent of status.
    with session_scope() as s:
        r = workstreams.create_workstream(
            s, phase_type="Development", title="t", identifier="WSK-013"
        )
        assert r["workstream_needs_attention"] is False
        assert r["workstream_needs_attention_reason"] is None
    with session_scope() as s:
        r = workstreams.patch_workstream(
            s,
            "WSK-013",
            needs_attention=True,
            needs_attention_reason="stuck on a credential",
        )
        assert r["workstream_needs_attention"] is True
        assert r["workstream_needs_attention_reason"] == "stuck on a credential"
        # The flag overlays the status without disturbing it.
        assert r["workstream_status"] == "Planned"
    with session_scope() as s:
        r = workstreams.patch_workstream(
            s, "WSK-013", needs_attention=False, needs_attention_reason=None
        )
        assert r["workstream_needs_attention"] is False
        assert r["workstream_needs_attention_reason"] is None


def test_needs_attention_set_on_create(v2_env):
    with session_scope() as s:
        r = workstreams.create_workstream(
            s,
            phase_type="Development",
            title="t",
            identifier="WSK-014",
            needs_attention=True,
            needs_attention_reason="born blocked on input",
        )
        assert r["workstream_needs_attention"] is True
        assert r["workstream_needs_attention_reason"] == "born blocked on input"


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
            s, phase_type="Architecture", title="t", identifier="WSK-040"
        )
    with session_scope() as s, pytest.raises(ConflictError):
        workstreams.create_workstream(
            s, phase_type="Architecture", title="t2", identifier="WSK-040"
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
