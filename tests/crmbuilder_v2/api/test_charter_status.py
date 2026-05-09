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


def test_charter_make_version_current(client):
    client.put("/charter", json={"payload": {"scope": "v1"}})
    client.put("/charter", json={"payload": {"scope": "v2"}})
    r = client.patch("/charter/versions/1/make-current")
    assert r.status_code == 200
    assert r.json()["data"]["version"] == 1
    r = client.get("/charter")
    assert r.json()["data"]["version"] == 1
    versions = client.get("/charter/versions").json()["data"]
    by_version = {v["version"]: v for v in versions}
    assert by_version[1]["is_current"] is True
    assert by_version[2]["is_current"] is False


def test_charter_make_version_current_unknown(client):
    client.put("/charter", json={"payload": {"scope": "v1"}})
    r = client.patch("/charter/versions/99/make-current")
    assert r.status_code == 404


def test_status_make_version_current(client):
    client.put("/status", json={"payload": {"phase": "Plan"}})
    client.put("/status", json={"payload": {"phase": "Build"}})
    r = client.patch("/status/versions/1/make-current")
    assert r.status_code == 200
    r = client.get("/status")
    assert r.json()["data"]["version"] == 1
