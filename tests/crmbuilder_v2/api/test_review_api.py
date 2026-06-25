"""Review surface data layer — requirements-provenance Phase 6.

topic-review tree (with sub-topic pruning), the read-back document, and the
approval + drift queues.
"""

from __future__ import annotations


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


def _refines(client, child, parent):
    _ref(client, "requirement", child, "requirement", parent,
         "requirement_refines_requirement")


def _topic(client, rid, tid):
    _ref(client, "requirement", rid, "topic", tid, "requirement_belongs_to_topic")


def test_topic_review_returns_the_tree(client):
    pid = _make(client, "Parent capability")
    cid = _make(client, "Child capability")
    _refines(client, cid, pid)
    _topic(client, pid, "TOP-001")
    data = client.get("/review/topics/TOP-001").json()["data"]
    assert data["topic"] == "TOP-001"
    roots = data["requirements"]
    assert len(roots) == 1
    assert roots[0]["identifier"] == pid
    assert [c["identifier"] for c in roots[0]["children"]] == [cid]


def test_child_relinked_to_subtopic_is_pruned(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    gid = _make(client, "Grandchild")
    _refines(client, cid, pid)
    _refines(client, gid, cid)
    _topic(client, pid, "TOP-001")
    _topic(client, cid, "TOP-002")  # child re-homed to a sub-topic
    # The parent topic's tree no longer contains the re-homed child.
    top1 = client.get("/review/topics/TOP-001").json()["data"]["requirements"]
    assert top1[0]["identifier"] == pid
    assert all(c["identifier"] != cid for c in top1[0]["children"])
    # The sub-topic owns the child, and the grandchild inherits the sub-topic.
    top2 = client.get("/review/topics/TOP-002").json()["data"]["requirements"]
    assert top2[0]["identifier"] == cid
    assert [c["identifier"] for c in top2[0]["children"]] == [gid]


def test_readback_document_renders_the_requirements(client):
    pid = _make(client, "Parent capability")
    _topic(client, pid, "TOP-001")
    doc = client.get("/review/topics/TOP-001/document").json()["data"]["document"]
    assert pid in doc
    assert "Parent capability" in doc
    assert "topic TOP-001" in doc


def test_approval_queue_shows_what_each_candidate_needs(client):
    rid = _make(client, "A capability")
    row = next(
        x for x in client.get("/review/approval-queue").json()["data"]
        if x["identifier"] == rid
    )
    assert row["has_provenance"] is False
    assert row["has_topic"] is False
    _ref(client, "requirement", rid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _topic(client, rid, "TOP-001")
    row = next(
        x for x in client.get("/review/approval-queue").json()["data"]
        if x["identifier"] == rid
    )
    assert row["has_provenance"] is True
    assert row["has_topic"] is True


def test_drift_queue_lists_needs_review(client):
    pid = _make(client, "Parent")
    cid = _make(client, "Child")
    _refines(client, cid, pid)
    # editing the parent flags the child needs_review
    client.patch(f"/requirements/{pid}", json={"requirement_description": "changed"})
    ids = [x["identifier"] for x in client.get("/review/drift-queue").json()["data"]]
    assert cid in ids


def test_signoff_records_and_snapshots_the_topic(client):
    pid = _make(client, "Parent capability")
    _topic(client, pid, "TOP-001")
    r = client.post(
        "/review/signoffs",
        json={
            "signoff_topic_identifier": "TOP-001",
            "signoff_reviewer": "Doug",
            "signoff_attestation": "Matches intent.",
        },
    )
    assert r.status_code == 201, r.text
    rec = r.json()["data"]
    assert rec["signoff_topic_identifier"] == "TOP-001"
    assert rec["signoff_reviewer"] == "Doug"
    assert any(x["identifier"] == pid for x in rec["signoff_reviewed_requirements"])
    listed = client.get("/review/signoffs?topic=TOP-001").json()["data"]
    assert len(listed) == 1
    assert listed[0]["signoff_attestation"] == "Matches intent."


def test_signoff_requires_a_reviewer(client):
    r = client.post(
        "/review/signoffs",
        json={
            "signoff_topic_identifier": "TOP-001",
            "signoff_reviewer": "   ",
            "signoff_attestation": "Matches intent.",
        },
    )
    assert r.status_code == 422, r.text


# -- Drift re-approval (PI-311 / REQ-345) -----------------------------------
# A confirmed, human_defined requirement that living drift flags needs_review
# stays confirmed (only ai_derived reopens to candidate). The governed approvals
# endpoint must re-affirm it — record a fresh approving decision + edge that
# clears the flag — rather than short-circuiting to already_confirmed.


def _get_req(client, rid):
    return client.get(f"/requirements/{rid}").json()["data"]


def _approve(client, rid):
    r = client.post("/review/approvals", json={
        "requirement_identifiers": [rid],
        "reviewer": "doug@x.com", "decision_date": "2026-06-24"})
    assert r.status_code == 201, r.text
    return r.json()["data"][0]


def test_reapprove_clears_drift_on_confirmed_human_defined(client):
    pid = _make(client, "Parent capability")
    cid = _make(client, "Child capability")
    _refines(client, cid, pid)
    _ref(client, "requirement", pid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _topic(client, pid, "TOP-001")
    # first approval through the governed endpoint -> real decision, child confirmed
    first = _approve(client, cid)
    assert first["outcome"] == "confirmed", first
    assert _get_req(client, cid)["requirement_status"] == "confirmed"

    # editing the parent's meaning flags the human_defined child needs_review
    # but leaves it confirmed (not reopened to candidate)
    client.patch(f"/requirements/{pid}",
                 json={"requirement_description": "A different thing now."})
    child = _get_req(client, cid)
    assert child["requirement_status"] == "confirmed"
    assert child["requirement_review_state"] == "needs_review"

    # re-approval records a SECOND approving decision + edge and clears the flag
    second = _approve(client, cid)
    assert second["outcome"] == "confirmed", second
    assert second["decision_identifier"], second
    assert second["decision_identifier"] != first["decision_identifier"]

    cleared = _get_req(client, cid)
    assert cleared["requirement_status"] == "confirmed"
    assert cleared["requirement_review_state"] == "current"


def test_reapprove_confirmed_current_is_noop(client):
    # a confirmed + current requirement is unchanged: already_confirmed, no
    # new decision recorded.
    rid = _make(client, "Solo capability")
    _ref(client, "requirement", rid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _topic(client, rid, "TOP-001")
    assert _approve(client, rid)["outcome"] == "confirmed"
    assert _get_req(client, rid)["requirement_review_state"] == "current"

    again = _approve(client, rid)
    assert again["outcome"] == "already_confirmed", again
    assert again["decision_identifier"] is None, again
