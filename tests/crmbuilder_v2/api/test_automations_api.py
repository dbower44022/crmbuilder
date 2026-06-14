"""Automation REST endpoint tests — PRJ-025 PI-189 slice 2.

Exercises the eight ``/automations`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations

_ACTIONS = [{"type": "set_field", "field": "stage", "value": "won"}]
_COND = {"field": "amount", "op": "gte", "value": 1000}


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def test_create_get_list_automation(client):
    e = _seed_entity(client, "Opportunity")
    resp = client.post(
        "/automations",
        json={
            "automation_name": "Mark won",
            "automation_entity": e,
            "automation_trigger": "on_update",
            "automation_actions": _ACTIONS,
            "automation_condition": _COND,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    aut = body["data"]["automation_identifier"]
    assert aut == "AUT-001"
    assert body["data"]["automation_status"] == "candidate"

    got = client.get(f"/automations/{aut}")
    assert got.status_code == 200
    assert got.json()["data"]["automation_actions"] == _ACTIONS

    listed = client.get("/automations")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/automations/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "AUT-001"


def test_create_rejects_bad_trigger(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "on_login",
            "automation_actions": _ACTIONS,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_bad_action_type(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "manual",
            "automation_actions": [{"type": "launch"}],
        },
    )
    assert resp.status_code == 422


def test_create_rejects_empty_actions(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "manual",
            "automation_actions": [],
        },
    )
    assert resp.status_code == 422


def test_create_rejects_malformed_condition(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "manual",
            "automation_actions": _ACTIONS,
            "automation_condition": {"op": "eq", "value": 1},
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_entity(client):
    resp = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": "ENT-999",
            "automation_trigger": "manual",
            "automation_actions": _ACTIONS,
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    e = _seed_entity(client, "E")
    aut = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "manual",
            "automation_actions": _ACTIONS,
        },
    ).json()["data"]["automation_identifier"]
    ok = client.patch(
        f"/automations/{aut}", json={"automation_status": "confirmed"}
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["automation_status"] == "confirmed"
    bad = client.patch(
        f"/automations/{aut}", json={"automation_status": "candidate"}
    )
    assert bad.status_code == 422


def test_delete_and_restore(client):
    e = _seed_entity(client, "E")
    aut = client.post(
        "/automations",
        json={
            "automation_name": "a",
            "automation_entity": e,
            "automation_trigger": "manual",
            "automation_actions": _ACTIONS,
        },
    ).json()["data"]["automation_identifier"]
    assert client.delete(f"/automations/{aut}").status_code == 200
    assert client.get(f"/automations/{aut}").status_code == 404
    assert client.post(f"/automations/{aut}/restore").status_code == 200
    assert client.get(f"/automations/{aut}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/automations/AUT-404").status_code == 404
