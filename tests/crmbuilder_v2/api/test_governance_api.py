"""Governance entity REST endpoint tests — UI v0.7 Slice B.

Covers the six new routers' happy paths and envelope shape, list filters,
identifier auto-assignment, the reference_book version sub-endpoints, the
deposit_event reduced surface (HTTP 405 on write methods), the atomic
deposit_event POST, and the GET /references server-side filter fix.
"""

from __future__ import annotations


def _envelope(resp):
    body = resp.json()
    assert set(body) == {"data", "meta", "errors"}
    return body


def _ws(client, name="WS A"):
    r = client.post(
        "/workstreams",
        json={"workstream_name": name, "workstream_purpose": "p",
              "workstream_description": "d"},
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["workstream_identifier"]


# A reusable, schema-valid 200-800 char executive summary (PI-074/PI-075).
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _session(client, ws_id, identifier="SES-100", title="Sess A"):
    """Create a session (PI-073: medium-agnostic communication container).

    Requires exactly one ``session_belongs_to_workstream`` edge.
    """
    r = client.post(
        "/sessions",
        json={
            "session_identifier": identifier,
            "session_title": title,
            "session_description": "d",
            "session_medium": "chat",
            "session_executive_summary": _EXEC_SUMMARY,
            "references": [{
                "source_type": "session", "source_id": identifier,
                "target_type": "workstream", "target_id": ws_id,
                "relationship": "session_belongs_to_workstream",
            }],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["session_identifier"]


def _conv(client, ws_id, identifier="CNV-001", title="Conv A", session_id=None):
    """Create a conversation (PI-073: topical sub-unit within a session).

    New ``CNV-NNN`` prefix; requires exactly one
    ``conversation_belongs_to_session`` edge. When ``session_id`` is not
    supplied, a session is created under ``ws_id`` first.
    """
    if session_id is None:
        # Derive a distinct session identifier from the conversation number
        # so repeated _conv calls within one test get distinct sessions
        # (offset into the SES-2NN band to avoid colliding with _session's
        # SES-100 default). Stays within the ^SES-\d{3}$ format.
        num = int(identifier.split("-", 1)[1])
        session_id = _session(client, ws_id, identifier=f"SES-2{num:02d}")
    r = client.post(
        "/conversations",
        json={
            "conversation_title": title, "conversation_purpose": "p",
            "conversation_description": "d", "conversation_identifier": identifier,
            "references": [{
                "source_type": "conversation", "source_id": identifier,
                "target_type": "session", "target_id": session_id,
                "relationship": "conversation_belongs_to_session",
            }],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["conversation_identifier"]


# --- workstreams ------------------------------------------------------------


def test_workstream_crud_and_envelope(client):
    r = client.post(
        "/workstreams",
        json={"workstream_name": "Gov", "workstream_purpose": "p",
              "workstream_description": "d"},
    )
    assert r.status_code == 201
    body = _envelope(r)
    assert body["data"]["workstream_identifier"] == "WS-001"
    assert client.get("/workstreams/next-identifier").json()["data"]["next"] == "WS-002"
    assert client.get("/workstreams/WS-404").status_code == 404
    # patch transition
    r = client.patch("/workstreams/WS-001", json={"workstream_status": "in_flight"})
    assert r.json()["data"]["workstream_started_at"]
    # delete + restore
    assert client.delete("/workstreams/WS-001").status_code == 200
    assert client.get("/workstreams").json()["data"] == []
    assert client.post("/workstreams/WS-001/restore").status_code == 200


def test_workstream_validation_failure_envelope(client):
    r = client.post(
        "/workstreams",
        json={"workstream_name": "X", "workstream_purpose": "p",
              "workstream_description": "d", "workstream_identifier": "WS-1"},
    )
    assert r.status_code == 422
    body = _envelope(r)
    assert body["data"] is None and body["errors"]


# --- conversations ----------------------------------------------------------


def test_conversation_membership_and_filters(client):
    ws = _ws(client)
    # missing membership (no conversation_belongs_to_session edge) -> 422
    r = client.post(
        "/conversations",
        json={"conversation_title": "No session", "conversation_purpose": "p",
              "conversation_description": "d"},
    )
    assert r.status_code == 422
    # Two conversations under one shared session; the session_identifier
    # filter replaces the removed workstream_identifier filter (PI-073:
    # conversations belong to sessions, not workstreams).
    ses = _session(client, ws)
    _conv(client, ws, "CNV-001", "A", session_id=ses)
    _conv(client, ws, "CNV-002", "B", session_id=ses)
    assert len(client.get(f"/conversations?session_identifier={ses}").json()["data"]) == 2
    client.patch("/conversations/CNV-001", json={"conversation_status": "in_flight"})
    assert len(client.get("/conversations?status=in_flight").json()["data"]) == 1


# --- reference_books + version sub-endpoints --------------------------------


def test_reference_book_versions_endpoints(client):
    r = client.post(
        "/reference-books",
        json={
            "reference_book_title": "Plan", "reference_book_description": "d",
            "reference_book_kind": "workstream_master_plan",
            "reference_book_file_path": "PRDs/p.md",
            "versions": [{"version_label": "1.0", "version_date": "2026-05-11T00:00:00"}],
        },
    )
    assert r.status_code == 201
    rid = r.json()["data"]["reference_book_identifier"]
    assert r.json()["data"]["reference_book_current_version_label"] == "1.0"
    add = client.post(
        f"/reference-books/{rid}/versions",
        json={"version_label": "1.1", "version_date": "2026-05-12T00:00:00"},
    )
    assert add.status_code == 201
    versions = client.get(f"/reference-books/{rid}/versions").json()["data"]
    assert len(versions) == 2
    at = client.get(f"/reference-books/{rid}/version-at?as_of=2026-05-11")
    assert at.json()["data"]["reference_book_version_label"] == "1.0"
    assert client.get(f"/reference-books/{rid}/version-at?as_of=2026-05-01").json()["data"] is None
    # kind filter
    assert len(client.get("/reference-books?kind=workstream_master_plan").json()["data"]) == 1


# --- work_tickets -----------------------------------------------------------


def test_work_ticket_filters(client):
    for k in ("kickoff_prompt", "claude_code_prompt"):
        client.post(
            "/work-tickets",
            json={"work_ticket_title": "WT " + k, "work_ticket_description": "d",
                  "work_ticket_kind": k, "work_ticket_file_path": "PRDs/k.md"},
        )
    assert len(client.get("/work-tickets?kind=claude_code_prompt").json()["data"]) == 1
    assert len(client.get("/work-tickets").json()["data"]) == 2


# --- close_out_payloads -----------------------------------------------------


def test_close_out_payload_production_edge_required(client):
    r = client.post(
        "/close-out-payloads",
        json={"close_out_payload_title": "P", "close_out_payload_description": "d",
              "close_out_payload_file_path": "close-out-payloads/x.json"},
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "payload_requires_producing_conversation_edge"


# --- deposit_events: atomic POST + reduced surface --------------------------


def _ready_cop(client, identifier="COP-001"):
    ws = _ws(client)
    conv = _conv(client, ws)
    r = client.post(
        "/close-out-payloads",
        json={
            "close_out_payload_title": "P", "close_out_payload_description": "d",
            "close_out_payload_file_path": "close-out-payloads/x.json",
            "close_out_payload_identifier": identifier,
            "close_out_payload_status": "ready",
            "references": [{
                "source_type": "close_out_payload", "source_id": identifier,
                "target_type": "conversation", "target_id": conv,
                "relationship": "close_out_payload_produced_by_conversation",
            }],
        },
    )
    assert r.status_code == 201, r.text
    return identifier


def test_deposit_event_success_drives_applied(client):
    cop = _ready_cop(client)
    r = client.post(
        "/deposit-events",
        json={
            "deposit_event_title": "Apply", "deposit_event_description": "ok",
            "deposit_event_outcome": "success",
            "deposit_event_records_summary": {"sessions": 1},
            "deposit_event_apply_context": {"runner": "test"},
            "deposit_event_log_file_path": "deposit-event-logs/dep_001.log",
            "references": [
                {"target_type": "close_out_payload", "target_id": cop,
                 "relationship": "deposit_event_applies_close_out_payload"},
                {"target_type": "session", "target_id": "SES-049",
                 "relationship": "deposit_event_wrote_record"},
            ],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["data"]["deposit_event_identifier"] == "DEP-001"
    assert client.get(f"/close-out-payloads/{cop}").json()["data"][
        "close_out_payload_status"
    ] == "applied"


def test_deposit_event_reduced_surface(client):
    # PUT/PATCH/DELETE on the collection / item paths -> 405.
    assert client.put("/deposit-events/DEP-001", json={}).status_code == 405
    assert client.patch("/deposit-events/DEP-001", json={}).status_code == 405
    assert client.delete("/deposit-events/DEP-001").status_code == 405
    # restore path is not registered at all -> 404 (acceptable per spec §3.5).
    assert client.post("/deposit-events/DEP-001/restore").status_code in (404, 405)


def test_deposit_event_outcome_filter(client):
    cop = _ready_cop(client)
    client.post(
        "/deposit-events",
        json={"deposit_event_title": "ok", "deposit_event_description": "d",
              "deposit_event_outcome": "success",
              "deposit_event_records_summary": {"sessions": 0},
              "deposit_event_apply_context": {}, "deposit_event_log_file_path": "deposit-event-logs/d.log",
              "references": [{"target_type": "close_out_payload", "target_id": cop,
                              "relationship": "deposit_event_applies_close_out_payload"}]},
    )
    assert len(client.get("/deposit-events?outcome=success").json()["data"]) == 1
    assert len(client.get("/deposit-events?outcome=failure").json()["data"]) == 0


# --- /references filter fix (commit dcb7377) --------------------------------


def test_references_filter_honored_server_side(client):
    _ws(client, "A")  # WS-001
    _ws(client, "B")  # WS-002
    # supersede WS-001 -> creates a supersedes edge WS-001 -> WS-002.
    client.patch(
        "/workstreams/WS-001",
        json={"workstream_status": "superseded",
              "references": [{"source_type": "workstream", "source_id": "WS-001",
                              "target_type": "workstream", "target_id": "WS-002",
                              "relationship": "supersedes"}]},
    )
    everything = client.get("/references").json()["data"]
    assert len(everything) >= 1
    by_kind = client.get("/references?relationship_kind=supersedes").json()["data"]
    assert len(by_kind) == 1 and by_kind[0]["relationship"] == "supersedes"
    by_source = client.get(
        "/references?source_type=workstream&source_id=WS-001"
    ).json()["data"]
    assert len(by_source) == 1
    # composed filter that matches nothing
    assert client.get(
        "/references?relationship_kind=supersedes&target_id=WS-999"
    ).json()["data"] == []
