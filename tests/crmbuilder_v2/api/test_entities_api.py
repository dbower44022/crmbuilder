"""Entities REST endpoint tests — UI v0.4 slice C.

Covers ``entity.md`` section 3.7 acceptance criteria 6 (all eight
endpoints, happy path + validation failures, v2 error envelope) and 7
(identifier auto-assignment, including under concurrent POSTs).
"""

from __future__ import annotations

import threading

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make(client, **overrides) -> dict:
    """POST an entity, returning the created record dict."""
    body = {
        "entity_name": overrides.pop("entity_name", "Contact"),
        "entity_description": overrides.pop(
            "entity_description", "A person record"
        ),
    }
    body.update(overrides)
    response = client.post("/entities", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 6 — the eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["entity_identifier"] == "ENT-001"
    assert record["entity_status"] == "candidate"
    assert record["entity_deleted_at"] is None


def test_get_list_and_single(client):
    _make(client, entity_name="Contact")
    _make(client, entity_name="Account")
    listing = client.get("/entities")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/entities/ENT-001")
    assert single.status_code == 200
    assert single.json()["data"]["entity_name"] == "Contact"


def test_get_missing_returns_404(client):
    response = client.get("/entities/ENT-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, entity_name="Old")
    response = client.put(
        "/entities/ENT-001",
        json={
            "entity_identifier": "ENT-001",
            "entity_name": "New",
            "entity_description": "nd",
            "entity_notes": "now noted",
            "entity_status": "confirmed",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["entity_name"] == "New"
    assert data["entity_status"] == "confirmed"
    assert data["entity_notes"] == "now noted"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/entities/ENT-001",
        json={
            "entity_identifier": "ENT-999",
            "entity_name": "X",
            "entity_description": "d",
            "entity_status": "candidate",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "entity_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/entities/ENT-001",
        json={"entity_description": "sharpened description"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["entity_description"] == (
        "sharpened description"
    )


def test_patch_invalid_transition_returns_422_with_error_body(client):
    _make(client)
    client.patch("/entities/ENT-001", json={"entity_status": "confirmed"})
    response = client.patch(
        "/entities/ENT-001", json={"entity_status": "candidate"}
    )
    assert response.status_code == 422
    # Dedicated body shape per entity.md section 3.5.3 — not the
    # standard {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "confirmed",
        "to": "candidate",
    }


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/entities",
        json={
            "entity_name": "Bad",
            "entity_description": "d",
            "entity_identifier": "ENT-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "entity_identifier"


def test_post_duplicate_name_returns_422(client):
    _make(client, entity_name="Contact")
    response = client.post(
        "/entities",
        json={"entity_name": "contact", "entity_description": "d"},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "entity_name"


def test_post_unknown_status_returns_422(client):
    response = client.post(
        "/entities",
        json={
            "entity_name": "X",
            "entity_description": "d",
            "entity_status": "archived",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "entity_status"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/entities/ENT-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["entity_deleted_at"] is not None
    # Hidden from the default GET, visible with ?include_deleted=true.
    assert client.get("/entities/ENT-001").status_code == 404
    shown = client.get("/entities/ENT-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/entities").json()["data"] == []
    assert (
        len(client.get("/entities?include_deleted=true").json()["data"]) == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/entities/ENT-001")
    restored = client.post("/entities/ENT-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["entity_deleted_at"] is None
    assert client.get("/entities/ENT-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/entities/ENT-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/entities/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "ENT-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/entities/next-identifier")
    assert response.json()["data"] == {"next": "ENT-002"}


def test_post_omitted_identifier_auto_assigns_and_echoes(client):
    first = _make(client, entity_name="A")
    second = _make(client, entity_name="B")
    assert first["entity_identifier"] == "ENT-001"
    assert second["entity_identifier"] == "ENT-002"


def test_concurrent_posts_get_distinct_identifiers(v2_env):
    """Eight simultaneous POSTs never share an identifier (criterion 7).

    A fresh ``TestClient`` per thread keeps each request on its own
    portal; the access layer's collision-retry guarantees uniqueness.
    """
    identifiers: list[str] = []
    failures: list[str] = []

    def worker(index: int) -> None:
        thread_client = TestClient(create_app())
        thread_client.headers.update({"X-Engagement": "ENG-001"})
        response = thread_client.post(
            "/entities",
            json={
                "entity_name": f"Concurrent {index}",
                "entity_description": "d",
            },
        )
        if response.status_code != 201:
            failures.append(response.text)
            return
        identifiers.append(response.json()["data"]["entity_identifier"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    assert len(identifiers) == 8
    assert len(set(identifiers)) == 8
