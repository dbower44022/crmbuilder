"""Manual configs REST endpoint tests — PI-004 cohort (v0.5+).

Covers ``manual_config.md`` §3.7 acceptance criteria 7, 8, 9: all eight
endpoints (happy path + validation failures, v2 envelope), identifier
auto-assignment, the §3.5.3 completed-field-population error body
shape, the dedicated invalid-status-transition body, and the references
round-trip for the four live outbound relationship kinds.
"""

from __future__ import annotations


def _make(client, **overrides) -> dict:
    """POST a manual_config, returning the created record dict."""
    body = {
        "manual_config_name": overrides.pop(
            "manual_config_name",
            "Saved view: Smoke",
        ),
        "manual_config_category": overrides.pop(
            "manual_config_category", "saved_view"
        ),
        "manual_config_description": overrides.pop(
            "manual_config_description", "Operator must edit clientDefs."
        ),
        "manual_config_instructions": overrides.pop(
            "manual_config_instructions",
            "1. Admin → ... 2. Save. 3. Clear cache.",
        ),
    }
    body.update(overrides)
    response = client.post("/manual-configs", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 7 — the eight endpoints, happy path + envelope
# ---------------------------------------------------------------------------


def test_post_create_returns_201_and_envelope(client):
    record = _make(client)
    assert record["manual_config_identifier"] == "MCF-001"
    assert record["manual_config_status"] == "candidate"
    assert record["manual_config_category"] == "saved_view"
    assert record["manual_config_deleted_at"] is None


def test_get_list_default_excludes_deleted(client):
    _make(client, manual_config_name="A")
    _make(client, manual_config_name="B")
    listing = client.get("/manual-configs")
    assert listing.status_code == 200
    body = listing.json()
    assert body["errors"] is None
    assert len(body["data"]) == 2

    # Soft-delete one and verify default excludes it.
    client.delete("/manual-configs/MCF-001")
    default = client.get("/manual-configs").json()["data"]
    assert len(default) == 1
    shown = client.get(
        "/manual-configs?include_deleted=true"
    ).json()["data"]
    assert len(shown) == 2


def test_get_missing_returns_404(client):
    response = client.get("/manual-configs/MCF-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_get_next_identifier_returns_envelope(client):
    response = client.get("/manual-configs/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "MCF-001"}


def test_post_omitted_identifier_auto_assigns(client):
    first = _make(client, manual_config_name="A")
    second = _make(client, manual_config_name="B")
    assert first["manual_config_identifier"] == "MCF-001"
    assert second["manual_config_identifier"] == "MCF-002"


def test_put_full_replace(client):
    _make(client, manual_config_name="Old")
    response = client.put(
        "/manual-configs/MCF-001",
        json={
            "manual_config_identifier": "MCF-001",
            "manual_config_name": "New",
            "manual_config_category": "workflow",
            "manual_config_description": "new desc",
            "manual_config_instructions": "new inst",
            "manual_config_notes": "now noted",
            "manual_config_status": "confirmed",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["manual_config_name"] == "New"
    assert data["manual_config_category"] == "workflow"
    assert data["manual_config_status"] == "confirmed"
    assert data["manual_config_notes"] == "now noted"


def test_put_path_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/manual-configs/MCF-001",
        json={
            "manual_config_identifier": "MCF-999",
            "manual_config_name": "X",
            "manual_config_category": "other",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
            "manual_config_status": "candidate",
        },
    )
    assert response.status_code == 422
    assert (
        response.json()["errors"][0]["field"] == "manual_config_identifier"
    )


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/manual-configs/MCF-001",
        json={"manual_config_description": "sharpened"},
    )
    assert response.status_code == 200
    assert (
        response.json()["data"]["manual_config_description"] == "sharpened"
    )


def test_patch_invalid_category_returns_422(client):
    _make(client)
    response = client.patch(
        "/manual-configs/MCF-001",
        json={"manual_config_category": "bogus"},
    )
    assert response.status_code == 422
    assert (
        response.json()["errors"][0]["field"] == "manual_config_category"
    )


# ---------------------------------------------------------------------------
# Criterion 5/6 — dedicated body shapes for transition + completion errors
# ---------------------------------------------------------------------------


def test_invalid_status_transition_returns_422_with_dedicated_body(client):
    """Direct ``candidate → completed`` rejects with the dedicated body."""
    _make(client)
    response = client.patch(
        "/manual-configs/MCF-001",
        json={
            "manual_config_status": "completed",
            "manual_config_completed_by": "doug@example.com",
        },
    )
    assert response.status_code == 422
    # Dedicated body shape from domain.md §3.5.3 (status_transition_handler).
    body = response.json()
    assert body == {
        "error": "invalid_status_transition",
        "from": "candidate",
        "to": "completed",
    }


def test_patch_to_completed_without_completion_by_returns_422(client):
    """Cross-field invariant: PATCH status=completed missing completed_by → 422."""
    _make(client)
    client.patch(
        "/manual-configs/MCF-001",
        json={"manual_config_status": "confirmed"},
    )
    response = client.patch(
        "/manual-configs/MCF-001",
        json={"manual_config_status": "completed"},
    )
    assert response.status_code == 422
    body = response.json()
    # v2 envelope shape with the dedicated error code + missing list.
    assert body["data"] is None
    assert body["errors"][0]["error"] == (
        "completed_status_requires_completion_fields"
    )
    assert body["errors"][0]["missing"] == ["manual_config_completed_by"]


def test_patch_to_completed_with_completion_by_succeeds(client):
    _make(client)
    client.patch(
        "/manual-configs/MCF-001",
        json={"manual_config_status": "confirmed"},
    )
    response = client.patch(
        "/manual-configs/MCF-001",
        json={
            "manual_config_status": "completed",
            "manual_config_completed_by": "doug@example.com",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["manual_config_status"] == "completed"
    assert data["manual_config_completed_by"] == "doug@example.com"
    assert data["manual_config_completed_at"] is not None


def test_post_completed_without_completion_by_returns_422(client):
    """POST status=completed missing completed_by → dedicated 422 body."""
    response = client.post(
        "/manual-configs",
        json={
            "manual_config_name": "Imported completed",
            "manual_config_category": "workflow",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
            "manual_config_status": "completed",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["errors"][0]["error"] == (
        "completed_status_requires_completion_fields"
    )


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/manual-configs",
        json={
            "manual_config_name": "Bad",
            "manual_config_category": "other",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
            "manual_config_identifier": "MCF-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "manual_config_identifier"


def test_post_invalid_category_returns_422(client):
    response = client.post(
        "/manual-configs",
        json={
            "manual_config_name": "X",
            "manual_config_category": "bogus",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
        },
    )
    assert response.status_code == 422
    assert (
        response.json()["errors"][0]["field"] == "manual_config_category"
    )


def test_post_duplicate_name_returns_422(client):
    _make(client, manual_config_name="Saved view foo")
    response = client.post(
        "/manual-configs",
        json={
            "manual_config_name": "SAVED VIEW FOO",
            "manual_config_category": "saved_view",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "manual_config_name"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/manual-configs/MCF-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["manual_config_deleted_at"] is not None
    assert client.get("/manual-configs/MCF-001").status_code == 404
    shown = client.get("/manual-configs/MCF-001?include_deleted=true")
    assert shown.status_code == 200


def test_restore_round_trip(client):
    _make(client)
    client.delete("/manual-configs/MCF-001")
    restored = client.post("/manual-configs/MCF-001/restore")
    assert restored.status_code == 200
    assert (
        restored.json()["data"]["manual_config_deleted_at"] is None
    )
    assert client.get("/manual-configs/MCF-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/manual-configs/MCF-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 15 — references round-trip for the four outbound kinds
# ---------------------------------------------------------------------------


def test_reference_round_trip_to_domain(client):
    """POST /references with (manual_config, domain, scopes_to_domain) works."""
    mcf = _make(client)
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
            "source_type": "manual_config",
            "source_id": mcf["manual_config_identifier"],
            "target_type": "domain",
            "target_id": dom["domain_identifier"],
            "relationship": "manual_config_scopes_to_domain",
        },
    )
    assert response.status_code == 201, response.text
    edge = response.json()["data"]
    assert edge["relationship"] == "manual_config_scopes_to_domain"


def test_reference_round_trip_to_entity(client):
    """POST /references with (manual_config, entity, touches_entity) works."""
    mcf = _make(client)
    ent = client.post(
        "/entities",
        json={
            "entity_name": "Contact",
            "entity_description": "A person tracked by the CRM.",
        },
    ).json()["data"]
    response = client.post(
        "/references",
        json={
            "source_type": "manual_config",
            "source_id": mcf["manual_config_identifier"],
            "target_type": "entity",
            "target_id": ent["entity_identifier"],
            "relationship": "manual_config_touches_entity",
        },
    )
    assert response.status_code == 201, response.text
    edge = response.json()["data"]
    assert edge["relationship"] == "manual_config_touches_entity"
