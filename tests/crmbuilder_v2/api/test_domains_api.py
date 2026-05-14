"""Domains REST endpoint tests — UI v0.4 slice B.

Covers ``domain.md`` section 3.7 acceptance criteria 6 (all eight
endpoints, happy path + validation failures, v2 error envelope) and 7
(identifier auto-assignment, including under concurrent POSTs).
"""

from __future__ import annotations

import threading

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make(client, **overrides) -> dict:
    """POST a domain, returning the created record dict."""
    body = {
        "domain_name": overrides.pop("domain_name", "Mentoring"),
        "domain_purpose": overrides.pop("domain_purpose", "Why it exists"),
        "domain_description": overrides.pop(
            "domain_description", "What it covers"
        ),
    }
    body.update(overrides)
    response = client.post("/domains", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 6 — the eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["domain_identifier"] == "DOM-001"
    assert record["domain_status"] == "candidate"
    assert record["domain_deleted_at"] is None


def test_get_list_and_single(client):
    _make(client, domain_name="Mentoring")
    _make(client, domain_name="Fundraising")
    listing = client.get("/domains")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/domains/DOM-001")
    assert single.status_code == 200
    assert single.json()["data"]["domain_name"] == "Mentoring"


def test_get_missing_returns_404(client):
    response = client.get("/domains/DOM-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, domain_name="Old")
    response = client.put(
        "/domains/DOM-001",
        json={
            "domain_identifier": "DOM-001",
            "domain_name": "New",
            "domain_purpose": "np",
            "domain_description": "nd",
            "domain_notes": "now noted",
            "domain_status": "confirmed",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["domain_name"] == "New"
    assert data["domain_status"] == "confirmed"
    assert data["domain_notes"] == "now noted"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/domains/DOM-001",
        json={
            "domain_identifier": "DOM-999",
            "domain_name": "X",
            "domain_purpose": "p",
            "domain_description": "d",
            "domain_status": "candidate",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "domain_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/domains/DOM-001", json={"domain_purpose": "sharpened purpose"}
    )
    assert response.status_code == 200
    assert response.json()["data"]["domain_purpose"] == "sharpened purpose"


def test_patch_invalid_transition_returns_422_with_error_body(client):
    _make(client)
    client.patch("/domains/DOM-001", json={"domain_status": "confirmed"})
    response = client.patch(
        "/domains/DOM-001", json={"domain_status": "candidate"}
    )
    assert response.status_code == 422
    # Dedicated body shape per domain.md section 3.5.3 — not the
    # standard {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "confirmed",
        "to": "candidate",
    }


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/domains",
        json={
            "domain_name": "Bad",
            "domain_purpose": "p",
            "domain_description": "d",
            "domain_identifier": "DOM-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "domain_identifier"


def test_post_duplicate_name_returns_422(client):
    _make(client, domain_name="Mentoring")
    response = client.post(
        "/domains",
        json={
            "domain_name": "mentoring",
            "domain_purpose": "p",
            "domain_description": "d",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "domain_name"


def test_post_unknown_status_returns_422(client):
    response = client.post(
        "/domains",
        json={
            "domain_name": "X",
            "domain_purpose": "p",
            "domain_description": "d",
            "domain_status": "archived",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "domain_status"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/domains/DOM-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["domain_deleted_at"] is not None
    # Hidden from the default GET, visible with ?include_deleted=true.
    assert client.get("/domains/DOM-001").status_code == 404
    shown = client.get("/domains/DOM-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/domains").json()["data"] == []
    assert (
        len(client.get("/domains?include_deleted=true").json()["data"]) == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/domains/DOM-001")
    restored = client.post("/domains/DOM-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["domain_deleted_at"] is None
    assert client.get("/domains/DOM-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/domains/DOM-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/domains/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "DOM-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/domains/next-identifier")
    assert response.json()["data"] == {"next": "DOM-002"}


def test_post_omitted_identifier_auto_assigns_and_echoes(client):
    first = _make(client, domain_name="A")
    second = _make(client, domain_name="B")
    assert first["domain_identifier"] == "DOM-001"
    assert second["domain_identifier"] == "DOM-002"


def test_concurrent_posts_get_distinct_identifiers(v2_env):
    """Eight simultaneous POSTs never share an identifier (criterion 7).

    A fresh ``TestClient`` per thread keeps each request on its own
    portal; the access layer's collision-retry guarantees uniqueness.
    """
    identifiers: list[str] = []
    failures: list[str] = []

    def worker(index: int) -> None:
        thread_client = TestClient(create_app())
        response = thread_client.post(
            "/domains",
            json={
                "domain_name": f"Concurrent {index}",
                "domain_purpose": "p",
                "domain_description": "d",
            },
        )
        if response.status_code != 201:
            failures.append(response.text)
            return
        identifiers.append(response.json()["data"]["domain_identifier"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    assert len(identifiers) == 8
    assert len(set(identifiers)) == 8
