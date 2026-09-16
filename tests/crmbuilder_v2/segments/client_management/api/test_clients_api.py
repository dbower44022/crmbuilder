"""Client REST endpoint tests (PI-512 / REQ-589): ``/clients`` and the two
client routes on ``/engagements``."""

from __future__ import annotations


def _ok(body: dict) -> dict:
    assert body["errors"] is None
    return body["data"]


def _make_engagement(client, identifier: str, code: str) -> None:
    r = client.post(
        "/engagements",
        json={
            "engagement_identifier": identifier,
            "engagement_code": code,
            "engagement_name": f"Engagement {code}",
            "engagement_purpose": "p",
        },
    )
    assert r.status_code == 201, r.text


def test_client_crud_round_trip(client):
    assert _ok(client.get("/clients").json()) == []
    assert _ok(client.get("/clients/next-identifier").json()) == {"next": "CLI-001"}

    r = client.post("/clients", json={"client_name": "Cleveland Business Mentors"})
    assert r.status_code == 201, r.text
    created = _ok(r.json())
    assert created["client_identifier"] == "CLI-001"
    assert created["client_status"] == "active"
    assert created["engagements"] == []

    r = client.patch("/clients/CLI-001", json={"client_notes": "nonprofit"})
    assert _ok(r.json())["client_notes"] == "nonprofit"

    r = client.put(
        "/clients/CLI-001",
        json={"client_name": "Cleveland Business Mentors", "client_status": "inactive"},
    )
    body = _ok(r.json())
    assert body["client_status"] == "inactive" and body["client_notes"] is None

    r = client.post("/clients", json={"client_name": "cleveland business mentors"})
    assert r.status_code == 422

    r = client.get("/clients/CLI-404")
    assert r.status_code == 404

    r = client.delete("/clients/CLI-001")
    assert _ok(r.json())["client_deleted_at"] is not None
    assert _ok(client.get("/clients").json()) == []
    assert len(_ok(client.get("/clients?include_deleted=true").json())) == 1
    r = client.post("/clients/CLI-001/restore")
    assert _ok(r.json())["client_deleted_at"] is None


def test_engagement_clients_round_trip(client):
    _make_engagement(client, "ENG-002", "ALPHA")
    _make_engagement(client, "ENG-003", "BETA")
    a = _ok(client.post("/clients", json={"client_name": "A"}).json())["client_identifier"]
    b = _ok(client.post("/clients", json={"client_name": "B"}).json())["client_identifier"]

    r = client.get("/engagements/ENG-002/clients")
    assert _ok(r.json()) == {"engagement": "ENG-002", "clients": [], "primary": None}

    r = client.put("/engagements/ENG-002/clients", json={"clients": [a]})
    answer = _ok(r.json())
    assert answer["primary"] == a
    assert [c["client_identifier"] for c in answer["clients"]] == [a]

    # A chapter engagement serves two clients, one primary.
    r = client.put("/engagements/ENG-003/clients", json={"clients": [a, b], "primary": b})
    answer = _ok(r.json())
    assert answer["primary"] == b
    assert [c["client_identifier"] for c in answer["clients"]] == [b, a]

    held = _ok(client.get(f"/clients/{a}/engagements").json())
    assert [(e["engagement_identifier"], e["is_primary"]) for e in held] == [
        ("ENG-002", True),
        ("ENG-003", False),
    ]
    assert _ok(client.get(f"/clients/{a}").json())["engagements"] == ["ENG-002", "ENG-003"]

    # A client holding engagements cannot be deleted.
    r = client.delete(f"/clients/{a}")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "client_holds_engagements"

    # Unknown client or primary outside the set: refused.
    r = client.put("/engagements/ENG-002/clients", json={"clients": ["CLI-404"]})
    assert r.status_code == 422
    r = client.put("/engagements/ENG-002/clients", json={"clients": [a], "primary": b})
    assert r.status_code == 422
    r = client.put("/engagements/ENG-404/clients", json={"clients": [a]})
    assert r.status_code == 404

    # Empty set: no client.
    r = client.put("/engagements/ENG-002/clients", json={"clients": []})
    assert _ok(r.json())["primary"] is None
