"""Project Manager substrate tests — WTK-006 (design §2 tier 1 / §3.1).

Covers the dependency-aware PI backlog: eligibility (startable + all blocked_by
Resolved), the eligible/in_flight/blocked partitions, dispatch (eligible PI ->
In Progress), and the way resolving a blocker unlocks its dependents.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import planning_items, pm, projects, references

_EXEC = "ADO Project Manager test executive summary, over the floor. " * 5


def _project(s, ident="PRJ-900"):
    projects.create_project(
        s, identifier=ident, name="Engagement", purpose="p", description="d",
    )
    return ident


def _pi(s, ident, project_id, *, blocked_by=None, status="Draft"):
    planning_items.create(
        s, identifier=ident, title=f"PI {ident}", item_type="pending_work",
        status=status, executive_summary=_EXEC,
    )
    references.create(
        s, source_type="planning_item", source_id=ident,
        target_type="project", target_id=project_id,
        relationship="planning_item_belongs_to_project",
    )
    for blocker in blocked_by or []:
        references.create(
            s, source_type="planning_item", source_id=ident,
            target_type="planning_item", target_id=blocker,
            relationship="blocked_by",
        )
    return ident


def test_backlog_eligibility_and_blocking(v2_env):
    with session_scope() as s:
        pid = _project(s)
        _pi(s, "PI-900", pid)                          # no blockers -> eligible
        _pi(s, "PI-901", pid, blocked_by=["PI-900"])   # blocked by PI-900 (Draft)
        b = pm.project_backlog(s, pid)
    assert b["eligible"] == ["PI-900"]
    assert b["blocked"] == ["PI-901"]
    assert b["all_resolved"] is False
    by_id = {i["identifier"]: i for i in b["planning_items"]}
    assert by_id["PI-901"]["unresolved_blockers"] == ["PI-900"]
    assert by_id["PI-901"]["eligible"] is False


def test_resolving_a_blocker_unlocks_dependents(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-901")
        _pi(s, "PI-910", pid)
        _pi(s, "PI-911", pid, blocked_by=["PI-910"])
        # PI-911 starts blocked.
        assert pm.project_backlog(s, pid)["eligible"] == ["PI-910"]
        # Resolve the blocker.
        planning_items.update(s, "PI-910", status="Resolved")
        b = pm.project_backlog(s, pid)
    assert "PI-911" in b["eligible"]
    assert b["resolved"] == ["PI-910"]


def test_independent_pis_are_both_eligible(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-902")
        _pi(s, "PI-920", pid)
        _pi(s, "PI-921", pid)  # no blocked_by between them -> parallelizable
        elig = {i["identifier"] for i in pm.eligible_planning_items(s, pid)}
    assert elig == {"PI-920", "PI-921"}


def test_dispatch_starts_eligible_pi(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-903")
        _pi(s, "PI-930", pid)
        out = pm.dispatch_planning_item(s, "PI-930")
        assert out["status"] == "In Progress"
        b = pm.project_backlog(s, pid)
        assert b["in_flight"] == ["PI-930"]
        assert "PI-930" not in b["eligible"]


def test_dispatch_blocked_pi_conflicts(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-904")
        _pi(s, "PI-940", pid)
        _pi(s, "PI-941", pid, blocked_by=["PI-940"])
    with session_scope() as s, pytest.raises(ConflictError):
        pm.dispatch_planning_item(s, "PI-941")


def test_dispatch_already_started_conflicts(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-905")
        _pi(s, "PI-950", pid, status="In Progress")
    with session_scope() as s, pytest.raises(ConflictError):
        pm.dispatch_planning_item(s, "PI-950")


def test_all_resolved_when_every_pi_terminal(v2_env):
    with session_scope() as s:
        pid = _project(s, ident="PRJ-906")
        _pi(s, "PI-960", pid, status="Resolved")
        _pi(s, "PI-961", pid, status="Resolved")
        b = pm.project_backlog(s, pid)
    assert b["all_resolved"] is True
    assert b["eligible"] == []


def test_backlog_unknown_project_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        pm.project_backlog(s, "PRJ-999")


def test_dispatch_unknown_pi_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        pm.dispatch_planning_item(s, "PI-999")
