"""PI-190 / REQ-165 — an interactive Planning Item is ADO-invisible at every
tier, not only at PM dispatch. Backstops on decompose / scope / start_phase /
claim_work_task each refuse an effective-interactive PI in the access layer, so
REST, MCP, and runtime callers are all covered.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    decomposition,
    lead,
    planning_items,
    pm,
    scoping,
    work_tasks,
)

_EXEC = "ADO interactive-gate test executive summary, over the floor. " * 5


def _pi(s, ident, mode="ado"):
    planning_items.create(
        s, identifier=ident, title=f"PI {ident}", item_type="pending_work",
        status="Draft", executive_summary=_EXEC, execution_mode=mode,
    )
    return ident


def test_decompose_refuses_interactive_pi(v2_env):
    with session_scope() as s:
        _pi(s, "PI-870", mode="interactive")
        assert pm.is_ado_interactive(s, "PI-870") is True
        with pytest.raises(ConflictError):
            decomposition.decompose_planning_item(s, "PI-870")


def test_scope_start_claim_refuse_interactive_pi(v2_env):
    """A PI decomposed + scoped while ado, then flipped interactive: every later
    ADO action on its phases / tasks is refused."""
    with session_scope() as s:
        _pi(s, "PI-871", mode="ado")
        ws = decomposition.decompose_planning_item(s, "PI-871")
        arch, dev = ws[0]["workstream_identifier"], ws[1]["workstream_identifier"]
        # Scope the first phase while still ado → creates a Ready phase + task.
        scoped = scoping.scope_workstream(s, arch, [{"title": "x", "area": "storage"}])
        wt_id = scoped["work_tasks"][0]["work_task_identifier"]

        # Now the PI is reclassified interactive (the realistic hazard).
        planning_items.update(s, "PI-871", execution_mode="interactive")

        # scope another (still-Planned) phase → refused.
        with pytest.raises(ConflictError):
            scoping.scope_workstream(s, dev, [{"title": "y", "area": "storage"}])
        # open the Ready phase for execution → refused.
        with pytest.raises(ConflictError):
            lead.start_phase(s, arch)
        # claim a Work Task under it → refused.
        with pytest.raises(ConflictError):
            work_tasks.claim_work_task(s, wt_id, claimed_by="CONV-001")


def test_ado_pi_still_flows_normally(v2_env):
    """Control: a plain ado PI is untouched by the gate end-to-end."""
    with session_scope() as s:
        _pi(s, "PI-872", mode="ado")
        ws = decomposition.decompose_planning_item(s, "PI-872")
        arch = ws[0]["workstream_identifier"]
        scoped = scoping.scope_workstream(s, arch, [{"title": "x", "area": "storage"}])
        wt_id = scoped["work_tasks"][0]["work_task_identifier"]
        started = lead.start_phase(s, arch)
        assert started["workstream"]["workstream_status"] == "In Progress"
        claimed = work_tasks.claim_work_task(s, wt_id, claimed_by="CONV-002")
        assert claimed["work_task_claimed_by"] == "CONV-002"


def test_effective_mode_inherits_interactive_project(v2_env):
    """The gate uses *effective* mode: an ado PI under an interactive Project is
    treated as interactive at every tier (decompose refused)."""
    from crmbuilder_v2.access.repositories import projects, references

    with session_scope() as s:
        projects.create_project(
            s, identifier="PRJ-870", name="Locked hub", purpose="p",
            description="d", execution_mode="interactive",
        )
        _pi(s, "PI-873", mode="ado")  # PI itself ado
        references.create(
            s, source_type="planning_item", source_id="PI-873",
            target_type="project", target_id="PRJ-870",
            relationship="planning_item_belongs_to_project",
        )
        assert pm.effective_execution_mode(s, "PI-873") == "interactive"
        with pytest.raises(ConflictError):
            decomposition.decompose_planning_item(s, "PI-873")
