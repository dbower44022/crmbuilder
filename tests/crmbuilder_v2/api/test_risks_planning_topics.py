"""Risks, planning items, and topics endpoints."""

from __future__ import annotations


def test_risks_crud(client):
    body = {
        "identifier": "RISK-001",
        "title": "Schema design takes longer than budget",
        "probability": "Medium",
        "impact": "High",
        "status": "Open",
    }
    r = client.post("/risks", json=body)
    assert r.status_code == 201

    r = client.patch("/risks/RISK-001", json={"status": "Mitigated"})
    assert r.json()["data"]["status"] == "Mitigated"

    r = client.delete("/risks/RISK-001")
    assert r.status_code == 200


def test_planning_items_crud(client):
    body = {
        "identifier": "PI-006",
        "title": "Division of labor",
        "item_type": "planning_dimension",
        "status": "Open",
    }
    r = client.post("/planning-items", json=body)
    assert r.status_code == 201

    r = client.patch(
        "/planning-items/PI-006",
        json={"status": "Resolved", "resolution_reference": "DEC-020"},
    )
    assert r.json()["data"]["status"] == "Resolved"


def test_topics_hierarchy(client):
    client.post("/topics", json={"identifier": "TOPIC-A", "name": "Schema"})
    r = client.post(
        "/topics",
        json={
            "identifier": "TOPIC-B",
            "name": "References",
            "parent_topic": "TOPIC-A",
        },
    )
    assert r.status_code == 201
    r = client.get("/topics/TOPIC-B")
    assert r.json()["data"]["parent_topic_identifier"] == "TOPIC-A"
