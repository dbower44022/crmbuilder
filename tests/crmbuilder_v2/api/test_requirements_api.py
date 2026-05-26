"""Requirements REST endpoint tests — PI-004 cohort (v0.5+).

Covers ``requirement.md`` §3.7 acceptance criteria 6, 7, 8: all eight
endpoints (happy path + validation failures, v2 error envelope),
identifier auto-assignment, and the references round-trip for the
five outbound relationship kinds.
"""

from __future__ import annotations

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make(client, **overrides) -> dict:
    """POST a requirement, returning the created record dict."""
    body = {
        "requirement_name": overrides.pop(
            "requirement_name", "Capture mentor availability slots"
        ),
        "requirement_description": overrides.pop(
            "requirement_description",
            "When a mentor registers, capture their weekly windows.",
        ),
        "requirement_acceptance_summary": overrides.pop(
            "requirement_acceptance_summary",
            (
                "A mentor record carries at least one availability "
                "window after registration."
            ),
        ),
    }
    body.update(overrides)
    response = client.post("/requirements", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 7 — the eight endpoints, happy path + envelope
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["requirement_identifier"] == "REQ-001"
    assert record["requirement_priority"] == "should"
    assert record["requirement_status"] == "candidate"
    assert record["requirement_deleted_at"] is None


def test_post_with_explicit_priority_persists(client):
    record = _make(client, requirement_priority="must")
    assert record["requirement_priority"] == "must"


def test_get_list_and_single(client):
    _make(client, requirement_name="A capability")
    _make(client, requirement_name="B capability")
    listing = client.get("/requirements")
    assert listing.status_code == 200
    body = listing.json()
    assert body["errors"] is None
    assert len(body["data"]) == 2
    single = client.get("/requirements/REQ-001")
    assert single.status_code == 200
    assert single.json()["data"]["requirement_name"] == "A capability"


def test_get_missing_returns_404(client):
    response = client.get("/requirements/REQ-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, requirement_name="Old")
    response = client.put(
        "/requirements/REQ-001",
        json={
            "requirement_identifier": "REQ-001",
            "requirement_name": "New",
            "requirement_description": "nd",
            "requirement_acceptance_summary": "na",
            "requirement_priority": "must",
            "requirement_notes": "now noted",
            "requirement_status": "confirmed",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["requirement_name"] == "New"
    assert data["requirement_status"] == "confirmed"
    assert data["requirement_notes"] == "now noted"
    assert data["requirement_priority"] == "must"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/requirements/REQ-001",
        json={
            "requirement_identifier": "REQ-999",
            "requirement_name": "X",
            "requirement_description": "d",
            "requirement_acceptance_summary": "a",
            "requirement_priority": "should",
            "requirement_status": "candidate",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "requirement_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/requirements/REQ-001",
        json={"requirement_description": "sharpened description"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["requirement_description"] == (
        "sharpened description"
    )


def test_patch_invalid_priority_returns_422(client):
    _make(client)
    response = client.patch(
        "/requirements/REQ-001",
        json={"requirement_priority": "maybe"},
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "requirement_priority"


def test_patch_invalid_transition_returns_422_with_error_body(client):
    _make(client)
    client.patch(
        "/requirements/REQ-001", json={"requirement_status": "confirmed"}
    )
    response = client.patch(
        "/requirements/REQ-001", json={"requirement_status": "candidate"}
    )
    assert response.status_code == 422
    # Dedicated body shape per requirement.md §3.5.3 — not the standard
    # {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "confirmed",
        "to": "candidate",
    }


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/requirements",
        json={
            "requirement_name": "Bad",
            "requirement_description": "d",
            "requirement_acceptance_summary": "a",
            "requirement_identifier": "REQ-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "requirement_identifier"


def test_post_invalid_priority_returns_422(client):
    response = client.post(
        "/requirements",
        json={
            "requirement_name": "X",
            "requirement_description": "d",
            "requirement_acceptance_summary": "a",
            "requirement_priority": "maybe",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "requirement_priority"


def test_post_duplicate_name_returns_422(client):
    _make(client, requirement_name="Capture mentor slots")
    response = client.post(
        "/requirements",
        json={
            "requirement_name": "CAPTURE mentor SLOTS",
            "requirement_description": "d",
            "requirement_acceptance_summary": "a",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "requirement_name"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/requirements/REQ-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["requirement_deleted_at"] is not None
    assert client.get("/requirements/REQ-001").status_code == 404
    shown = client.get("/requirements/REQ-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/requirements").json()["data"] == []
    assert (
        len(
            client.get("/requirements?include_deleted=true").json()["data"]
        )
        == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/requirements/REQ-001")
    restored = client.post("/requirements/REQ-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["requirement_deleted_at"] is None
    assert client.get("/requirements/REQ-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/requirements/REQ-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 8 — identifier auto-assignment
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/requirements/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "REQ-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/requirements/next-identifier")
    assert response.json()["data"] == {"next": "REQ-002"}


def test_post_omitted_identifier_auto_assigns_and_echoes(client):
    first = _make(client, requirement_name="A")
    second = _make(client, requirement_name="B")
    assert first["requirement_identifier"] == "REQ-001"
    assert second["requirement_identifier"] == "REQ-002"


# ---------------------------------------------------------------------------
# Criterion 14 — references round-trip for the four live outbound kinds
# ---------------------------------------------------------------------------


def test_reference_to_live_domain_target_accepted(client):
    """POST /references with (requirement, domain, scopes_to_domain) works."""
    req = _make(client)
    dom = client.post(
        "/domains",
        json={
            "domain_name": "Mentoring",
            "domain_purpose": "Mentor recruitment + onboarding.",
            "domain_description": "Mentor recruitment + onboarding.",
        },
    ).json()["data"]
    response = client.post(
        "/references",
        json={
            "source_type": "requirement",
            "source_id": req["requirement_identifier"],
            "target_type": "domain",
            "target_id": dom["domain_identifier"],
            "relationship": "requirement_scopes_to_domain",
        },
    )
    assert response.status_code == 201, response.text
    edge = response.json()["data"]
    assert edge["relationship"] == "requirement_scopes_to_domain"
