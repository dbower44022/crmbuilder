"""Risks, planning items, and topics endpoints."""

from __future__ import annotations

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def test_risks_crud(client):
    body = {
        "identifier": "RSK-001",
        "title": "Schema design takes longer than budget",
        "probability": "Medium",
        "impact": "High",
        "status": "Open",
    }
    r = client.post("/risks", json=body)
    assert r.status_code == 201

    r = client.patch("/risks/RSK-001", json={"status": "Mitigated"})
    assert r.json()["data"]["status"] == "Mitigated"

    r = client.delete("/risks/RSK-001")
    assert r.status_code == 200


def test_planning_items_crud(client):
    body = {
        "identifier": "PI-006",
        "title": "Division of labor",
        "item_type": "planning_dimension",
        "status": "Open",
        "executive_summary": _VALID_EXEC_SUMMARY,
    }
    r = client.post("/planning-items", json=body)
    assert r.status_code == 201

    r = client.patch(
        "/planning-items/PI-006",
        json={"status": "Resolved", "resolution_reference": "DEC-020"},
    )
    assert r.json()["data"]["status"] == "Resolved"


def test_topics_hierarchy(client):
    client.post("/topics", json={"identifier": "TOP-001", "name": "Schema"})
    r = client.post(
        "/topics",
        json={
            "identifier": "TOP-002",
            "name": "References",
            "parent_topic": "TOP-001",
        },
    )
    assert r.status_code == 201
    r = client.get("/topics/TOP-002")
    assert r.json()["data"]["parent_topic_identifier"] == "TOP-001"


# ---------------------------------------------------------------------------
# PI-002 — POST without identifier returns 201 with server-assigned value
# ---------------------------------------------------------------------------


def test_post_risk_without_identifier_assigns_one(client):
    r = client.post(
        "/risks",
        json={
            "title": "Auto",
            "probability": "Medium",
            "impact": "High",
            "status": "Open",
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["identifier"] == "RSK-001"


def test_post_risk_with_invalid_format_returns_422(client):
    r = client.post(
        "/risks",
        json={
            "identifier": "RSK-1",
            "title": "Bad",
            "probability": "Medium",
            "impact": "High",
            "status": "Open",
        },
    )
    assert r.status_code == 422, r.json()


def test_post_planning_item_without_identifier_assigns_one(client):
    r = client.post(
        "/planning-items",
        json={"title": "Auto", "item_type": "open_question", "status": "Open",
              "executive_summary": _VALID_EXEC_SUMMARY},
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["identifier"] == "PI-001"


def test_post_planning_item_with_invalid_format_returns_422(client):
    r = client.post(
        "/planning-items",
        json={
            "identifier": "PI-1",
            "title": "Bad",
            "item_type": "open_question",
            "status": "Open",
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    assert r.status_code == 422, r.json()


def test_post_topic_without_identifier_assigns_one(client):
    r = client.post("/topics", json={"name": "Auto"})
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["identifier"] == "TOP-001"


def test_post_topic_with_invalid_format_returns_422(client):
    r = client.post("/topics", json={"identifier": "TOP-1", "name": "Bad"})
    assert r.status_code == 422, r.json()


# ---------------------------------------------------------------------------
# PI-076 — ``area`` field on planning items, end-to-end through the API
# ---------------------------------------------------------------------------


def test_planning_item_area_roundtrip(client):
    r = client.post(
        "/planning-items",
        json={
            "identifier": "PI-020",
            "title": "Area-bearing",
            "item_type": "pending_work",
            "status": "Open",
            "area": ["v2-access", "v2-api"],
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["area"] == ["v2-access", "v2-api"]

    r = client.get("/planning-items/PI-020")
    assert r.json()["data"]["area"] == ["v2-access", "v2-api"]

    r = client.patch("/planning-items/PI-020", json={"area": ["v2-ui"]})
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["area"] == ["v2-ui"]


def test_post_planning_item_with_unknown_area_returns_400(client):
    r = client.post(
        "/planning-items",
        json={
            "title": "Bad area",
            "item_type": "pending_work",
            "status": "Open",
            "area": ["not-a-real-area"],
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    assert r.status_code == 400, r.json()


def test_post_planning_item_without_area_is_null(client):
    r = client.post(
        "/planning-items",
        json={
            "title": "No area",
            "item_type": "pending_work",
            "status": "Open",
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    assert r.status_code == 201, r.json()
    assert r.json()["data"]["area"] is None


# ---------------------------------------------------------------------------
# PI-077 — claim / release endpoints
# ---------------------------------------------------------------------------


def test_planning_item_claim_release_roundtrip(client):
    client.post(
        "/planning-items",
        json={
            "identifier": "PI-040",
            "title": "Claimable",
            "item_type": "pending_work",
            "status": "Open",
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    r = client.post("/planning-items/PI-040/claim", json={"claimant": "CONV-100"})
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["claimed_by"] == "CONV-100"
    assert r.json()["data"]["claimed_at"] is not None

    r = client.post("/planning-items/PI-040/release", json={"claimant": "CONV-100"})
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["claimed_by"] is None


def test_claim_conflict_returns_409(client):
    client.post(
        "/planning-items",
        json={
            "identifier": "PI-041",
            "title": "Contended",
            "item_type": "pending_work",
            "status": "Open",
            "executive_summary": _VALID_EXEC_SUMMARY,
        },
    )
    client.post("/planning-items/PI-041/claim", json={"claimant": "CONV-100"})
    r = client.post("/planning-items/PI-041/claim", json={"claimant": "CONV-200"})
    assert r.status_code == 409, r.json()
