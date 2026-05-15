"""CRM Candidates REST endpoint tests — UI v0.4 slice E.

Covers ``crm_candidate.md`` section 3.7 acceptance criterion 6 (all
eight endpoints, happy path + validation failures, v2 error envelope)
and criterion 7 (identifier auto-assignment, including under
concurrent POSTs). Includes API-level singleton-``selected`` 422
dedicated-body assertions.
"""

from __future__ import annotations

import threading

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make(client, **overrides) -> dict:
    """POST a crm_candidate, returning the created record dict."""
    body = {
        "crm_candidate_name": overrides.pop("crm_candidate_name", "EspoCRM"),
        "crm_candidate_fit_reason": overrides.pop(
            "crm_candidate_fit_reason",
            "Open source self-hostable platform with strong customization.",
        ),
    }
    body.update(overrides)
    response = client.post("/crm_candidates", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 6 — the eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["crm_candidate_identifier"] == "CRM-001"
    assert record["crm_candidate_status"] == "active"
    assert record["crm_candidate_deleted_at"] is None


def test_get_list_and_single(client):
    _make(client, crm_candidate_name="EspoCRM")
    _make(client, crm_candidate_name="SuiteCRM")
    listing = client.get("/crm_candidates")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/crm_candidates/CRM-001")
    assert single.status_code == 200
    assert single.json()["data"]["crm_candidate_name"] == "EspoCRM"


def test_get_missing_returns_404(client):
    response = client.get("/crm_candidates/CRM-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    _make(client, crm_candidate_name="Old")
    response = client.put(
        "/crm_candidates/CRM-001",
        json={
            "crm_candidate_identifier": "CRM-001",
            "crm_candidate_name": "New",
            "crm_candidate_fit_reason": "nfr",
            "crm_candidate_notes": "now noted",
            "crm_candidate_status": "declined",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["crm_candidate_name"] == "New"
    assert data["crm_candidate_status"] == "declined"
    assert data["crm_candidate_notes"] == "now noted"


def test_put_identifier_mismatch_returns_422(client):
    _make(client)
    response = client.put(
        "/crm_candidates/CRM-001",
        json={
            "crm_candidate_identifier": "CRM-999",
            "crm_candidate_name": "X",
            "crm_candidate_fit_reason": "fr",
            "crm_candidate_status": "active",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "crm_candidate_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/crm_candidates/CRM-001",
        json={"crm_candidate_fit_reason": "sharpened reason"},
    )
    assert response.status_code == 200
    assert (
        response.json()["data"]["crm_candidate_fit_reason"]
        == "sharpened reason"
    )


def test_patch_invalid_terminal_transition_returns_422_with_error_body(client):
    _make(client)
    client.patch(
        "/crm_candidates/CRM-001", json={"crm_candidate_status": "selected"}
    )
    response = client.patch(
        "/crm_candidates/CRM-001",
        json={"crm_candidate_status": "declined"},
    )
    assert response.status_code == 422
    # Dedicated body shape per crm_candidate.md section 3.5.3 — not the
    # standard {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_status_transition",
        "from": "selected",
        "to": "declined",
    }


def test_post_with_selected_when_one_exists_returns_dedicated_422(client):
    _make(
        client, crm_candidate_name="EspoCRM", crm_candidate_status="selected"
    )
    response = client.post(
        "/crm_candidates",
        json={
            "crm_candidate_name": "SuiteCRM",
            "crm_candidate_fit_reason": "fr",
            "crm_candidate_status": "selected",
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "selected_candidate_already_exists",
        "existing": "CRM-001",
    }


def test_patch_into_selected_when_one_exists_returns_dedicated_422(client):
    _make(client, crm_candidate_name="EspoCRM", crm_candidate_status="selected")
    _make(client, crm_candidate_name="SuiteCRM")
    response = client.patch(
        "/crm_candidates/CRM-002",
        json={"crm_candidate_status": "selected"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "selected_candidate_already_exists",
        "existing": "CRM-001",
    }


def test_post_malformed_identifier_returns_422(client):
    response = client.post(
        "/crm_candidates",
        json={
            "crm_candidate_name": "Bad",
            "crm_candidate_fit_reason": "fr",
            "crm_candidate_identifier": "CRM-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "crm_candidate_identifier"


def test_post_duplicate_name_returns_422(client):
    _make(client, crm_candidate_name="EspoCRM")
    response = client.post(
        "/crm_candidates",
        json={
            "crm_candidate_name": "espocrm",
            "crm_candidate_fit_reason": "fr",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "crm_candidate_name"


def test_post_unknown_status_returns_422(client):
    response = client.post(
        "/crm_candidates",
        json={
            "crm_candidate_name": "X",
            "crm_candidate_fit_reason": "fr",
            "crm_candidate_status": "archived",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "crm_candidate_status"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/crm_candidates/CRM-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["crm_candidate_deleted_at"] is not None
    assert client.get("/crm_candidates/CRM-001").status_code == 404
    shown = client.get("/crm_candidates/CRM-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/crm_candidates").json()["data"] == []
    assert (
        len(
            client.get("/crm_candidates?include_deleted=true").json()["data"]
        )
        == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/crm_candidates/CRM-001")
    restored = client.post("/crm_candidates/CRM-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["crm_candidate_deleted_at"] is None
    assert client.get("/crm_candidates/CRM-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/crm_candidates/CRM-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


def test_restore_selected_when_another_selected_returns_dedicated_422(client):
    _make(
        client, crm_candidate_name="EspoCRM", crm_candidate_status="selected"
    )
    client.delete("/crm_candidates/CRM-001")
    _make(
        client, crm_candidate_name="SuiteCRM", crm_candidate_status="selected"
    )
    response = client.post("/crm_candidates/CRM-001/restore")
    assert response.status_code == 422
    assert response.json() == {
        "error": "selected_candidate_already_exists",
        "existing": "CRM-002",
    }


# ---------------------------------------------------------------------------
# Criterion 7 — identifier auto-assignment
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/crm_candidates/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "CRM-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/crm_candidates/next-identifier")
    assert response.json()["data"] == {"next": "CRM-002"}


def test_post_omitted_identifier_auto_assigns_and_echoes(client):
    first = _make(client, crm_candidate_name="A")
    second = _make(client, crm_candidate_name="B")
    assert first["crm_candidate_identifier"] == "CRM-001"
    assert second["crm_candidate_identifier"] == "CRM-002"


def test_concurrent_posts_get_distinct_identifiers(v2_env):
    """Eight simultaneous POSTs never share an identifier (criterion 7)."""
    identifiers: list[str] = []
    failures: list[str] = []

    def worker(index: int) -> None:
        thread_client = TestClient(create_app())
        response = thread_client.post(
            "/crm_candidates",
            json={
                "crm_candidate_name": f"Concurrent {index}",
                "crm_candidate_fit_reason": "fr",
            },
        )
        if response.status_code != 201:
            failures.append(response.text)
            return
        identifiers.append(response.json()["data"]["crm_candidate_identifier"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    assert len(identifiers) == 8
    assert len(set(identifiers)) == 8
