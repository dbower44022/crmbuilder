"""PI-229 / REQ-251 — reviewer-driven approval from the Review surface.

`POST /review/approvals` records a governed approving decision per requirement
and confirms each via the approving-decision edge + its gates (never a status
edit). Covers: a rooted candidate confirms; an unrooted one fails with the
gate's reason and stays candidate; batch isolation (one failure doesn't block
others); idempotent already-confirmed; reviewer required.
"""

from __future__ import annotations


def _make(client, **overrides) -> str:
    body = {
        "requirement_name": overrides.pop("requirement_name", "A capability"),
        "requirement_description": overrides.pop(
            "requirement_description", "What the system must do for its users."
        ),
        "requirement_acceptance_summary": overrides.pop(
            "requirement_acceptance_summary",
            "Verifiable when the described thing happens for a user.",
        ),
    }
    body.update(overrides)
    r = client.post("/requirements", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]["requirement_identifier"]


def _ref(client, src, rel, tgt_type, tgt):
    return client.post(
        "/references",
        json={"source_type": "requirement", "source_id": src,
              "target_type": tgt_type, "target_id": tgt, "relationship": rel},
    )


def _rooted(client, name) -> str:
    """A candidate with provenance (conversation + topic) — confirmable."""
    rid = _make(client, requirement_name=name)
    _ref(client, rid, "requirement_defined_in_conversation", "conversation", "CNV-001")
    _ref(client, rid, "requirement_belongs_to_topic", "topic", "TOP-001")
    return rid


def _approve(client, ids, reviewer="Doug Bower", note=None):
    body = {"requirement_identifiers": ids, "reviewer": reviewer,
            "decision_date": "2026-06-18"}
    if note is not None:
        body["note"] = note
    return client.post("/review/approvals", json=body)


def test_approve_confirms_rooted_candidate(client):
    rid = _rooted(client, "Approvable one")
    r = _approve(client, [rid], note="looks good")
    assert r.status_code == 201, r.text
    res = r.json()["data"]
    assert res[0]["identifier"] == rid
    assert res[0]["outcome"] == "confirmed"
    assert res[0]["decision_identifier"].startswith("DEC-")
    assert res[0]["reason"] is None
    rec = client.get(f"/requirements/{rid}").json()["data"]
    assert rec["requirement_status"] == "confirmed"
    assert rec["requirement_approved_at"] is not None


def test_approve_unrooted_fails_and_stays_candidate(client):
    rid = _make(client, requirement_name="No topic")
    _ref(client, rid, "requirement_defined_in_conversation", "conversation", "CNV-001")
    res = _approve(client, [rid]).json()["data"]
    assert res[0]["outcome"] == "failed"
    assert "topic" in res[0]["reason"].lower()
    assert res[0]["decision_identifier"] is None
    # stayed candidate; no approving decision lingered (savepoint rolled back)
    assert client.get(f"/requirements/{rid}").json()["data"][
        "requirement_status"] == "candidate"


def test_batch_isolation_and_order(client):
    good = _rooted(client, "Good one")
    bad = _make(client, requirement_name="Bad one no topic")
    _ref(client, bad, "requirement_defined_in_conversation", "conversation", "CNV-001")
    res = _approve(client, [good, bad]).json()["data"]
    assert [r["identifier"] for r in res] == [good, bad]  # order-preserving
    by = {r["identifier"]: r for r in res}
    assert by[good]["outcome"] == "confirmed"
    assert by[bad]["outcome"] == "failed"
    # the good one really confirmed despite the sibling's failure
    assert client.get(f"/requirements/{good}").json()["data"][
        "requirement_status"] == "confirmed"


def test_already_confirmed_is_idempotent(client):
    rid = _rooted(client, "Twice")
    _approve(client, [rid])
    res = _approve(client, [rid]).json()["data"]
    assert res[0]["outcome"] == "already_confirmed"
    assert res[0]["decision_identifier"] is None


def test_reviewer_required(client):
    rid = _rooted(client, "Needs a reviewer")
    r = _approve(client, [rid], reviewer="   ")
    assert r.status_code == 422
    assert client.get(f"/requirements/{rid}").json()["data"][
        "requirement_status"] == "candidate"


def test_confirm_records_governed_decision_naming_reviewer_and_edge(client):
    """Contract acceptance #3 + Actor: each confirmed requirement gets a governed
    approving decision authored by — and naming — the reviewer, plus a
    ``requirement_approved_by_decision`` edge to it. Confirmation is *only* via
    that governed path, never a status edit."""
    rid = _rooted(client, "Edge and decision")
    res = _approve(client, [rid], reviewer="Dana Reviewer").json()["data"][0]
    assert res["outcome"] == "confirmed"
    did = res["decision_identifier"]

    dec = client.get(f"/decisions/{did}").json()["data"]
    assert dec["status"] == "Active"  # a real, active governed decision
    # the reviewer is named on the record, and the requirement under review cited
    assert "Dana Reviewer" in dec["context"]
    assert "Dana Reviewer" in dec["executive_summary"]
    assert rid in dec["context"]

    # the approving-decision edge exists from the requirement to that decision
    edges = client.get(
        "/references",
        params={"target_id": did,
                "relationship_kind": "requirement_approved_by_decision"},
    ).json()["data"]
    assert any(e["source_id"] == rid and e["target_id"] == did for e in edges)


def test_reviewer_note_is_folded_into_the_decision(client):
    """Contract Effects: a reviewer note is carried into the approving decision's
    context and summary, so the rationale travels with the governed record."""
    rid = _rooted(client, "Noted approval")
    did = _approve(
        client, [rid], reviewer="Dana Reviewer",
        note="Confirmed scope with the PM on 06-18.",
    ).json()["data"][0]["decision_identifier"]
    dec = client.get(f"/decisions/{did}").json()["data"]
    assert "Confirmed scope with the PM on 06-18." in dec["context"]
    assert "Confirmed scope with the PM on 06-18." in dec["executive_summary"]
