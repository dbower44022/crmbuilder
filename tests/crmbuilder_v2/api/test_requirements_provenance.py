"""Requirements-provenance Phase 2 — decision-outcome flips + activation gate.

Covers the deliver / change outcomes wired into references.create (decline is
covered by the existing rejected_by_decision tests):

- approve activates a rooted requirement (candidate -> confirmed + approved_at);
- approve of an UNROOTED requirement is rejected and rolls back (no orphan
  capability, enforced at activation per decision A1);
- provenance is inherited up the requirement_refines_requirement chain;
- a change decision reopens a confirmed requirement (gated, decision B1).
"""

from __future__ import annotations


def _make(client, **overrides) -> dict:
    body = {
        "requirement_name": overrides.pop("requirement_name", "A capability"),
        "requirement_description": overrides.pop(
            "requirement_description", "What the system must do."
        ),
        "requirement_acceptance_summary": overrides.pop(
            "requirement_acceptance_summary", "Verifiable when the thing happens."
        ),
    }
    body.update(overrides)
    r = client.post("/requirements", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _ref(client, src_type, src_id, tgt_type, tgt_id, rel):
    return client.post(
        "/references",
        json={
            "source_type": src_type,
            "source_id": src_id,
            "target_type": tgt_type,
            "target_id": tgt_id,
            "relationship": rel,
        },
    )


def _provenance(client, rid, cid="CNV-001"):
    return _ref(client, "requirement", rid, "conversation", cid,
                "requirement_defined_in_conversation")


def _topic(client, rid, tid="TOP-001"):
    return _ref(client, "requirement", rid, "topic", tid,
                "requirement_belongs_to_topic")


def _approve(client, rid, did="DEC-001"):
    return _ref(client, "requirement", rid, "decision", did,
                "requirement_approved_by_decision")


def test_approve_activates_rooted_requirement(client):
    rid = _make(client)["requirement_identifier"]
    assert _provenance(client, rid).status_code == 201
    assert _topic(client, rid).status_code == 201
    assert _approve(client, rid).status_code == 201
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_approved_at"] is not None


def test_approve_without_provenance_is_rejected_and_rolls_back(client):
    rid = _make(client)["requirement_identifier"]
    assert _topic(client, rid).status_code == 201  # has a topic but no provenance
    resp = _approve(client, rid)
    assert resp.status_code == 422, resp.text
    assert "provenance" in resp.text
    # status unchanged and the approve edge did not land (transaction rolled back).
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"
    assert rec["requirement_approved_at"] is None
    edges = client.get(f"/references/from/requirement/{rid}").json()["data"]
    assert all(
        e["relationship"] != "requirement_approved_by_decision" for e in edges
    )


def test_approve_without_topic_is_rejected(client):
    rid = _make(client)["requirement_identifier"]
    assert _provenance(client, rid).status_code == 201  # rooted but no topic
    resp = _approve(client, rid)
    assert resp.status_code == 422, resp.text
    assert "topic" in resp.text
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"


def test_approve_inherits_provenance_and_topic_through_parent(client):
    pid = _make(client, requirement_name="Parent capability")["requirement_identifier"]
    cid = _make(client, requirement_name="Child capability")["requirement_identifier"]
    assert _provenance(client, pid).status_code == 201
    assert _topic(client, pid).status_code == 201
    # child refines parent (child -> parent)
    assert _ref(client, "requirement", cid, "requirement", pid,
                "requirement_refines_requirement").status_code == 201
    # the child has no own provenance/topic edges, but inherits the parent's
    assert _approve(client, cid).status_code == 201
    rec = client.get(f"/requirements/{cid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"


def test_change_decision_reopens_confirmed_requirement(client):
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)
    _approve(client, rid)
    assert client.get(f"/requirements/{rid}").json()["data"]["requirement_status"] == "confirmed"
    # a change decision reopens it: back to candidate + needs_review, approval cleared
    assert _ref(client, "requirement", rid, "decision", "DEC-002",
                "requirement_changed_by_decision").status_code == 201
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"
    assert rec["requirement_review_state"] == "needs_review"
    assert rec["requirement_approved_at"] is None


def test_fresh_approval_leaves_review_state_current(client):
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)
    _approve(client, rid)
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_review_state"] == "current"


