"""Living drift (requirements-provenance Phase 4).

When a requirement's meaning changes (a content edit, or a change-decision
reopen), every descendant down the refines-chain is flagged needs_review; an
AI-derived descendant that was confirmed additionally re-opens for re-approval.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories.requirement import _get_row


def _make(client, name):
    r = client.post(
        "/requirements",
        json={
            "requirement_name": name,
            "requirement_description": "What the system must do.",
            "requirement_acceptance_summary": "Verifiable when it happens.",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["requirement_identifier"]


def _ref(client, st, si, tt, ti, rel):
    r = client.post(
        "/references",
        json={
            "source_type": st, "source_id": si,
            "target_type": tt, "target_id": ti, "relationship": rel,
        },
    )
    assert r.status_code == 201, r.text
    return r


def _refines(client, child, parent):
    return _ref(client, "requirement", child, "requirement", parent,
                "requirement_refines_requirement")


def _get(client, rid):
    return client.get(f"/requirements/{rid}").json()["data"]


def test_editing_parent_flags_child_needs_review(client):
    pid = _make(client, "Parent capability")
    cid = _make(client, "Child capability")
    _refines(client, cid, pid)
    assert _get(client, cid)["requirement_review_state"] == "current"
    r = client.patch(f"/requirements/{pid}", json={"requirement_description":"a changed meaning"})
    assert r.status_code == 200, r.text
    assert _get(client, cid)["requirement_review_state"] == "needs_review"


def test_edit_propagates_to_grandchild(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    gid = _make(client, "Grandchild")
    _refines(client, cid, pid)
    _refines(client, gid, cid)
    client.patch(f"/requirements/{pid}", json={"requirement_description":"changed"})
    assert _get(client, cid)["requirement_review_state"] == "needs_review"
    assert _get(client, gid)["requirement_review_state"] == "needs_review"


def test_change_decision_reopen_flags_descendants(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    _refines(client, cid, pid)
    # a change decision reopens the parent; its descendants are flagged too
    _ref(client, "requirement", pid, "decision", "DEC-001",
         "requirement_changed_by_decision")
    assert _get(client, pid)["requirement_status"] == "candidate"
    assert _get(client, cid)["requirement_review_state"] == "needs_review"


def test_notes_only_edit_does_not_flag(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    _refines(client, cid, pid)
    # editing only notes is not a meaning change — no propagation
    r = client.patch(f"/requirements/{pid}", json={"requirement_notes": "internal note"})
    assert r.status_code == 200, r.text
    assert _get(client, cid)["requirement_review_state"] == "current"


def test_ai_derived_descendant_reopens_on_ancestor_change(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    _refines(client, cid, pid)
    # parent carries provenance + topic; the child inherits both
    _ref(client, "requirement", pid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _ref(client, "requirement", pid, "topic", "TOP-001",
         "requirement_belongs_to_topic")
    # mark the child AI-derived (origin is not settable via the API yet)
    with session_scope() as s:
        _get_row(s, cid).requirement_origin = "ai_derived"
    # approve the child -> confirmed (inherits the parent's provenance + topic)
    _ref(client, "requirement", cid, "decision", "DEC-001",
         "requirement_approved_by_decision")
    assert _get(client, cid)["requirement_status"] == "confirmed"
    # editing the parent reopens the AI-derived, confirmed child for re-approval
    client.patch(f"/requirements/{pid}", json={"requirement_description":"changed meaning"})
    child = _get(client, cid)
    assert child["requirement_status"] == "candidate"
    assert child["requirement_review_state"] == "needs_review"
    assert child["requirement_approved_at"] is None
