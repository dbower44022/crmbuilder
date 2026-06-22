"""REQ-265 — planning excludes already-delivered requirements.

A requirement whose implementing planning item has reached a delivered state
(``In Review`` / ``Resolved``) must not be planned, designed, or built again. The
predicates live in ``releases``; the release scheduler applies them in
``_confirmed_requirements`` (the demands-agent input) and in the ``_plan``
decompose loop (skipping a planning item whose every requirement is delivered).
"""

from __future__ import annotations

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import PlanningItem, Requirement
from crmbuilder_v2.access.repositories import (
    planning_items,
    references,
    releases,
    requirement,
)


def _link(s, src_t, src, tgt_t, tgt, rel):
    references.create(
        s, source_type=src_t, source_id=src,
        target_type=tgt_t, target_id=tgt, relationship=rel,
    )


def _req(s, name="REQ x", *, confirmed=True):
    rid = requirement.create_requirement(
        s, name=name, description="d", acceptance_summary="a"
    )["requirement_identifier"]
    if confirmed:
        row = get_by_identifier(s, Requirement, Requirement.requirement_identifier, rid)
        row.requirement_status = "confirmed"
        s.flush()
    return rid


def _pi(s, title, *, status="Draft"):
    pid = planning_items.create(
        s, title=title, item_type="pending_work",
        executive_summary="x" * 250, area=["storage"],
    )["identifier"]
    if status != "Draft":
        row = get_by_identifier(s, PlanningItem, PlanningItem.identifier, pid)
        row.status = status
        s.flush()
    return pid


def _implements(s, pid, rid):
    _link(s, "planning_item", pid, "requirement", rid,
          "planning_item_implements_requirement")


# --- the predicate: requirement_is_delivered -------------------------------


def test_requirement_with_no_implementing_pi_is_not_delivered(v2_env):
    with session_scope() as s:
        rid = _req(s)
        assert releases.requirement_is_delivered(s, rid) is False


def test_requirement_with_draft_pi_is_not_delivered(v2_env):
    with session_scope() as s:
        rid = _req(s)
        pid = _pi(s, "PI draft", status="Draft")
        _implements(s, pid, rid)
        assert releases.requirement_is_delivered(s, rid) is False


def test_requirement_with_resolved_pi_is_delivered(v2_env):
    with session_scope() as s:
        rid = _req(s)
        pid = _pi(s, "PI resolved", status="Resolved")
        _implements(s, pid, rid)
        assert releases.requirement_is_delivered(s, rid) is True


def test_requirement_with_in_review_pi_is_delivered(v2_env):
    with session_scope() as s:
        rid = _req(s)
        pid = _pi(s, "PI in review", status="In Review")
        _implements(s, pid, rid)
        assert releases.requirement_is_delivered(s, rid) is True


def test_delivered_if_any_implementing_pi_is_delivered(v2_env):
    # The same requirement implemented by a Draft PI AND a Resolved PI is delivered.
    with session_scope() as s:
        rid = _req(s)
        _implements(s, _pi(s, "PI a", status="Draft"), rid)
        _implements(s, _pi(s, "PI b", status="Resolved"), rid)
        assert releases.requirement_is_delivered(s, rid) is True


# --- the predicate: pi_has_undelivered_requirements ------------------------


def test_pi_with_no_requirements_is_buildable(v2_env):
    # No traced requirements → we cannot prove it is done, so do not suppress it.
    with session_scope() as s:
        pid = _pi(s, "PI untraced")
        assert releases.pi_has_undelivered_requirements(s, pid) is True


def test_pi_all_requirements_delivered_has_nothing_to_build(v2_env):
    with session_scope() as s:
        pid = _pi(s, "PI done")
        delivered_pi = _pi(s, "PI shipper", status="Resolved")
        r1 = _req(s, "REQ one")
        _implements(s, pid, r1)
        _implements(s, delivered_pi, r1)  # r1 already delivered elsewhere
        assert releases.pi_has_undelivered_requirements(s, pid) is False


def test_pi_with_one_undelivered_requirement_is_buildable(v2_env):
    with session_scope() as s:
        pid = _pi(s, "PI mixed")
        shipper = _pi(s, "PI shipper", status="Resolved")
        delivered = _req(s, "REQ delivered")
        fresh = _req(s, "REQ fresh")
        _implements(s, pid, delivered)
        _implements(s, shipper, delivered)  # delivered elsewhere
        _implements(s, pid, fresh)          # but this one is not
        assert releases.pi_has_undelivered_requirements(s, pid) is True
