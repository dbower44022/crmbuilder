"""References endpoints — DEC-006 universal pattern."""

from __future__ import annotations


def _add_session_decision_ref(client, sid="SES-001", did="DEC-001"):
    return client.post(
        "/references",
        json={
            "source_type": "session",
            "source_id": sid,
            "target_type": "decision",
            "target_id": did,
            "relationship": "decided_in",
        },
    )


def test_create_and_list(client):
    r = _add_session_decision_ref(client)
    assert r.status_code == 201
    r = client.get("/references")
    rows = r.json()["data"]
    assert len(rows) == 1


def test_list_from_to_touching(client):
    _add_session_decision_ref(client, did="DEC-001")
    _add_session_decision_ref(client, did="DEC-002")

    r = client.get("/references/from/session/SES-001")
    assert len(r.json()["data"]) == 2

    r = client.get("/references/to/decision/DEC-001")
    assert len(r.json()["data"]) == 1

    r = client.get("/references/touching/session/SES-001")
    body = r.json()["data"]
    assert len(body["as_source"]) == 2
    assert len(body["as_target"]) == 0


def test_invalid_relationship_400(client):
    r = client.post(
        "/references",
        json={
            "source_type": "session",
            "source_id": "X",
            "target_type": "decision",
            "target_id": "Y",
            "relationship": "vibes_with",
        },
    )
    assert r.status_code == 400


def test_duplicate_409(client):
    _add_session_decision_ref(client)
    r = _add_session_decision_ref(client)
    assert r.status_code == 409


def test_delete_via_post(client):
    _add_session_decision_ref(client)
    r = client.post(
        "/references/delete",
        json={
            "source_type": "session",
            "source_id": "SES-001",
            "target_type": "decision",
            "target_id": "DEC-001",
            "relationship": "decided_in",
        },
    )
    assert r.status_code == 200
    r = client.get("/references")
    assert r.json()["data"] == []


def test_delete_by_id(client):
    """v0.3 slice C: DELETE /references/{id} hard-deletes by integer id."""
    create = _add_session_decision_ref(client)
    ref_id = create.json()["data"]["id"]

    r = client.delete(f"/references/{ref_id}")
    assert r.status_code == 200
    r = client.get("/references")
    assert r.json()["data"] == []


def test_delete_by_id_unknown_returns_404(client):
    r = client.delete("/references/999999")
    assert r.status_code == 404


def test_post_references_conversation_orchestrates_conversation(client):
    """PI-080: ``conversation_orchestrates_conversation`` round-trips
    through POST /references. Source and target are both conversations;
    no entity rows are needed (references are soft pointers per the
    DEC-006 universal pattern)."""
    r = client.post(
        "/references",
        json={
            "source_type": "conversation",
            "source_id": "CNV-901",
            "target_type": "conversation",
            "target_id": "CNV-902",
            "relationship": "conversation_orchestrates_conversation",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()["data"]
    assert body["relationship"] == "conversation_orchestrates_conversation"
    assert body["source_type"] == "conversation"
    assert body["target_type"] == "conversation"


def test_post_references_resolves_flips_status(client):
    """PI-030 slice A: POST /references with relationship=resolves
    triggers the atomic status flip on the target planning_item."""
    ws_resp = client.post("/workstreams", json={
        "workstream_name": "WS CONV-995",
        "workstream_purpose": "p",
        "workstream_description": "d",
    })
    wid = ws_resp.json()["data"]["workstream_identifier"]
    client.post("/conversations", json={
        "conversation_title": "Conv CONV-995",
        "conversation_purpose": "p",
        "conversation_description": "d",
        "conversation_identifier": "CONV-995",
        "references": [{
            "source_type": "conversation", "source_id": "CONV-995",
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    })
    client.post("/planning-items", json={
        "identifier": "PI-995",
        "title": "Test PI for resolves",
        "item_type": "pending_work",
        "status": "Open",
    })

    r = client.post("/references", json={
        "source_type": "conversation",
        "source_id": "CONV-995",
        "target_type": "planning_item",
        "target_id": "PI-995",
        "relationship": "resolves",
    })
    assert r.status_code == 201

    r = client.get("/planning-items/PI-995")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Resolved"
