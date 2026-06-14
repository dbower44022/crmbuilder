"""Dedup-rule REST endpoint tests — PRJ-025 PI-189 slice 3.

Exercises the eight ``/dedup-rules`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def test_create_get_list_dedup_rule(client):
    e = _seed_entity(client, "Contact")
    resp = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "Email match",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "block",
            "dedup_rule_normalize": {"email": "lowercase"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    dup = body["data"]["dedup_rule_identifier"]
    assert dup == "DUP-001"
    assert body["data"]["dedup_rule_status"] == "candidate"

    got = client.get(f"/dedup-rules/{dup}")
    assert got.status_code == 200
    assert got.json()["data"]["dedup_rule_match_fields"] == ["email"]

    listed = client.get("/dedup-rules")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/dedup-rules/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "DUP-001"


def test_create_rejects_empty_match_fields(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": [],
            "dedup_rule_on_match": "block",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_bad_on_match(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "explode",
        },
    )
    assert resp.status_code == 422


def test_create_rejects_bad_normalize_token(client):
    e = _seed_entity(client, "E")
    resp = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "block",
            "dedup_rule_normalize": {"email": "shout"},
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_entity(client):
    resp = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": "ENT-999",
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "block",
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    e = _seed_entity(client, "E")
    dup = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "block",
        },
    ).json()["data"]["dedup_rule_identifier"]
    ok = client.patch(
        f"/dedup-rules/{dup}", json={"dedup_rule_status": "confirmed"}
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["dedup_rule_status"] == "confirmed"
    bad = client.patch(
        f"/dedup-rules/{dup}", json={"dedup_rule_status": "candidate"}
    )
    assert bad.status_code == 422


def test_delete_and_restore(client):
    e = _seed_entity(client, "E")
    dup = client.post(
        "/dedup-rules",
        json={
            "dedup_rule_name": "d",
            "dedup_rule_entity": e,
            "dedup_rule_match_fields": ["email"],
            "dedup_rule_on_match": "block",
        },
    ).json()["data"]["dedup_rule_identifier"]
    assert client.delete(f"/dedup-rules/{dup}").status_code == 200
    assert client.get(f"/dedup-rules/{dup}").status_code == 404
    assert client.post(f"/dedup-rules/{dup}/restore").status_code == 200
    assert client.get(f"/dedup-rules/{dup}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/dedup-rules/DUP-404").status_code == 404
