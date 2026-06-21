"""Freeze gate: ready-or-explicitly-deferred — PI-239 (PRJ-041 / REQ-285, D14).

The freeze gate requires every in-scope planning item to be *ready* (its
requirements confirmed AND no blocker outside this release) or *explicitly
deferred* by a human (status Deferred). No silent auto-defer: a not-ready,
not-deferred PI blocks the freeze. Covers freeze_readiness (the per-PI report),
the gate (blocks / passes), and the explicit defer action.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import PlanningItem, Release, Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    projects,
    references,
    releases,
    requirement,
)

_SUMMARY = (
    "A planning item exercised by the freeze-readiness tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive summary the "
    "planning_items repository enforces on create, so the scaffolding builds a "
    "valid in-scope item the freeze gate can evaluate for readiness cleanly."
)


def _link(s, st, sid, tt, tid, rel):
    references.create(s, source_type=st, source_id=sid, target_type=tt,
                      target_id=tid, relationship=rel)


def _confirm(s, req):
    row = get_by_identifier(s, Requirement, Requirement.requirement_identifier, req)
    row.requirement_status = "confirmed"
    s.flush()


def _scoped(s, *, confirmed=True, title="R"):
    """A release with one project + one in-scope PI implementing one requirement."""
    rel = releases.create_release(s, title=title, description="d")["release_identifier"]
    prj = projects.create_project(s, name=f"P{title}", purpose="p", description="d")[
        "project_identifier"
    ]
    pi = planning_items.create(
        s, title=f"PI{title}", item_type="pending_work", executive_summary=_SUMMARY,
    )["identifier"]
    req = requirement.create_requirement(
        s, name=f"REQ{title}", description="d", acceptance_summary="a"
    )["requirement_identifier"]
    _link(s, "project", prj, "release", rel, "project_belongs_to_release")
    _link(s, "planning_item", pi, "project", prj, "planning_item_belongs_to_project")
    _link(s, "planning_item", pi, "requirement", req, "planning_item_implements_requirement")
    if confirmed:
        _confirm(s, req)
    return rel, prj, pi, req


def _set_status(s, pi, status):
    row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pi)
    row.status = status
    s.flush()


# --- freeze_readiness report ------------------------------------------------


def test_ready_when_confirmed_and_no_blocker(v2_env):
    with session_scope() as s:
        rel, _, pi, _ = _scoped(s)
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is True
        assert rep["items"][0]["planning_item"] == pi
        assert rep["items"][0]["ready"] is True


def test_not_ready_when_requirement_unconfirmed(v2_env):
    with session_scope() as s:
        rel, _, pi, req = _scoped(s, confirmed=False)
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is False
        item = rep["not_ready"][0]
        assert item["planning_item"] == pi
        assert req in item["unconfirmed_requirements"]


def test_not_ready_when_blocked_by_external_pi(v2_env):
    with session_scope() as s:
        rel, prj, pi, _ = _scoped(s)
        # an out-of-scope PI (not linked to any in-scope project), not Resolved
        ext = planning_items.create(
            s, title="EXT", item_type="pending_work", executive_summary=_SUMMARY,
        )["identifier"]
        _link(s, "planning_item", pi, "planning_item", ext, "blocked_by")
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is False
        assert ext in rep["not_ready"][0]["external_blockers"]


def test_ready_when_blocker_is_in_scope(v2_env):
    with session_scope() as s:
        rel, prj, pi, _ = _scoped(s)
        # a second in-scope PI; an in-release dependency does not block freeze
        pi2 = planning_items.create(
            s, title="PI2", item_type="pending_work", executive_summary=_SUMMARY,
        )["identifier"]
        _link(s, "planning_item", pi2, "project", prj, "planning_item_belongs_to_project")
        _link(s, "planning_item", pi, "planning_item", pi2, "blocked_by")
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is True


def test_ready_when_external_blocker_resolved(v2_env):
    with session_scope() as s:
        rel, prj, pi, _ = _scoped(s)
        ext = planning_items.create(
            s, title="EXT", item_type="pending_work", executive_summary=_SUMMARY,
        )["identifier"]
        _set_status(s, ext, "Resolved")  # a finished external dep is not a blocker
        _link(s, "planning_item", pi, "planning_item", ext, "blocked_by")
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is True


def test_deferred_pi_is_excluded_from_readiness(v2_env):
    with session_scope() as s:
        rel, _, pi, _ = _scoped(s, confirmed=False)  # would be not-ready ...
        _set_status(s, pi, "Deferred")               # ... but explicitly deferred
        rep = releases.freeze_readiness(s, rel)
        assert rep["ready_to_freeze"] is True
        assert rep["items"][0]["deferred"] is True
        assert rep["not_ready"] == []


# --- the gate + explicit defer ----------------------------------------------


def test_freeze_blocks_not_ready_then_defer_unblocks(v2_env):
    with session_scope() as s:
        rel, prj, pi, _ = _scoped(s)
        ext = planning_items.create(
            s, title="EXT", item_type="pending_work", executive_summary=_SUMMARY,
        )["identifier"]
        _link(s, "planning_item", pi, "planning_item", ext, "blocked_by")
        releases.transition(s, rel, "development_planning")
        # not ready (external blocker) → freeze blocks, naming the defer alternative
        with pytest.raises(ConflictError, match="not ready"):
            releases.transition(s, rel, "reconciliation")
        # explicit human defer → the PI leaves the readiness requirement
        out = releases.defer_planning_item(s, rel, pi)
        assert out["status"] == "Deferred"
        assert releases.transition(s, rel, "reconciliation")[
            "release_status"] == "reconciliation"


def test_defer_rejects_out_of_scope_pi(v2_env):
    with session_scope() as s:
        rel, _, _, _ = _scoped(s)
        other = planning_items.create(
            s, title="OTHER", item_type="pending_work", executive_summary=_SUMMARY,
        )["identifier"]
        with pytest.raises(ConflictError, match="not in scope"):
            releases.defer_planning_item(s, rel, other)
