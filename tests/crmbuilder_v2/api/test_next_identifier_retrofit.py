"""GET /<entity>/next-identifier retrofit (UI v0.4 slice A, DEC-043).

Eight helper endpoints across the existing prefixed-identifier
governance entity types. Six prefix-NNN types (decision, session,
risk, planning_item, topic) plus references return ``{"next": ...}``;
charter and status return their next integer version.
"""

from __future__ import annotations

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7

# (path, repository plural prefix) for the six prefix-NNN style endpoints.
# planning-items uses a hyphenated router prefix.
_PREFIX_ENDPOINTS = [
    ("/decisions/next-identifier", "DEC-001"),
    ("/sessions/next-identifier", "SES-001"),
    ("/risks/next-identifier", "RSK-001"),
    ("/planning-items/next-identifier", "PI-001"),
    ("/topics/next-identifier", "TOP-001"),
]


# --------------------------------------------------------------------
# Happy path / empty-DB boundary
# --------------------------------------------------------------------

def test_prefix_endpoints_empty_db_return_001(client):
    """Boundary: an empty DB yields ``<PREFIX>-001`` for each prefix type."""
    for path, expected in _PREFIX_ENDPOINTS:
        r = client.get(path)
        assert r.status_code == 200, path
        assert r.json()["data"] == {"next": expected}, path


def test_references_endpoint_empty_db_returns_1(client):
    """References are tuple-identified; the helper returns the next int id."""
    r = client.get("/references/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"] == {"next": 1}


def test_charter_endpoint_empty_db_returns_version_1(client):
    r = client.get("/charter/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"] == {"next": 1}


def test_status_endpoint_empty_db_returns_version_1(client):
    r = client.get("/status/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"] == {"next": 1}


def test_all_eight_endpoints_respond_200(client):
    """Every retrofitted endpoint returns 200 with a ``next`` key."""
    paths = [p for p, _ in _PREFIX_ENDPOINTS] + [
        "/references/next-identifier",
        "/charter/next-identifier",
        "/status/next-identifier",
    ]
    for path in paths:
        r = client.get(path)
        assert r.status_code == 200, path
        assert "next" in r.json()["data"], path


# --------------------------------------------------------------------
# Increment after a write
# --------------------------------------------------------------------

def test_decisions_next_increments_after_create(client):
    r = client.get("/decisions/next-identifier")
    assert r.json()["data"]["next"] == "DEC-001"

    body = {
        "identifier": "DEC-001",
        "title": "first decision",
        "decision_date": "05-14-26",
        "status": "Active",
        "executive_summary": _VALID_EXEC_SUMMARY,
    }
    assert client.post("/decisions", json=body).status_code == 201

    r = client.get("/decisions/next-identifier")
    assert r.json()["data"]["next"] == "DEC-002"


def test_sessions_next_increments_after_create(client):
    # PI-073: a session is the medium-agnostic communication container and
    # requires exactly one ``session_belongs_to_workstream`` edge, supplied
    # here via ``references`` against a freshly-created workstream.
    ws = client.post(
        "/workstreams",
        json={
            "workstream_name": "WS for next-identifier test",
            "workstream_purpose": "host the session under test",
            "workstream_description": "fixture workstream",
        },
    )
    assert ws.status_code == 201, ws.json()
    ws_id = ws.json()["data"]["workstream_identifier"]

    body = {
        "session_identifier": "SES-001",
        "session_title": "first session",
        "session_description": "first session description",
        "session_medium": "chat",
        "session_status": "planned",
        "session_executive_summary": _VALID_EXEC_SUMMARY,
        "references": [
            {
                "source_type": "session",
                "source_id": "SES-001",
                "target_type": "workstream",
                "target_id": ws_id,
                "relationship": "session_belongs_to_workstream",
            }
        ],
    }
    assert client.post("/sessions", json=body).status_code == 201
    r = client.get("/sessions/next-identifier")
    assert r.json()["data"]["next"] == "SES-002"


def test_planning_items_next_increments_after_create(client):
    body = {
        "identifier": "PI-001",
        "title": "first item",
        "item_type": "planning_dimension",
        "status": "Open",
        "executive_summary": _VALID_EXEC_SUMMARY,
    }
    assert client.post("/planning-items", json=body).status_code == 201
    r = client.get("/planning-items/next-identifier")
    assert r.json()["data"]["next"] == "PI-002"


def test_references_next_increments_after_create(client):
    body = {
        "source_type": "decision",
        "source_id": "DEC-001",
        "target_type": "session",
        "target_id": "SES-001",
        "relationship": "is_about",
    }
    assert client.post("/references", json=body).status_code == 201
    r = client.get("/references/next-identifier")
    assert r.json()["data"]["next"] == 2


def test_charter_next_increments_after_replace(client):
    assert client.put("/charter", json={"payload": {"scope": "v1"}}).status_code == 200
    r = client.get("/charter/next-identifier")
    assert r.json()["data"]["next"] == 2


def test_status_next_increments_after_replace(client):
    assert client.put("/status", json={"payload": {"summary": "v1"}}).status_code == 200
    r = client.get("/status/next-identifier")
    assert r.json()["data"]["next"] == 2


# --------------------------------------------------------------------
# Concurrent fetch — the value is advisory; consuming it is atomic
# --------------------------------------------------------------------

def test_concurrent_fetch_then_atomic_consume(client):
    """Two fetches return the same identifier; the second POST that
    consumes it collides (409). The helper does not reserve the value —
    uniqueness is enforced at write time."""
    first = client.get("/decisions/next-identifier").json()["data"]["next"]
    second = client.get("/decisions/next-identifier").json()["data"]["next"]
    assert first == second == "DEC-001"

    body = {
        "identifier": first,
        "title": "winner",
        "decision_date": "05-14-26",
        "status": "Active",
        "executive_summary": _VALID_EXEC_SUMMARY,
    }
    assert client.post("/decisions", json=body).status_code == 201
    # The second consumer of the same identifier loses.
    body["title"] = "loser"
    assert client.post("/decisions", json=body).status_code == 409
