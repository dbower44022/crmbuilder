"""PI-102 — API contract for the now-required executive_summary.

Omitting the field entirely is a Pydantic schema violation (422);
supplying an out-of-range value is an access-layer ValidationError
(400). Previously both produced either a silent success or a database
IntegrityError (500); this locks in the clean validation behaviour.
"""

from __future__ import annotations

_VALID = "PI-102 executive summary used for API contract tests. " * 5  # ~270


def test_post_decision_missing_summary_returns_422(client):
    r = client.post(
        "/decisions",
        json={
            "identifier": "DEC-001",
            "title": "t",
            "decision_date": "05-07-26",
            "status": "Active",
        },
    )
    assert r.status_code == 422


def test_post_decision_short_summary_returns_400(client):
    r = client.post(
        "/decisions",
        json={
            "identifier": "DEC-001",
            "title": "t",
            "decision_date": "05-07-26",
            "status": "Active",
            "executive_summary": "too short",
        },
    )
    assert r.status_code == 400
    assert r.json()["errors"][0]["field"] == "executive_summary"


def test_post_decision_valid_summary_succeeds(client):
    r = client.post(
        "/decisions",
        json={
            "identifier": "DEC-001",
            "title": "t",
            "decision_date": "05-07-26",
            "status": "Active",
            "executive_summary": _VALID,
        },
    )
    assert r.status_code == 201
    assert r.json()["data"]["executive_summary"] == _VALID


def test_post_planning_item_missing_summary_returns_422(client):
    r = client.post(
        "/planning-items",
        json={
            "identifier": "PI-001",
            "title": "t",
            "item_type": "pending_work",
            "status": "Open",
        },
    )
    assert r.status_code == 422


def test_post_session_missing_summary_returns_422(client):
    r = client.post(
        "/sessions",
        json={
            "session_title": "t",
            "session_description": "d",
            "session_medium": "chat",
        },
    )
    assert r.status_code == 422
