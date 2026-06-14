"""Rule REST endpoint tests — PRJ-025 PI-189 slice 2.

Exercises the eight ``/rules`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations

_COND = {"field": "stage", "op": "eq", "value": "won"}


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def _seed_field(client, entity_id: str, name: str) -> str:
    resp = client.post(
        "/fields",
        json={
            "field_belongs_to_entity_identifier": entity_id,
            "field_name": name,
            "field_description": "seed",
            "field_type": "text",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["field_identifier"]


def test_create_get_list_rule(client):
    e = _seed_entity(client, "Opportunity")
    f = _seed_field(client, e, "stage")
    resp = client.post(
        "/rules",
        json={
            "rule_name": "Stage required",
            "rule_subject_type": "field",
            "rule_subject_identifier": f,
            "rule_effect": "required_when",
            "rule_condition": _COND,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    rul = body["data"]["rule_identifier"]
    assert rul == "RUL-001"
    assert body["data"]["rule_status"] == "candidate"

    got = client.get(f"/rules/{rul}")
    assert got.status_code == 200
    assert got.json()["data"]["rule_condition"] == _COND

    listed = client.get("/rules")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/rules/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "RUL-001"


def test_create_rejects_bad_effect(client):
    e = _seed_entity(client, "E")
    f = _seed_field(client, e, "fld")
    resp = client.post(
        "/rules",
        json={
            "rule_name": "x",
            "rule_subject_type": "field",
            "rule_subject_identifier": f,
            "rule_effect": "nope_when",
            "rule_condition": _COND,
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_malformed_condition(client):
    e = _seed_entity(client, "E")
    f = _seed_field(client, e, "fld")
    resp = client.post(
        "/rules",
        json={
            "rule_name": "x",
            "rule_subject_type": "field",
            "rule_subject_identifier": f,
            "rule_effect": "required_when",
            "rule_condition": {"all": []},
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_subject(client):
    resp = client.post(
        "/rules",
        json={
            "rule_name": "x",
            "rule_subject_type": "field",
            "rule_subject_identifier": "FLD-999",
            "rule_effect": "required_when",
            "rule_condition": _COND,
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    e = _seed_entity(client, "E")
    f = _seed_field(client, e, "fld")
    rul = client.post(
        "/rules",
        json={
            "rule_name": "x",
            "rule_subject_type": "field",
            "rule_subject_identifier": f,
            "rule_effect": "required_when",
            "rule_condition": _COND,
        },
    ).json()["data"]["rule_identifier"]
    ok = client.patch(f"/rules/{rul}", json={"rule_status": "confirmed"})
    assert ok.status_code == 200
    assert ok.json()["data"]["rule_status"] == "confirmed"
    bad = client.patch(f"/rules/{rul}", json={"rule_status": "candidate"})
    assert bad.status_code == 422


def test_delete_and_restore(client):
    e = _seed_entity(client, "E")
    f = _seed_field(client, e, "fld")
    rul = client.post(
        "/rules",
        json={
            "rule_name": "x",
            "rule_subject_type": "field",
            "rule_subject_identifier": f,
            "rule_effect": "required_when",
            "rule_condition": _COND,
        },
    ).json()["data"]["rule_identifier"]
    assert client.delete(f"/rules/{rul}").status_code == 200
    assert client.get(f"/rules/{rul}").status_code == 404
    assert client.post(f"/rules/{rul}/restore").status_code == 200
    assert client.get(f"/rules/{rul}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/rules/RUL-404").status_code == 404
