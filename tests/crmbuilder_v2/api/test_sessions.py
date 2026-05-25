"""Sessions endpoints (append-only)."""

from __future__ import annotations


def _create(client, identifier="SES-001", **overrides):
    body = {
        "identifier": identifier,
        "title": f"{identifier} title",
        "session_date": "05-07-26",
        "status": "Complete",
    }
    body.update(overrides)
    return client.post("/sessions", json=body)


def test_create_then_get(client):
    r = _create(client)
    assert r.status_code == 201
    r = client.get("/sessions/SES-001")
    assert r.status_code == 200


def test_no_patch_endpoint(client):
    """Append-only — there is no PATCH route on /sessions."""
    r = client.patch("/sessions/SES-001", json={})
    assert r.status_code == 405  # Method Not Allowed


def test_list_with_limit(client):
    _create(client, identifier="SES-001", session_date="05-01-26")
    _create(client, identifier="SES-002", session_date="05-07-26")
    r = client.get("/sessions?limit=1")
    rows = r.json()["data"]
    assert len(rows) == 1
    assert rows[0]["identifier"] == "SES-002"


def test_delete(client):
    _create(client)
    client.delete("/sessions/SES-001")
    r = client.get("/sessions/SES-001")
    assert r.status_code == 404


# PI-002 — POST without identifier returns 201 with server-assigned value.


def test_post_without_identifier_assigns_one(client):
    r = client.post(
        "/sessions",
        json={"title": "Auto", "session_date": "05-25-26", "status": "Complete"},
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["identifier"] == "SES-001"


def test_post_with_invalid_identifier_format_returns_422(client):
    r = client.post(
        "/sessions",
        json={
            "identifier": "SES-1",
            "title": "Bad",
            "session_date": "05-25-26",
            "status": "Complete",
        },
    )
    assert r.status_code == 422, r.json()
