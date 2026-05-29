"""Sessions endpoints (PI-073 / DEC-314 redesign).

Under the redesign a ``session`` is the medium-agnostic communication
container with a six-status lifecycle; it is no longer append-only. The
legacy fixture shape (bare ``title``/``status``/``identifier`` plus
``session_date``) is gone — POST bodies now use the ``session_*`` field
names, ``session_medium`` must be a valid vocab enum, and
``session_executive_summary`` is a required 200-800 character string
(PI-074/PI-075). Every live session also requires exactly one outbound
``session_belongs_to_workstream`` edge, supplied here via ``references``.
Responses key the identifier as ``session_identifier``.
"""

from __future__ import annotations

# A valid 200-800 char executive summary reused across fixtures.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _make_workstream(client):
    r = client.post(
        "/workstreams",
        json={
            "workstream_name": "WS for session tests",
            "workstream_purpose": "host sessions under test",
            "workstream_description": "fixture workstream",
        },
    )
    assert r.status_code == 201, r.json()
    return r.json()["data"]["workstream_identifier"]


def _member_edge(session_identifier, ws_id):
    return {
        "source_type": "session",
        "source_id": session_identifier,
        "target_type": "workstream",
        "target_id": ws_id,
        "relationship": "session_belongs_to_workstream",
    }


def _create(client, ws_id, identifier="SES-001", **overrides):
    """Create a session in the PI-073 shape with a workstream edge.

    Defaults to ``planned`` status (the only status that requires nothing
    beyond the membership edge).
    """
    body = {
        "session_identifier": identifier,
        "session_title": f"{identifier} title",
        "session_description": f"{identifier} description",
        "session_medium": "chat",
        "session_status": "planned",
        "session_executive_summary": _EXEC_SUMMARY,
        "references": [_member_edge(identifier, ws_id)],
    }
    body.update(overrides)
    return client.post("/sessions", json=body)


def test_create_then_get(client):
    ws_id = _make_workstream(client)
    r = _create(client, ws_id)
    assert r.status_code == 201, r.json()
    r = client.get("/sessions/SES-001")
    assert r.status_code == 200
    assert r.json()["data"]["session_identifier"] == "SES-001"


def test_patch_endpoint(client):
    """PI-073/DEC-314 — sessions are stateful, so PATCH is now supported.

    The legacy model was append-only with no PATCH route (the old test
    asserted 405); the redesign supersedes DEC-013, so a partial update
    must succeed and persist.
    """
    ws_id = _make_workstream(client)
    _create(client, ws_id)
    r = client.patch("/sessions/SES-001", json={"session_notes": "updated"})
    assert r.status_code == 200, r.json()
    r = client.get("/sessions/SES-001")
    assert r.json()["data"]["session_notes"] == "updated"


def test_list_orders_by_identifier(client):
    """The list endpoint returns sessions ordered ascending by identifier.

    (The legacy test passed ``?limit=1`` and expected the most-recent row
    first; the current router exposes no ``limit`` parameter and orders
    ascending, so both rows come back with SES-001 first.)
    """
    ws_id = _make_workstream(client)
    _create(client, ws_id, identifier="SES-001")
    _create(client, ws_id, identifier="SES-002")
    r = client.get("/sessions")
    rows = r.json()["data"]
    assert [row["session_identifier"] for row in rows] == ["SES-001", "SES-002"]


def test_delete(client):
    ws_id = _make_workstream(client)
    _create(client, ws_id)
    client.delete("/sessions/SES-001")
    r = client.get("/sessions/SES-001")
    assert r.status_code == 404


# PI-002 — POST without identifier returns 201 with server-assigned value.


def test_post_without_identifier_assigns_one(client):
    ws_id = _make_workstream(client)
    # Identifier is server-assigned; the membership edge must reference the
    # same value the server will assign (first session -> SES-001).
    r = client.post(
        "/sessions",
        json={
            "session_title": "Auto",
            "session_description": "Auto description",
            "session_medium": "chat",
            "session_status": "planned",
            "session_executive_summary": _EXEC_SUMMARY,
            "references": [_member_edge("SES-001", ws_id)],
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["session_identifier"] == "SES-001"


def test_post_with_invalid_identifier_format_returns_422(client):
    ws_id = _make_workstream(client)
    r = client.post(
        "/sessions",
        json={
            "session_identifier": "SES-1",
            "session_title": "Bad",
            "session_description": "Bad description",
            "session_medium": "chat",
            "session_status": "planned",
            "session_executive_summary": _EXEC_SUMMARY,
            "references": [_member_edge("SES-1", ws_id)],
        },
    )
    assert r.status_code == 422, r.json()
