"""Test specs REST endpoint tests — PI-004 cohort closer (v0.5+).

Covers ``test_spec.md`` §3.7 acceptance criteria 7, 8, 9: nine endpoints
(the eight standard ones plus the ``/record-run`` convenience), the v2
envelope, dual-axis transition validation including the dedicated
invalid-status-transition body and the §3.4.4 cross-field invariant on
``last_run_at``, identifier auto-assignment, and the references round-
trip for the three live outbound relationship kinds.
"""

from __future__ import annotations


def _make(client, **overrides) -> dict:
    """POST a test_spec, returning the created record dict."""
    body = {
        "test_spec_name": overrides.pop(
            "test_spec_name",
            "Mentor application confirmation email",
        ),
        "test_spec_description": overrides.pop(
            "test_spec_description",
            "Verifies the mentor-application happy path.",
        ),
        "test_spec_steps": overrides.pop(
            "test_spec_steps",
            "1. Open form. 2. Fill required fields. 3. Submit.",
        ),
        "test_spec_expected": overrides.pop(
            "test_spec_expected",
            "Confirmation email arrives within 2 minutes.",
        ),
    }
    body.update(overrides)
    response = client.post("/test-specs", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 7 / 8 — happy path + envelope
# ---------------------------------------------------------------------------


def test_post_minimum_returns_201_with_envelope(client):
    response = client.post(
        "/test-specs",
        json={
            "test_spec_name": "Smoke",
            "test_spec_description": "Smoke desc",
            "test_spec_steps": "Do",
            "test_spec_expected": "Works",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["errors"] is None
    assert body["data"]["test_spec_identifier"] == "TST-001"
    assert body["data"]["test_spec_status"] == "candidate"
    assert body["data"]["test_spec_last_run_outcome"] == "not_run"
    assert body["data"]["test_spec_last_run_at"] is None


def test_get_list_default_excludes_deleted(client):
    _make(client, test_spec_name="A")
    _make(client, test_spec_name="B")
    listing = client.get("/test-specs")
    assert listing.status_code == 200
    body = listing.json()
    assert body["errors"] is None
    assert len(body["data"]) == 2

    client.delete("/test-specs/TST-001")
    listing = client.get("/test-specs")
    assert len(listing.json()["data"]) == 1

    listing_all = client.get("/test-specs?include_deleted=true")
    assert len(listing_all.json()["data"]) == 2


def test_get_single_404_on_missing(client):
    response = client.get("/test-specs/TST-404")
    assert response.status_code == 404


def test_put_replace_round_trip(client):
    _make(client)
    response = client.put(
        "/test-specs/TST-001",
        json={
            "test_spec_identifier": "TST-001",
            "test_spec_name": "Renamed",
            "test_spec_description": "Updated desc.",
            "test_spec_steps": "1. Step. 2. Step.",
            "test_spec_expected": "Pass.",
            "test_spec_status": "candidate",
            "test_spec_last_run_outcome": "not_run",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["test_spec_name"] == "Renamed"


# ---------------------------------------------------------------------------
# Criterion 4 — methodology status transition
# ---------------------------------------------------------------------------


def test_patch_invalid_status_transition_returns_422(client):
    """confirmed → candidate yields the dedicated body shape."""
    _make(client)
    # Advance to confirmed first.
    client.patch(
        "/test-specs/TST-001",
        json={"test_spec_status": "confirmed"},
    )
    response = client.patch(
        "/test-specs/TST-001",
        json={"test_spec_status": "candidate"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_status_transition"
    assert body["from"] == "confirmed"
    assert body["to"] == "candidate"


# ---------------------------------------------------------------------------
# Criterion 6 — §3.4.4 cross-field invariant via REST
# ---------------------------------------------------------------------------


def test_patch_outcome_to_passing_auto_sets_last_run_at(client):
    """Server defaults last_run_at to now() when outcome moves to a run state."""
    _make(client)
    response = client.patch(
        "/test-specs/TST-001",
        json={"test_spec_last_run_outcome": "passing"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["test_spec_last_run_outcome"] == "passing"
    assert body["test_spec_last_run_at"] is not None


def test_patch_outcome_to_not_run_clears_fields(client):
    """Server clears last_run_at AND last_run_notes on transition to not_run."""
    _make(client)
    client.patch(
        "/test-specs/TST-001",
        json={
            "test_spec_last_run_outcome": "passing",
            "test_spec_last_run_notes": "ok",
        },
    )
    response = client.patch(
        "/test-specs/TST-001",
        json={"test_spec_last_run_outcome": "not_run"},
    )
    assert response.status_code == 200
    body = response.json()["data"]
    assert body["test_spec_last_run_outcome"] == "not_run"
    assert body["test_spec_last_run_at"] is None
    assert body["test_spec_last_run_notes"] is None


def test_patch_outcome_run_state_with_explicit_null_at_rejected(client):
    """PATCH outcome=passing + explicit last_run_at=null → 422."""
    _make(client)
    response = client.patch(
        "/test-specs/TST-001",
        json={
            "test_spec_last_run_outcome": "passing",
            "test_spec_last_run_at": None,
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /record-run convenience endpoint (§3.8.1)
# ---------------------------------------------------------------------------


def test_record_run_endpoint_round_trip(client):
    _make(client)
    response = client.post(
        "/test-specs/TST-001/record-run",
        json={"outcome": "passing", "notes": "ok"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["errors"] is None
    data = body["data"]
    assert data["test_spec_last_run_outcome"] == "passing"
    assert data["test_spec_last_run_notes"] == "ok"
    assert data["test_spec_last_run_at"] is not None


def test_record_run_reset_clears_notes(client):
    _make(client)
    client.post(
        "/test-specs/TST-001/record-run",
        json={"outcome": "failing", "notes": "step 4 timed out"},
    )
    response = client.post(
        "/test-specs/TST-001/record-run",
        json={"outcome": "not_run", "notes": "ignored on reset"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["test_spec_last_run_outcome"] == "not_run"
    assert data["test_spec_last_run_at"] is None
    assert data["test_spec_last_run_notes"] is None


# ---------------------------------------------------------------------------
# Criterion 9 — next-identifier helper
# ---------------------------------------------------------------------------


def test_next_identifier_endpoint(client):
    response = client.get("/test-specs/next-identifier")
    assert response.status_code == 200
    body = response.json()
    assert body["errors"] is None
    assert body["data"]["next"] == "TST-001"

    _make(client)
    response = client.get("/test-specs/next-identifier")
    assert response.json()["data"]["next"] == "TST-002"


# ---------------------------------------------------------------------------
# Criterion 10 — soft-delete / restore via REST
# ---------------------------------------------------------------------------


def test_soft_delete_then_restore_via_rest(client):
    _make(client)
    delete_response = client.delete("/test-specs/TST-001")
    assert delete_response.status_code == 200
    # Default GET 404s soft-deleted.
    get_response = client.get("/test-specs/TST-001")
    assert get_response.status_code == 404
    # Restore.
    restore_response = client.post("/test-specs/TST-001/restore")
    assert restore_response.status_code == 200
    # Now visible again.
    assert client.get("/test-specs/TST-001").status_code == 200


# ---------------------------------------------------------------------------
# Criterion 15 — references round-trip
# ---------------------------------------------------------------------------


def test_post_references_test_spec_touches_entity_round_trip(client):
    _make(client)
    # Create a target entity.
    entity_resp = client.post(
        "/entities",
        json={
            "entity_name": "Mentor Application",
            "entity_description": "An entity for the cross-edge round-trip test.",
        },
    )
    assert entity_resp.status_code == 201, entity_resp.text
    ent_id = entity_resp.json()["data"]["entity_identifier"]
    # POST the reference edge.
    ref_resp = client.post(
        "/references",
        json={
            "source_type": "test_spec",
            "source_id": "TST-001",
            "target_type": "entity",
            "target_id": ent_id,
            "relationship": "test_spec_touches_entity",
        },
    )
    assert ref_resp.status_code in (200, 201), ref_resp.text
    # The reference is visible from both ends.
    from_side = client.get(
        "/references", params={"source_id": "TST-001"}
    )
    assert from_side.status_code == 200
    rows_from = from_side.json()["data"]
    # Row dicts surface the relationship under the key ``relationship``
    # per ``references.py:_row_dict``.
    assert any(
        r.get("source_id") == "TST-001"
        and r.get("relationship") == "test_spec_touches_entity"
        for r in rows_from
    )
    to_side = client.get(
        "/references", params={"target_id": ent_id}
    )
    rows_to = to_side.json()["data"]
    assert any(
        r.get("target_id") == ent_id
        and r.get("relationship") == "test_spec_touches_entity"
        for r in rows_to
    )
