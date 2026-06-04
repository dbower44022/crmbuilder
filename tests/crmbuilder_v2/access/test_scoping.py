"""Phase-specialist substrate tests — WTK-003 (design §2.1 / §3.2 / §4.3).

Covers scope_workstream (create Work Tasks + drive Planned->Scoping->Ready, or
->Not Applicable for an empty scope) and prior_phase_outputs (feed-forward).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import (
    decomposition,
    planning_items,
    references,
    scoping,
)

_EXEC = "ADO scoping test executive summary, comfortably over the floor. " * 5


def _decomposed_pi(s, ident="PI-820"):
    planning_items.create(
        s, identifier=ident, title="Ship feature", item_type="pending_work",
        status="Draft", executive_summary=_EXEC,
    )
    return decomposition.decompose_planning_item(s, ident)  # 6 workstreams, in order


def test_scope_with_work_tasks_sets_ready_and_wires_edges(v2_env):
    with session_scope() as s:
        ws = _decomposed_pi(s)
        arch = ws[0]["workstream_identifier"]
        result = scoping.scope_workstream(s, arch, [
            {"title": "Add entity Mentor", "area": "methodology-product"},
            {"title": "Modify intake process", "area": "methodology-process"},
        ])
        assert result["workstream"]["workstream_status"] == "Ready"
        assert len(result["work_tasks"]) == 2

    with session_scope() as s:
        edges = references.list_references(
            s, target_type="workstream", target_id=arch,
            relationship_kind="work_task_belongs_to_workstream",
        )
        assert len(edges) == 2


def test_scope_empty_is_not_applicable(v2_env):
    with session_scope() as s:
        ws = _decomposed_pi(s, ident="PI-821")
        test = ws[2]["workstream_identifier"]  # Test — scoped empty here
        result = scoping.scope_workstream(s, test, [])
        assert result["workstream"]["workstream_status"] == "Not Applicable"
        assert result["work_tasks"] == []


def test_scope_non_planned_conflicts(v2_env):
    with session_scope() as s:
        ws = _decomposed_pi(s, ident="PI-822")
        arch = ws[0]["workstream_identifier"]
        scoping.scope_workstream(s, arch, [{"title": "t", "area": "access"}])
    with session_scope() as s, pytest.raises(ConflictError):
        scoping.scope_workstream(s, arch, [{"title": "t2", "area": "api"}])


def test_scope_unknown_workstream_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        scoping.scope_workstream(s, "WSK-999", [])


def test_prior_phase_outputs_feeds_forward(v2_env):
    with session_scope() as s:
        ws = _decomposed_pi(s, ident="PI-823")
        arch = ws[0]["workstream_identifier"]
        dev = ws[1]["workstream_identifier"]
        scoping.scope_workstream(s, arch, [
            {"title": "Add entity X", "area": "methodology-product"},
        ])

    with session_scope() as s:
        # Design (first step) has no prior output.
        arch_ctx = scoping.prior_phase_outputs(s, arch)
        assert arch_ctx["prior_phases"] == []
        assert arch_ctx["planning_item"] == "PI-823"

        # Develop sees Design's Work Task.
        dev_ctx = scoping.prior_phase_outputs(s, dev)
        assert [p["phase_type"] for p in dev_ctx["prior_phases"]] == ["Design"]
        arch_tasks = dev_ctx["prior_phases"][0]["work_tasks"]
        assert len(arch_tasks) == 1
        assert arch_tasks[0]["work_task_title"] == "Add entity X"


def test_prior_phase_outputs_unknown_workstream_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        scoping.prior_phase_outputs(s, "WSK-999")
