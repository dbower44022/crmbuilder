"""Identifier reservation endpoint (PI-078)."""

from __future__ import annotations


def test_reserve_endpoint_returns_block(client):
    r = client.post(
        "/identifiers/reserve", json={"entity_type": "planning_item", "count": 3}
    )
    assert r.status_code == 200, r.json()
    data = r.json()["data"]
    assert data["reserved"] == ["PI-001", "PI-002", "PI-003"]
    assert data["head_after"] == "PI-004"


def test_reserve_endpoint_consecutive_calls_do_not_overlap(client):
    a = client.post(
        "/identifiers/reserve", json={"entity_type": "session", "count": 2}
    ).json()["data"]
    b = client.post(
        "/identifiers/reserve", json={"entity_type": "session", "count": 2}
    ).json()["data"]
    assert set(a["reserved"]).isdisjoint(b["reserved"])


def test_reserve_unknown_type_returns_422(client):
    r = client.post(
        "/identifiers/reserve", json={"entity_type": "charter", "count": 1}
    )
    assert r.status_code == 422, r.json()


def test_reserve_invalid_count_returns_400(client):
    r = client.post(
        "/identifiers/reserve", json={"entity_type": "planning_item", "count": 0}
    )
    assert r.status_code == 400, r.json()


def test_reserve_records_reserved_by(client):
    r = client.post(
        "/identifiers/reserve",
        json={"entity_type": "decision", "count": 1, "reserved_by": "CONV-9"},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["data"]["reserved_by"] == "CONV-9"
