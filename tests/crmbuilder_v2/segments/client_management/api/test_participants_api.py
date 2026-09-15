"""Participants REST endpoint tests — REL-040 / PI-094 (REQ-412).

Covers the eight ``/participants`` endpoints happy-path plus the
``persona_backed_by_participant`` vocab + ``_kinds_for_pair`` integration
end-to-end through the ``/references`` POST surface.
"""

from __future__ import annotations


def _make(client, **overrides) -> dict:
    """POST a participant, returning the created record dict."""
    body = {
        "participant_name": overrides.pop("participant_name", "Jane Doe"),
        "participant_role_kind": overrides.pop(
            "participant_role_kind", "Client SME"
        ),
    }
    body.update(overrides)
    response = client.post("/participants", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _make_persona(client, **overrides) -> dict:
    body = {
        "persona_name": overrides.pop("persona_name", "Volunteer Mentor"),
        "persona_role_summary": overrides.pop(
            "persona_role_summary", "Mentors program participants"
        ),
    }
    response = client.post("/personas", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# The eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["participant_identifier"] == "PTC-001"
    assert record["participant_status"] == "active"
    assert record["participant_deleted_at"] is None


def test_next_identifier(client):
    _make(client)
    response = client.get("/participants/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"]["next"] == "PTC-002"


def test_get_list_and_single(client):
    _make(client, participant_name="Jane Doe")
    _make(client, participant_name="Client Admin", participant_role_kind="Client Administrator")
    listing = client.get("/participants")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/participants/PTC-001")
    assert single.status_code == 200
    assert single.json()["data"]["participant_name"] == "Jane Doe"


def test_get_missing_returns_404(client):
    response = client.get("/participants/PTC-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, participant_name="Old")
    response = client.put(
        "/participants/PTC-001",
        json={
            "participant_identifier": "PTC-001",
            "participant_name": "New",
            "participant_role_kind": "Technical Administrator",
            "participant_affiliation": "Acme",
            "participant_contact": "new@acme.example",
            "participant_notes": "now noted",
            "participant_status": "inactive",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["participant_name"] == "New"
    assert data["participant_role_kind"] == "Technical Administrator"
    assert data["participant_status"] == "inactive"
    assert data["participant_affiliation"] == "Acme"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/participants/PTC-001",
        json={
            "participant_identifier": "PTC-999",
            "participant_name": "X",
            "participant_role_kind": "Client SME",
            "participant_status": "active",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "participant_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/participants/PTC-001",
        json={"participant_role_kind": "Methodology Author"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["participant_role_kind"] == (
        "Methodology Author"
    )


def test_patch_explicit_null_clears_affiliation(client):
    _make(client, participant_affiliation="initial")
    response = client.patch(
        "/participants/PTC-001",
        json={"participant_affiliation": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["participant_affiliation"] is None


def test_delete_and_restore(client):
    _make(client)
    deleted = client.delete("/participants/PTC-001")
    assert deleted.status_code == 200
    # Soft-deleted → 404 by default, visible with include_deleted.
    assert client.get("/participants/PTC-001").status_code == 404
    with_deleted = client.get("/participants/PTC-001?include_deleted=true")
    assert with_deleted.status_code == 200
    restored = client.post("/participants/PTC-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["participant_deleted_at"] is None


def test_invalid_status_returns_422(client):
    response = client.post(
        "/participants",
        json={
            "participant_name": "A",
            "participant_role_kind": "Client SME",
            "participant_status": "archived",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# persona_backed_by_participant integration through /references
# ---------------------------------------------------------------------------


def test_post_reference_persona_backed_by_participant_succeeds(client):
    _make_persona(client)
    _make(client)
    response = client.post(
        "/references",
        json={
            "source_type": "persona",
            "source_id": "PER-001",
            "target_type": "participant",
            "target_id": "PTC-001",
            "relationship": "persona_backed_by_participant",
        },
    )
    assert response.status_code == 201, response.text


def test_post_reference_made_up_kind_rejected(client):
    """An unknown relationship kind fails vocab validation (4xx)."""
    _make_persona(client)
    _make(client)
    response = client.post(
        "/references",
        json={
            "source_type": "persona",
            "source_id": "PER-001",
            "target_type": "participant",
            "target_id": "PTC-001",
            "relationship": "totally_made_up_kind",
        },
    )
    assert response.status_code >= 400
