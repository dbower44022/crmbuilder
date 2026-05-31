"""PI Lead substrate tests — WTK-005 (design §3.2-3.4).

Covers the execution gate (phase_overview readiness + serial blocked_by), opening
a phase (start_phase: Ready->In Progress + ready Work Tasks), and verify-and-
advance (complete_phase requires all Work Tasks Complete).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import (
    decomposition,
    lead,
    planning_items,
    scoping,
)
from crmbuilder_v2.access.repositories import (
    work_tasks as work_tasks_repo,
)

_EXEC = "ADO PI Lead test executive summary, comfortably over the floor. " * 5


def _scoped_pi(s, ident="PI-850"):
    """Decompose a PI and scope every phase (each gets one Work Task)."""
    planning_items.create(
        s, identifier=ident, title="Deliver feature", item_type="pending_work",
        status="Draft", executive_summary=_EXEC,
    )
    ws = decomposition.decompose_planning_item(s, ident)
    phases = {w["workstream_phase_type"]: w["workstream_identifier"] for w in ws}
    for ph, wid in phases.items():
        scoping.scope_workstream(s, wid, [{"title": f"{ph} task", "area": "access"}])
    return ident, phases


def _complete_all_tasks(s, workstream_id):
    """Drive every Work Task of a Workstream Ready->Claimed->In Progress->Complete."""
    for wt in lead._work_tasks_of(s, workstream_id):
        wid = wt["work_task_identifier"]
        work_tasks_repo.claim_work_task(s, wid, claimed_by="area-specialist")
        for st in ("Claimed", "In Progress", "Complete"):
            work_tasks_repo.patch_work_task(s, wid, status=st)


def test_overview_fresh_decomposition(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-851", title="t", item_type="pending_work",
            status="Draft", executive_summary=_EXEC,
        )
        decomposition.decompose_planning_item(s, "PI-851")
        ov = lead.phase_overview(s, "PI-851")
    assert ov["decomposed"] is True
    assert len(ov["phases"]) == 6
    assert ov["all_scoped"] is False
    assert ov["all_terminal"] is False
    assert ov["next_executable"] is None  # nothing is Ready yet


def test_gate_opens_after_scoping(v2_env):
    with session_scope() as s:
        _, phases = _scoped_pi(s, ident="PI-852")
        ov = lead.phase_overview(s, "PI-852")
    assert ov["all_scoped"] is True
    # Only Architecture (first phase, no predecessors) is executable now.
    assert ov["next_executable"] == phases["Architecture"]
    by_phase = {p["phase_type"]: p for p in ov["phases"]}
    assert by_phase["Architecture"]["executable_now"] is True
    assert by_phase["Development"]["executable_now"] is False
    assert by_phase["Development"]["blocked_by"] == [phases["Architecture"]]


def test_start_phase_readies_work_tasks(v2_env):
    with session_scope() as s:
        _, phases = _scoped_pi(s, ident="PI-853")
        arch = phases["Architecture"]
        result = lead.start_phase(s, arch)
        assert result["workstream"]["workstream_status"] == "In Progress"
        assert all(t["work_task_status"] == "Ready" for t in result["readied_work_tasks"])


def test_start_phase_blocked_by_predecessor(v2_env):
    with session_scope() as s:
        _, phases = _scoped_pi(s, ident="PI-854")
    # Development is blocked_by Architecture (still Ready, not terminal).
    with session_scope() as s, pytest.raises(ConflictError):
        lead.start_phase(s, phases["Development"])


def test_start_phase_requires_ready(v2_env):
    with session_scope() as s:
        planning_items.create(
            s, identifier="PI-855", title="t", item_type="pending_work",
            status="Draft", executive_summary=_EXEC,
        )
        ws = decomposition.decompose_planning_item(s, "PI-855")
        planned = ws[0]["workstream_identifier"]  # still Planned (unscoped)
    with session_scope() as s, pytest.raises(ConflictError):
        lead.start_phase(s, planned)


def test_complete_phase_requires_all_tasks_complete(v2_env):
    with session_scope() as s:
        _, phases = _scoped_pi(s, ident="PI-856")
        arch = phases["Architecture"]
        lead.start_phase(s, arch)  # In Progress, tasks Ready (not Complete)
    with session_scope() as s, pytest.raises(ConflictError):
        lead.complete_phase(s, arch)


def test_full_serial_execution_to_all_terminal(v2_env):
    with session_scope() as s:
        pid, phases = _scoped_pi(s, ident="PI-857")

    # Walk the phases in canonical order, honoring the serial gate each step.
    for phase in decomposition.PHASE_SEQUENCE:
        wid = phases[phase]
        with session_scope() as s:
            ov = lead.phase_overview(s, pid)
            assert ov["next_executable"] == wid  # the gate exposes exactly this one
            lead.start_phase(s, wid)
            _complete_all_tasks(s, wid)
            lead.complete_phase(s, wid)

    with session_scope() as s:
        ov = lead.phase_overview(s, pid)
        assert ov["all_terminal"] is True
        assert ov["next_executable"] is None


def test_overview_unknown_pi_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        lead.phase_overview(s, "PI-999")
