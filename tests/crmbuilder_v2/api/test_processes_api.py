"""Processes REST endpoint tests — UI v0.4 slice D.

Covers ``process.md`` section 3.7 acceptance criteria 7 (all eight
endpoints, happy path + validation failures, v2 error envelope and the
two dedicated-body errors) and 8 (identifier auto-assignment, including
under concurrent POSTs).
"""

from __future__ import annotations

import threading

from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient


def _make_domain(client, name: str = "Mentoring") -> str:
    """POST a domain, returning its identifier."""
    response = client.post(
        "/domains",
        json={
            "domain_name": name,
            "domain_purpose": "Why it exists",
            "domain_description": "What it covers",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["domain_identifier"]


def _make(client, *, domain_identifier: str | None = None, **overrides) -> dict:
    """POST a process, returning the created record dict."""
    if domain_identifier is None:
        domain_identifier = _make_domain(client)
    body = {
        "process_name": overrides.pop("process_name", "Mentor Recruit"),
        "process_domain_identifier": domain_identifier,
        "process_purpose": overrides.pop(
            "process_purpose", "Bring mentors into the program"
        ),
    }
    body.update(overrides)
    response = client.post("/processes", json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Criterion 7 — the eight endpoints, happy path
# ---------------------------------------------------------------------------


def test_post_creates_with_server_assigned_identifier(client):
    record = _make(client)
    assert record["process_identifier"] == "PROC-001"
    assert record["process_classification"] == "unclassified"
    assert record["process_deleted_at"] is None


def test_get_list_and_single(client):
    dom = _make_domain(client)
    _make(client, domain_identifier=dom, process_name="Mentor Recruit")
    _make(client, domain_identifier=dom, process_name="Client Recruit")
    listing = client.get("/processes")
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 2
    single = client.get("/processes/PROC-001")
    assert single.status_code == 200
    assert single.json()["data"]["process_name"] == "Mentor Recruit"


def test_get_missing_returns_404(client):
    response = client.get("/processes/PROC-404")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_put_full_replace(client):
    dom = _make(client)["process_domain_identifier"]
    response = client.put(
        "/processes/PROC-001",
        json={
            "process_identifier": "PROC-001",
            "process_name": "New",
            "process_domain_identifier": dom,
            "process_purpose": "np",
            "process_classification": "supporting",
            "process_classification_rationale": "not critical path",
            "process_notes": "now noted",
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["process_name"] == "New"
    assert data["process_classification"] == "supporting"
    assert data["process_notes"] == "now noted"


def test_put_identifier_mismatch_returns_422(client):
    dom = _make(client)["process_domain_identifier"]
    response = client.put(
        "/processes/PROC-001",
        json={
            "process_identifier": "PROC-999",
            "process_name": "X",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_classification": "unclassified",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "process_identifier"


def test_patch_partial_update(client):
    _make(client)
    response = client.patch(
        "/processes/PROC-001",
        json={"process_purpose": "sharpened purpose"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["process_purpose"] == "sharpened purpose"


def test_patch_invalid_classification_transition_returns_422(client):
    _make(client)
    client.patch(
        "/processes/PROC-001",
        json={"process_classification": "mission_critical"},
    )
    response = client.patch(
        "/processes/PROC-001",
        json={"process_classification": "unclassified"},
    )
    assert response.status_code == 422
    # Dedicated body shape per process.md section 3.5.3 — not the
    # standard {data, meta, errors} envelope.
    assert response.json() == {
        "error": "invalid_classification_transition",
        "from": "mission_critical",
        "to": "unclassified",
    }


def test_post_unknown_classification_returns_422(client):
    dom = _make_domain(client)
    response = client.post(
        "/processes",
        json={
            "process_name": "X",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_classification": "critical",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "process_classification"


def test_post_nonexistent_domain_returns_422_dedicated_body(client):
    response = client.post(
        "/processes",
        json={
            "process_name": "X",
            "process_domain_identifier": "DOM-404",
            "process_purpose": "p",
        },
    )
    assert response.status_code == 422
    # Dedicated body shape per process.md section 3.5.4.
    assert response.json() == {
        "error": "invalid_domain_reference",
        "domain_identifier": "DOM-404",
    }


def test_post_soft_deleted_domain_returns_422(client):
    dom = _make_domain(client)
    client.delete(f"/domains/{dom}")
    response = client.post(
        "/processes",
        json={
            "process_name": "X",
            "process_domain_identifier": dom,
            "process_purpose": "p",
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_domain_reference",
        "domain_identifier": dom,
    }


def test_patch_invalid_domain_returns_422(client):
    _make(client)
    response = client.patch(
        "/processes/PROC-001",
        json={"process_domain_identifier": "DOM-404"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "error": "invalid_domain_reference",
        "domain_identifier": "DOM-404",
    }


def test_post_malformed_identifier_returns_422(client):
    dom = _make_domain(client)
    response = client.post(
        "/processes",
        json={
            "process_name": "Bad",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_identifier": "PROC-1",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["data"] is None
    assert body["errors"][0]["field"] == "process_identifier"


def test_post_duplicate_name_returns_422(client):
    dom = _make(client, process_name="Mentor Recruit")[
        "process_domain_identifier"
    ]
    response = client.post(
        "/processes",
        json={
            "process_name": "mentor recruit",
            "process_domain_identifier": dom,
            "process_purpose": "p",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "process_name"


def test_delete_then_get_default_and_include_deleted(client):
    _make(client)
    deleted = client.delete("/processes/PROC-001")
    assert deleted.status_code == 200
    assert deleted.json()["data"]["process_deleted_at"] is not None
    assert client.get("/processes/PROC-001").status_code == 404
    shown = client.get("/processes/PROC-001?include_deleted=true")
    assert shown.status_code == 200
    assert client.get("/processes").json()["data"] == []
    assert (
        len(client.get("/processes?include_deleted=true").json()["data"])
        == 1
    )


def test_restore_round_trip(client):
    _make(client)
    client.delete("/processes/PROC-001")
    restored = client.post("/processes/PROC-001/restore")
    assert restored.status_code == 200
    assert restored.json()["data"]["process_deleted_at"] is None
    assert client.get("/processes/PROC-001").status_code == 200


def test_restore_on_live_record_returns_422(client):
    _make(client)
    response = client.post("/processes/PROC-001/restore")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_deleted"


# ---------------------------------------------------------------------------
# Criterion 8 — identifier auto-assignment
# ---------------------------------------------------------------------------


def test_next_identifier_empty_db(client):
    response = client.get("/processes/next-identifier")
    assert response.status_code == 200
    assert response.json()["data"] == {"next": "PROC-001"}


def test_next_identifier_increments_after_create(client):
    _make(client)
    response = client.get("/processes/next-identifier")
    assert response.json()["data"] == {"next": "PROC-002"}


def test_post_omitted_identifier_auto_assigns(client):
    dom = _make_domain(client)
    first = _make(client, domain_identifier=dom, process_name="A")
    second = _make(client, domain_identifier=dom, process_name="B")
    assert first["process_identifier"] == "PROC-001"
    assert second["process_identifier"] == "PROC-002"


def test_concurrent_posts_get_distinct_identifiers(v2_env):
    """Eight simultaneous POSTs never share an identifier (criterion 8)."""
    setup_client = TestClient(create_app())
    setup_client.headers.update({"X-Engagement": "ENG-001"})
    dom = _make_domain(setup_client)

    identifiers: list[str] = []
    failures: list[str] = []

    def worker(index: int) -> None:
        thread_client = TestClient(create_app())
        thread_client.headers.update({"X-Engagement": "ENG-001"})
        response = thread_client.post(
            "/processes",
            json={
                "process_name": f"Concurrent {index}",
                "process_domain_identifier": dom,
                "process_purpose": "p",
            },
        )
        if response.status_code != 201:
            failures.append(response.text)
            return
        identifiers.append(response.json()["data"]["process_identifier"])

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert failures == []
    assert len(identifiers) == 8
    assert len(set(identifiers)) == 8


# ---------------------------------------------------------------------------
# v0.8 process v2 schema growth — PI-005, process-v2.md §3.7
# ---------------------------------------------------------------------------


_PHASE3_FIELDS = (
    "process_steps",
    "process_triggers",
    "process_outcomes",
    "process_edge_cases",
    "process_frequency",
    "process_duration_estimate",
)


def test_post_with_phase3_fields_persists_and_get_returns(client):
    """POST a process with all six Phase 3 fields populated; GET returns them.

    Satisfies ``process-v2.md`` §3.7 acceptance criterion 5 (REST surface).
    """
    dom = _make_domain(client)
    response = client.post(
        "/processes",
        json={
            "process_name": "Phase 3 record",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_steps": "1. one 2. two",
            "process_triggers": "trigger text",
            "process_outcomes": "outcome text",
            "process_edge_cases": "edge case text",
            "process_frequency": "weekly",
            "process_duration_estimate": "5 minutes",
        },
    )
    assert response.status_code == 201, response.text
    identifier = response.json()["data"]["process_identifier"]
    got = client.get(f"/processes/{identifier}")
    assert got.status_code == 200
    data = got.json()["data"]
    assert data["process_steps"] == "1. one 2. two"
    assert data["process_triggers"] == "trigger text"
    assert data["process_outcomes"] == "outcome text"
    assert data["process_edge_cases"] == "edge case text"
    assert data["process_frequency"] == "weekly"
    assert data["process_duration_estimate"] == "5 minutes"


def test_get_v04_record_returns_null_phase3_fields(client):
    """A POST without Phase 3 fields is GET-able with all six as None.

    Satisfies ``process-v2.md`` §3.7 acceptance criterion 3 (REST view).
    """
    record = _make(client)
    identifier = record["process_identifier"]
    got = client.get(f"/processes/{identifier}")
    data = got.json()["data"]
    for field in _PHASE3_FIELDS:
        assert data[field] is None, field


def test_patch_phase3_null_clears_via_api(client):
    """PATCH process_steps to JSON null clears the column via the REST API.

    Satisfies ``process-v2.md`` §3.5.2 (REST surface).
    """
    dom = _make_domain(client)
    posted = client.post(
        "/processes",
        json={
            "process_name": "Patch target",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_steps": "initial steps",
        },
    )
    identifier = posted.json()["data"]["process_identifier"]
    patched = client.patch(
        f"/processes/{identifier}", json={"process_steps": None}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["process_steps"] is None


def test_patch_phase3_empty_string_stored_via_api(client):
    """PATCH process_steps to "" stores empty string via the REST API.

    Satisfies ``process-v2.md`` §3.5.2 (REST surface).
    """
    dom = _make_domain(client)
    posted = client.post(
        "/processes",
        json={
            "process_name": "Empty target",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_steps": "initial steps",
        },
    )
    identifier = posted.json()["data"]["process_identifier"]
    patched = client.patch(
        f"/processes/{identifier}", json={"process_steps": ""}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["process_steps"] == ""


def test_put_omitting_phase3_clears_via_api(client):
    """PUT replacing the record without Phase 3 fields clears all six.

    Satisfies ``process-v2.md`` §3.5.2 (REST PUT semantics).
    """
    dom = _make_domain(client)
    posted = client.post(
        "/processes",
        json={
            "process_name": "PUT target",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_steps": "initial steps",
            "process_triggers": "initial triggers",
            "process_outcomes": "initial outcomes",
            "process_edge_cases": "initial edge cases",
            "process_frequency": "initial frequency",
            "process_duration_estimate": "initial duration",
        },
    )
    identifier = posted.json()["data"]["process_identifier"]
    # PUT without any of the six Phase 3 fields. Their absence means
    # the schema defaults each to None, which the access layer
    # interprets as a clear.
    replaced = client.put(
        f"/processes/{identifier}",
        json={
            "process_name": "PUT target",
            "process_domain_identifier": dom,
            "process_purpose": "p",
            "process_classification": "unclassified",
        },
    )
    assert replaced.status_code == 200, replaced.text
    data = replaced.json()["data"]
    for field in _PHASE3_FIELDS:
        assert data[field] is None, field
