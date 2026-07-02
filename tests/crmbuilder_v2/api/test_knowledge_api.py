"""REL-039 / PI-357 — preference / lesson / reference_pointer REST routers.

Exercises the envelope-wrapped CRUD set for the three knowledge classes
(REQ-416, DEC-891): list / next-identifier / get / create (identifier optional) /
patch / delete, plus the vocab-rejection and scope paths.
"""

from __future__ import annotations


def test_preference_crud_roundtrip(client):
    created = client.post(
        "/preferences",
        json={"category": "interaction", "title": "No confirmation",
              "body": "Execute autonomously.", "applies_to": "claude_code"},
    )
    assert created.status_code == 201
    data = created.json()["data"]
    assert data["identifier"] == "PRF-001"
    assert data["scope"] == "system"

    nxt = client.get("/preferences/next-identifier").json()["data"]["next"]
    assert nxt == "PRF-002"

    got = client.get("/preferences/PRF-001").json()["data"]
    assert got["title"] == "No confirmation"

    listing = client.get("/preferences", params={"category": "interaction"}).json()["data"]
    assert [p["identifier"] for p in listing] == ["PRF-001"]

    patched = client.patch("/preferences/PRF-001", json={"status": "retired"}).json()["data"]
    assert patched["status"] == "retired"

    assert client.delete("/preferences/PRF-001").status_code == 200
    assert client.get("/preferences/PRF-001").status_code == 404


def test_preference_rejects_bad_vocab(client):
    r = client.post("/preferences", json={"category": "bogus", "title": "x", "body": "y"})
    assert r.status_code == 422


def test_lesson_crud_and_signal(client):
    r = client.post(
        "/lessons",
        json={"category": "engineering", "title": "Rebuild change_log CHECK",
              "body": "Adding an entity type rebuilds the change_log CHECK.",
              "signal": "hazard"},
    )
    assert r.status_code == 201
    assert r.json()["data"]["identifier"] == "LSN-001"
    hazards = client.get("/lessons", params={"signal": "hazard"}).json()["data"]
    assert [l["identifier"] for l in hazards] == ["LSN-001"]


def test_reference_pointer_crud_and_scope(client):
    r = client.post(
        "/reference-pointers",
        json={"kind": "server", "title": "CBM prod",
              "target": "crm.clevelandbusinessmentors.org",
              "access_note": "SSH root + ~/.ssh/id_ed25519 (path only, never the key)",
              "scope": "ENG-001"},
    )
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["identifier"] == "RFP-001"
    assert data["scope"] == "ENG-001"
    servers = client.get("/reference-pointers", params={"kind": "server"}).json()["data"]
    assert [p["identifier"] for p in servers] == ["RFP-001"]


def test_reference_pointer_rejects_bad_kind(client):
    r = client.post("/reference-pointers", json={"kind": "bogus", "title": "x", "target": "y"})
    assert r.status_code == 422