def test_approve_after_reopen_clears_needs_review(client):
    """REQ-249 — an approval that immediately follows a change-decision reopen
    returns review_state to current, leaving the requirement cleanly active
    rather than approved-but-flagged."""
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)
    _approve(client, rid)
    # change decision reopens: candidate + needs_review, approval cleared
    assert _ref(client, "requirement", rid, "decision", "DEC-002",
                "requirement_changed_by_decision").status_code == 201
    assert client.get(f"/requirements/{rid}").json()["data"][
        "requirement_review_state"] == "needs_review"
    # re-approve via a fresh decision edge: back to confirmed AND current
    assert _approve(client, rid, did="DEC-003").status_code == 201
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_review_state"] == "current"
    assert rec["requirement_approved_at"] is not None


def test_reapprove_clears_drift_flag_on_already_confirmed(client):
    """A confirmed, human_defined requirement flagged needs_review by living
    drift stays confirmed (status unchanged). Re-approving it is the human
    sign-off that clears the lingering needs_review flag (REQ-249)."""
    pid = _make(client, requirement_name="Parent capability")["requirement_identifier"]
    cid = _make(client, requirement_name="Child capability")["requirement_identifier"]
    _provenance(client, pid)
    _topic(client, pid)
    # child refines parent, inheriting its provenance + topic; approve the child
    assert _ref(client, "requirement", cid, "requirement", pid,
                "requirement_refines_requirement").status_code == 201
    _approve(client, cid)
    assert client.get(f"/requirements/{cid}").json()["data"][
        "requirement_status"] == "confirmed"
    # editing the parent flags the (human_defined) confirmed child for review,
    # but leaves its status confirmed
    client.patch(f"/requirements/{pid}",
                 json={"requirement_description": "a changed meaning"})
    flagged = client.get(f"/requirements/{cid}").json()["data"]
    assert flagged["requirement_status"] == "confirmed"
    assert flagged["requirement_review_state"] == "needs_review"
    # re-approving the still-confirmed child clears the flag
    assert _approve(client, cid, did="DEC-002").status_code == 201
    rec = client.get(f"/requirements/{cid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_review_state"] == "current"


def _record(client, rid, did="DEC-002"):
    return _ref(client, "requirement", rid, "decision", did,
                "requirement_recorded_by_decision")


def test_recorded_decision_leaves_confirmed_requirement_untouched(client):
    """REQ-476 — the status-neutral outcome. A decision that records a
    completion against a confirmed requirement must not de-confirm it; this is
    the regression DEC-903 caused on REQ-472 by using the change edge."""
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)
    _approve(client, rid)
    before = client.get(f"/requirements/{rid}").json()["data"]
    assert before["requirement_status"] == "confirmed"

    assert _record(client, rid).status_code == 201

    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_review_state"] == "current"
    assert rec["requirement_approved_at"] == before["requirement_approved_at"]


def test_recorded_decision_does_not_activate_a_candidate(client):
    """The neutral edge records; it never approves. A candidate stays candidate
    even when the requirement is fully rooted and would otherwise activate."""
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)

    assert _record(client, rid).status_code == 201

    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"
    assert rec["requirement_approved_at"] is None


def test_recorded_decision_does_not_require_provenance(client):
    """Recording is not an approval, so it is not provenance-gated: an unrooted
    requirement (no conversation, no topic) accepts the edge, where approval
    would roll the transaction back."""
    rid = _make(client)["requirement_identifier"]

    assert _record(client, rid).status_code == 201

    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"


def test_change_edge_still_reopens_after_neutral_kind_added(client):
    """The neutral kind must not blunt the change outcome it sits beside."""
    rid = _make(client)["requirement_identifier"]
    _provenance(client, rid)
    _topic(client, rid)
    _approve(client, rid)
    assert _record(client, rid, did="DEC-002").status_code == 201
    # the change edge still reopens, unaffected by the recorded edge alongside it
    assert _ref(client, "requirement", rid, "decision", "DEC-003",
                "requirement_changed_by_decision").status_code == 201
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "candidate"
    assert rec["requirement_review_state"] == "needs_review"
    assert rec["requirement_approved_at"] is None
