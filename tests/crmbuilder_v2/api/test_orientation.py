"""Orientation endpoints — Tier 2 reads from DEC-011."""

from __future__ import annotations


def _seed(client):
    # Two sessions, two decisions, refs from SES-001 to both decisions.
    for sid, date in [("SES-001", "05-06-26"), ("SES-002", "05-07-26")]:
        client.post(
            "/sessions",
            json={
                "identifier": sid,
                "title": sid,
                "session_date": date,
                "status": "Complete",
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
    assert rows[0]["identifier"] == "SES-002"


def test_decisions_for_session(client):
    _seed(client)
    r = client.get("/orientation/decisions-for-session/SES-001")
    assert r.status_code == 200
    rows = r.json()["data"]
    assert sorted(d["identifier"] for d in rows) == ["DEC-001", "DEC-002"]


def test_decisions_for_unknown_session_returns_404(client):
    r = client.get("/orientation/decisions-for-session/SES-NONE")
    assert r.status_code == 404
