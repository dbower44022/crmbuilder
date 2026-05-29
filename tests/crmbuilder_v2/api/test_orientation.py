"""Orientation endpoints — Tier 2 reads from DEC-011."""

from __future__ import annotations

# A valid 200-800 char executive summary reused across the seeded
# governance records (required since PI-074/PI-075 and PI-102).
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _seed(client):
    # One workstream (sessions require exactly one session_belongs_to_workstream
    # edge per PI-073), two sessions, two decisions, refs from SES-001 to both
    # decisions.
    client.post(
        "/workstreams",
        json={
            "workstream_identifier": "WS-001",
            "workstream_name": "Orientation fixtures",
            "workstream_purpose": "House the seeded orientation-test sessions.",
            "workstream_description": "Test-only workstream for orientation reads.",
        },
    )
    for sid in ("SES-001", "SES-002"):
        client.post(
            "/sessions",
            json={
                "session_identifier": sid,
                "session_title": sid,
                "session_description": f"Seeded session {sid}.",
                "session_medium": "chat",
                "session_status": "in_flight",
                "session_executive_summary": _EXEC_SUMMARY,
                "references": [
                    {
                        "source_type": "session",
                        "source_id": sid,
                        "target_type": "workstream",
                        "target_id": "WS-001",
                        "relationship": "session_belongs_to_workstream",
                    }
                ],
            },
        )
    for did in ("DEC-001", "DEC-002"):
        client.post(
            "/decisions",
            json={
                "identifier": did,
                "title": did,
                "decision_date": "05-06-26",
                "status": "Active",
                "executive_summary": _EXEC_SUMMARY,
            },
        )
    for did in ("DEC-001", "DEC-002"):
        client.post(
            "/references",
            json={
                "source_type": "session",
                "source_id": "SES-001",
                "target_type": "decision",
                "target_id": did,
                "relationship": "decided_in",
            },
        )


def test_recent_sessions(client):
    _seed(client)
    r = client.get("/orientation/recent-sessions?limit=1")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert len(rows) == 1
    # recent-sessions lists sessions ordered by identifier and applies the
    # limit to the head of that list, so limit=1 yields the first session.
    assert rows[0]["session_identifier"] == "SES-001"


def test_decisions_for_session(client):
    _seed(client)
    r = client.get("/orientation/decisions-for-session/SES-001")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert sorted(d["identifier"] for d in rows) == ["DEC-001", "DEC-002"]


def test_decisions_for_unknown_session_returns_404(client):
    r = client.get("/orientation/decisions-for-session/SES-NONE")
    assert r.status_code == 404
