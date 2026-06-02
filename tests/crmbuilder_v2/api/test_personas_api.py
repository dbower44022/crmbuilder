"""Personas REST endpoint tests — v0.5+ (PI-003).

Covers ``persona.md`` §3.7 acceptance criteria 6, 7 plus criterion 13
(vocab + ``_kinds_for_pair`` integration end-to-end through the
references POST surface).
"""

from __future__ import annotations

import threading

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make(client, **overrides) -> dict:
    """POST a persona, returning the created record dict."""
    body = {
        "persona_name": overrides.pop(
            "persona_name", "Mentor Coordinator"
        ),
        "persona_role_summary": overrides.pop(
            "persona_role_summary",
            "Oversees the mentor program day-to-day",
        ),
    }
    body.update(overrides)
    response = client.post("/personas", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _make_domain(client, **overrides) -> dict:
    body = {
        "domain_name": overrides.pop("domain_name", "Mentor Recruitment"),
        "domain_purpose": overrides.pop("domain_purpose", "Why it exists"),
        "domain_description": overrides.pop(
            "domain_description", "What it covers"
        ),
    }
    response = client.post("/domains", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _make_entity(client, **overrides) -> dict:
    body = {
        "entity_name": overrides.pop("entity_name", "Mentor"),
        "entity_description": overrides.pop(
            "entity_description", "What kind of thing it is"
        ),
    }
    response = client.post("/entities", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 6 — the eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["persona_identifier"] == "PER-001"
    assert record["persona_status"] == "candidate"
    assert record["persona_deleted_at"] is None


def test_get_list_and_single(client):
    _make(client, persona_name="Mentor Coordinator")
    _make(client, persona_name="Program Manager")
    listing = client.get("/personas")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/personas/PER-001")
    assert single.status_code == 200
    assert single.json()["data"]["persona_name"] == "Mentor Coordinator"


def test_get_missing_returns_404(client):
    response = client.get("/personas/PER-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, persona_name="Old")
    response = client.put(
        "/personas/PER-001",
        json={
            "persona_identifier": "PER-001",
            "persona_name": "New",
            "persona_role_summary": "new summary",
            "persona_responsibilities": "now has responsibilities",
            "persona_notes": "now noted",
            "persona_status": "confirmed",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["persona_name"] == "New"
    assert data["persona_status"] == "confirmed"
    assert data["persona_notes"] == "now noted"
    assert data["persona_responsibilities"] == "now has responsibilities"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/personas/PER-001",
        json={
            "persona_identifier": "PER-999",
            "persona_name": "X",
            "persona_role_summary": "r",
            "persona_status": "candidate",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "persona_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/personas/PER-001",
        json={"persona_role_summary": "sharpened summary"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["persona_role_summary"] == (
        "sharpened summary"
    )


def test_patch_explicit_null_clears_responsibilities(client):
    """PATCH with explicit ``persona_responsibilities: null`` clears it."""
    _make(client, persona_responsibilities="initial")
    # The field round-trips through the PATCH and returns null after.
    response = client.patch(
        "/personas/PER-001",
        json={"persona_responsibilities": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["persona_responsibilities"] is None


def test_patch_invalid_transition_returns_422_with_error_body(client):
    _make(client)
    client.patch("/personas/PER-001", json={"persona_status": "confirmed"})
    response = client.patch(
        "/personas/PER-001", json={"persona_status": "candidate"}
    )
    assert response.status_code == 422
    # Dedicated body shape per persona.md §3.5.3 — not the standard
    # {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "confirmed",
        "to": "candidate",
    }


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/personas",
        json={
            "persona_name": "Bad",
            "persona_role_summary": "r",
            "persona_identifier": "PER-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "persona_identifier"


def test_post_collision_returns_409(client):
    """Explicit-identifier POST that collides with an existing row → 409."""
    _make(client, persona_identifier="PER-001")
    response = client.post(
        "/personas",
        json={
            "persona_name": "Second",
            "persona_role_summary": "r",
            "persona_identifier": "PER-001",
        },
    )
    assert response.status_code == 409


def test_post_duplicate_name_returns_422(client):
    _make(client, persona_name="Mentor Coordinator")
    response = client.post(
        "/personas",
        json={
            "persona_name": "mentor coordinator",
            "persona_role_summary": "r",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "persona_name"


def test_post_unknown_status_returns_422(client):
    response = client.post(
        "/personas",
        json={
            "persona_name": "X",
            "persona_role_summary": "r",
            "persona_status": "archived",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "persona_status"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/personas/PER-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["persona_deleted_at"] is not None
    assert client.get("/personas/PER-001").status_code == 404
    shown = client.get("/personas/PER-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/personas").json()["data"] == []
    assert (
        len(client.get("/personas?include_deleted=true").json()["data"]) == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/personas/PER-001")
    restored = client.post("/personas/PER-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["persona_deleted_at"] is None
    assert client.get("/personas/PER-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/personas/PER-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment, including under concurrency
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/personas/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "PER-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/personas/next-identifier")
    assert response.json()["data"] == {"next": "PER-002"}


def test_post_omitted_identifier_auto_assigns_and_echoes(client):
    first = _make(client, persona_name="A")
    second = _make(client, persona_name="B")
    assert first["persona_identifier"] == "PER-001"
    assert second["persona_identifier"] == "PER-002"


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
            "/personas",
            json={
                "persona_name": f"Concurrent {index}",
                "persona_role_summary": "r",
            },
        )
        if response.status_code != 201:
            failures.append(response.text)
            return
        identifiers.append(response.json()["data"]["persona_identifier"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    assert len(identifiers) == 8
    assert len(set(identifiers)) == 8


# ---------------------------------------------------------------------------
# Criterion 13 — vocab + _kinds_for_pair integration through /references
# ---------------------------------------------------------------------------


def test_post_reference_persona_scopes_to_domain_succeeds(client):
    _make(client)
    _make_domain(client)
    response = client.post(
        "/references",
        json={
            "source_type": "persona",
            "source_id": "PER-001",
            "target_type": "domain",
            "target_id": "DOM-001",
            "relationship": "persona_scopes_to_domain",
        },
    )
    assert response.status_code == 201, response.text


def test_post_reference_persona_realized_as_entity_succeeds(client):
    _make(client)
    _make_entity(client)
    response = client.post(
        "/references",
        json={
            "source_type": "persona",
            "source_id": "PER-001",
            "target_type": "entity",
            "target_id": "ENT-001",
            "relationship": "persona_realized_as_entity",
        },
    )
    assert response.status_code == 201, response.text


def test_post_reference_persona_to_domain_made_up_kind_rejected(client):
    """A made-up relationship kind fails vocab validation at the access layer.

    The access layer's ``require_in`` check rejects the unknown
    relationship kind with HTTP 4xx (the existing API surface returns
    400 for this case via the generic ``FieldError`` handler).
    """
    _make(client)
    _make_domain(client)
    response = client.post(
        "/references",
        json={
            "source_type": "persona",
            "source_id": "PER-001",
            "target_type": "domain",
            "target_id": "DOM-001",
            "relationship": "totally_made_up_kind",
        },
    )
    assert response.status_code in (400, 422)
    # And the response body surfaces the rejection at the
    # ``relationship`` field.
    body = response.json()
    assert body["data"] is None
    assert any(
        err.get("field") == "relationship" for err in body["errors"]
    ), body
