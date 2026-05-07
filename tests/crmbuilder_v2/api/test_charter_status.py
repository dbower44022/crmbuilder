"""Charter and Status endpoints."""

from __future__ import annotations


def test_charter_lifecycle(client):
    # No current charter yet.
    r = client.get("/charter")
    assert r.status_code == 404

    r = client.put("/charter", json={"payload": {"scope": "v1"}})
    assert r.status_code == 200
    assert r.json()["data"]["version"] == 1

    r = client.put("/charter", json={"payload": {"scope": "v2"}})
    assert r.status_code == 200
    assert r.json()["data"]["version"] == 2

    r = client.get("/charter")
    assert r.json()["data"]["version"] == 2

    r = client.get("/charter/versions")
    versions = r.json()["data"]
    assert [v["version"] for v in versions] == [2, 1]

    r = client.get("/charter/versions/1")
    assert r.json()["data"]["payload"]["scope"] == "v1"


def test_status_lifecycle(client):
    r = client.put("/status", json={"payload": {"phase": "Build"}})
    assert r.status_code == 200
    r = client.get("/status")
    assert r.json()["data"]["payload"]["phase"] == "Build"
