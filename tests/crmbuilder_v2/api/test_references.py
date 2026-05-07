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
