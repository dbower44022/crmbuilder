"""Decisions endpoints."""

from __future__ import annotations


def _create(client, identifier="DEC-001", **overrides):
    body = {
        "identifier": identifier,
        "title": f"{identifier} title",
        "decision_date": "05-07-26",
        "status": "Active",
    }
    body.update(overrides)
    return client.post("/decisions", json=body)


def test_create_then_get(client):
    r = _create(client)
    assert r.status_code == 201
    assert r.json()["data"]["identifier"] == "DEC-001"

    r = client.get("/decisions/DEC-001")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Active"


def test_create_invalid_status(client):
    r = _create(client, status="bogus")
    assert r.status_code == 400
    assert r.json()["errors"][0]["field"] == "status"


def test_create_unknown_field_rejected(client):
    body = {
        "identifier": "DEC-001",
        "title": "x",
        "decision_date": "05-07-26",
        "status": "Active",
        "extra_field": "nope",
    }
    r = client.post("/decisions", json=body)
    # Pydantic extra='forbid' produces a 422
    assert r.status_code == 422


def test_get_missing(client):
    r = client.get("/decisions/DEC-NONE")
    assert r.status_code == 404
    assert r.json()["errors"][0]["code"] == "not_found"


def test_duplicate_returns_409(client):
    _create(client, identifier="DEC-001")
    r = _create(client, identifier="DEC-001")
    assert r.status_code == 409


def test_patch_status(client):
    _create(client, identifier="DEC-001")
    r = client.patch("/decisions/DEC-001", json={"status": "Superseded"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Superseded"


def test_supersedes_chain_via_api(client):
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002", supersedes="DEC-001")
    client.patch("/decisions/DEC-001", json={"superseded_by": "DEC-002"})
    r = client.get("/decisions/DEC-001")
    assert r.json()["data"]["superseded_by_identifier"] == "DEC-002"
    r = client.get("/decisions/DEC-002")
    assert r.json()["data"]["supersedes_identifier"] == "DEC-001"


def test_list(client):
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002")
    r = client.get("/decisions")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 2


def test_delete_is_soft(client):
    """DELETE soft-deletes the row; GET still returns it with status='Deleted'."""
    _create(client, identifier="DEC-099")
    r = client.delete("/decisions/DEC-099")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Deleted"
    r = client.get("/decisions/DEC-099")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Deleted"


def test_list_excludes_deleted(client):
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002")
    client.delete("/decisions/DEC-002")
    r = client.get("/decisions")
    assert r.status_code == 200
    identifiers = {row["identifier"] for row in r.json()["data"]}
    assert identifiers == {"DEC-001"}


def test_patch_supersedes_empty_string_clears_link(client):
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002", supersedes="DEC-001")
    r = client.patch("/decisions/DEC-002", json={"supersedes": ""})
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["supersedes_identifier"] is None
    r = client.get("/decisions/DEC-002")
    assert r.json()["data"]["supersedes_identifier"] is None
