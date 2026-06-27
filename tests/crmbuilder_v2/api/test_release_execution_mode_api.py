"""Release execution_mode API surface — PI-294 (PRJ-051, REQ-331/332).

The automated/manual discriminator round-trips through the REST create/get/patch
endpoints under the ``{data, meta, errors}`` envelope. Gate behaviour is covered
at the access layer (test_release_manual_mode.py); here we lock the API contract.
"""

from __future__ import annotations


def test_create_defaults_automated(client):
    r = client.post("/releases", json={
        "release_title": "A", "release_description": "d"})
    assert r.status_code == 201
    assert r.json()["data"]["release_execution_mode"] == "automated"


def test_create_manual_round_trips(client):
    r = client.post("/releases", json={
        "release_title": "M", "release_description": "d",
        "release_execution_mode": "manual"})
    assert r.status_code == 201
    rel = r.json()["data"]["release_identifier"]
    got = client.get(f"/releases/{rel}").json()["data"]
    assert got["release_execution_mode"] == "manual"


def test_patch_flips_mode(client):
    rel = client.post("/releases", json={
        "release_title": "P", "release_description": "d"}).json()[
        "data"]["release_identifier"]
    r = client.patch(f"/releases/{rel}", json={"release_execution_mode": "manual"})
    assert r.status_code == 200
    assert r.json()["data"]["release_execution_mode"] == "manual"


def test_create_rejects_unknown_mode(client):
    r = client.post("/releases", json={
        "release_title": "X", "release_description": "d",
        "release_execution_mode": "semi"})
    assert r.status_code == 422
