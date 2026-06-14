"""View REST endpoint tests — PRJ-025 PI-189 slice 2.

Exercises the eight ``/views`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations

_FILTER = {"any": [{"field": "stage", "op": "eq", "value": "open"}]}


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def test_create_get_list_view(client):
    e = _seed_entity(client, "Opportunity")
    resp = client.post(
        "/views",
        json={
            "view_name": "Open opps",
            "view_entity": e,
            "view_columns": ["name", "stage"],
            "view_filter": _FILTER,
            "view_sort_field": "amount",
            "view_sort_direction": "desc",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    vew = body["data"]["view_identifier"]
    assert vew == "VEW-001"
    assert body["data"]["view_status"] == "candidate"

    got = client.get(f"/views/{vew}")
    assert got.status_code == 200
    assert got.json()["data"]["view_columns"] == ["name", "stage"]

    listed = client.get("/views")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/views/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "VEW-001"


def test_create_rejects_empty_columns(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/views",
        json={"view_name": "v", "view_entity": e, "view_columns": []},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_bad_sort_direction(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/views",
        json={
            "view_name": "v",
            "view_entity": e,
            "view_columns": ["name"],
            "view_sort_direction": "sideways",
        },
    )
    assert resp.status_code == 422


def test_create_rejects_malformed_filter(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/views",
        json={
            "view_name": "v",
            "view_entity": e,
            "view_columns": ["name"],
            "view_filter": {"all": []},
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_entity(client):
    resp = client.post(
        "/views",
        json={
            "view_name": "v",
            "view_entity": "ENT-999",
            "view_columns": ["name"],
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    e = _seed_entity(client, "E")
    vew = client.post(
        "/views",
        json={"view_name": "v", "view_entity": e, "view_columns": ["name"]},
    ).json()["data"]["view_identifier"]
    ok = client.patch(f"/views/{vew}", json={"view_status": "confirmed"})
    assert ok.status_code == 200
    assert ok.json()["data"]["view_status"] == "confirmed"
    bad = client.patch(f"/views/{vew}", json={"view_status": "candidate"})
    assert bad.status_code == 422


def test_delete_and_restore(client):
    e = _seed_entity(client, "E")
    vew = client.post(
        "/views",
        json={"view_name": "v", "view_entity": e, "view_columns": ["name"]},
    ).json()["data"]["view_identifier"]
    assert client.delete(f"/views/{vew}").status_code == 200
    assert client.get(f"/views/{vew}").status_code == 404
    assert client.post(f"/views/{vew}/restore").status_code == 200
    assert client.get(f"/views/{vew}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/views/VEW-404").status_code == 404
