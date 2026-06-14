"""Association REST endpoint tests — PRJ-025 PI-189 slice 1.

Exercises the eight ``/associations`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def test_create_get_list_association(client):
    a = _seed_entity(client, "Mentor")
    b = _seed_entity(client, "Mentee")
    resp = client.post(
        "/associations",
        json={
            "association_name": "Mentor assignment",
            "association_source_entity": a,
            "association_target_entity": b,
            "association_cardinality": "many_to_many",
            "association_source_role": "mentor",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    asn = body["data"]["association_identifier"]
    assert asn == "ASN-001"
    assert body["data"]["association_status"] == "candidate"

    got = client.get(f"/associations/{asn}")
    assert got.status_code == 200
    assert got.json()["data"]["association_source_role"] == "mentor"

    listed = client.get("/associations")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/associations/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "ASN-001"


def test_create_rejects_bad_cardinality(client):
    a = _seed_entity(client, "A")
    b = _seed_entity(client, "B")
    resp = client.post(
        "/associations",
        json={
            "association_name": "x",
            "association_source_entity": a,
            "association_target_entity": b,
            "association_cardinality": "nope",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_dead_endpoint(client):
    a = _seed_entity(client, "A")
    resp = client.post(
        "/associations",
        json={
            "association_name": "x",
            "association_source_entity": a,
            "association_target_entity": "ENT-999",
            "association_cardinality": "one_to_one",
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    a = _seed_entity(client, "A")
    b = _seed_entity(client, "B")
    asn = client.post(
        "/associations",
        json={
            "association_name": "x",
            "association_source_entity": a,
            "association_target_entity": b,
            "association_cardinality": "one_to_one",
        },
    ).json()["data"]["association_identifier"]
    ok = client.patch(
        f"/associations/{asn}", json={"association_status": "confirmed"}
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["association_status"] == "confirmed"
    # confirmed -> candidate is rejected (status_transition_handler flat shape).
    bad = client.patch(
        f"/associations/{asn}", json={"association_status": "candidate"}
    )
    assert bad.status_code == 422


def test_delete_and_restore(client):
    a = _seed_entity(client, "A")
    b = _seed_entity(client, "B")
    asn = client.post(
        "/associations",
        json={
            "association_name": "x",
            "association_source_entity": a,
            "association_target_entity": b,
            "association_cardinality": "one_to_one",
        },
    ).json()["data"]["association_identifier"]
    assert client.delete(f"/associations/{asn}").status_code == 200
    assert client.get(f"/associations/{asn}").status_code == 404
    assert (
        client.post(f"/associations/{asn}/restore").status_code == 200
    )
    assert client.get(f"/associations/{asn}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/associations/ASN-404").status_code == 404
