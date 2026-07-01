"""Decisions endpoints."""

from __future__ import annotations

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def _create(client, identifier="DEC-001", **overrides):
    body = {
        "identifier": identifier,
        "title": f"{identifier} title",
        "decision_date": "05-07-26",
        "status": "Active",
        "executive_summary": _VALID_EXEC_SUMMARY,
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
        "executive_summary": _VALID_EXEC_SUMMARY,
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


def test_list_includes_deleted_with_query_param(client):
    """GET /decisions?include_deleted=true returns soft-deleted rows."""
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002")
    client.delete("/decisions/DEC-002")
    r = client.get("/decisions?include_deleted=true")
    assert r.status_code == 200
    identifiers = {row["identifier"] for row in r.json()["data"]}
    assert identifiers == {"DEC-001", "DEC-002"}


def test_patch_status_back_to_active_restores(client):
    """PATCH status=Active on a soft-deleted decision restores it (slice F restore path)."""
    _create(client, identifier="DEC-001")
    client.delete("/decisions/DEC-001")
    r = client.patch("/decisions/DEC-001", json={"status": "Active"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "Active"
    r = client.get("/decisions")
    identifiers = {row["identifier"] for row in r.json()["data"]}
    assert "DEC-001" in identifiers


def test_patch_supersedes_empty_string_clears_link(client):
    _create(client, identifier="DEC-001")
    _create(client, identifier="DEC-002", supersedes="DEC-001")
    r = client.patch("/decisions/DEC-002", json={"supersedes": ""})
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["supersedes_identifier"] is None
    r = client.get("/decisions/DEC-002")
    assert r.json()["data"]["supersedes_identifier"] is None


# PI-002 — POST without identifier returns 201 with server-assigned value.


def test_post_without_identifier_assigns_one(client):
    r = client.post(
        "/decisions",
        json={"title": "Auto", "decision_date": "05-25-26", "status": "Active",
              "executive_summary": _VALID_EXEC_SUMMARY},
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["identifier"] == "DEC-001"


def test_post_with_invalid_identifier_format_returns_422(client):
    r = client.post(
        "/decisions",
        json={
            "identifier": "DEC-1",
            "title": "Bad",
            "decision_date": "05-25-26",
            "status": "Active",
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    assert r.status_code == 422, r.json()


# -- REQ-396 / PI-103: optimistic lost-update guard (HTTP layer) -------------


def test_patch_with_stale_precondition_is_409(client):
    _create(client, identifier="DEC-050")
    token = client.get("/decisions/DEC-050").json()["data"]["updated_at"]

    # A concurrent edit advances updated_at.
    r1 = client.patch("/decisions/DEC-050", json={"title": "edit-1"})
    assert r1.status_code == 200

    # A second edit using the pre-edit token is refused (409), not silently applied.
    r2 = client.patch(
        "/decisions/DEC-050",
        json={"title": "edit-2", "expected_updated_at": token},
    )
    assert r2.status_code == 409, r2.json()
    assert "stale_write" in str(r2.json()["errors"])

    # edit-1 survived; edit-2 never landed.
    assert client.get("/decisions/DEC-050").json()["data"]["title"] == "edit-1"


def test_patch_with_fresh_precondition_succeeds(client):
    _create(client, identifier="DEC-051")
    token = client.get("/decisions/DEC-051").json()["data"]["updated_at"]
    r = client.patch(
        "/decisions/DEC-051",
        json={"title": "guarded-ok", "expected_updated_at": token},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["title"] == "guarded-ok"


def test_patch_without_precondition_still_works(client):
    _create(client, identifier="DEC-052")
    r = client.patch("/decisions/DEC-052", json={"title": "unguarded"})
    assert r.status_code == 200
    assert r.json()["data"]["title"] == "unguarded"
