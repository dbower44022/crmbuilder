"""Message-template REST endpoint tests — PRJ-025 PI-189 slice 3.

Exercises the eight ``/message-templates`` routes through the TestClient, the
``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations


def _seed_entity(client, name: str) -> str:
    resp = client.post(
        "/entities", json={"entity_name": name, "entity_description": "seed"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["entity_identifier"]


def test_create_get_list_message_template(client):
    e = _seed_entity(client, "Contact")
    resp = client.post(
        "/message-templates",
        json={
            "message_template_name": "Welcome",
            "message_template_body": "Hello {{name}}",
            "message_template_entity": e,
            "message_template_channel": "email",
            "message_template_subject": "Welcome {{name}}",
            "message_template_merge_fields": ["name"],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    msg = body["data"]["message_template_identifier"]
    assert msg == "MSG-001"
    assert body["data"]["message_template_status"] == "candidate"

    got = client.get(f"/message-templates/{msg}")
    assert got.status_code == 200
    assert got.json()["data"]["message_template_body"] == "Hello {{name}}"

    listed = client.get("/message-templates")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_create_minimal_body_only(client):
    resp = client.post(
        "/message-templates",
        json={"message_template_name": "t", "message_template_body": "b"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["message_template_entity"] is None
    assert data["message_template_channel"] is None


def test_next_identifier(client):
    resp = client.get("/message-templates/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "MSG-001"


def test_create_rejects_empty_body(client):
    resp = client.post(
        "/message-templates",
        json={"message_template_name": "t", "message_template_body": "  "},
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_bad_channel(client):
    resp = client.post(
        "/message-templates",
        json={
            "message_template_name": "t",
            "message_template_body": "b",
            "message_template_channel": "carrier_pigeon",
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_entity_when_present(client):
    resp = client.post(
        "/message-templates",
        json={
            "message_template_name": "t",
            "message_template_body": "b",
            "message_template_entity": "ENT-999",
        },
    )
    assert resp.status_code == 422


def test_patch_status_transition_and_invalid(client):
    msg = client.post(
        "/message-templates",
        json={"message_template_name": "t", "message_template_body": "b"},
    ).json()["data"]["message_template_identifier"]
    ok = client.patch(
        f"/message-templates/{msg}",
        json={"message_template_status": "confirmed"},
    )
    assert ok.status_code == 200
    assert ok.json()["data"]["message_template_status"] == "confirmed"
    bad = client.patch(
        f"/message-templates/{msg}",
        json={"message_template_status": "candidate"},
    )
    assert bad.status_code == 422


def test_delete_and_restore(client):
    msg = client.post(
        "/message-templates",
        json={"message_template_name": "t", "message_template_body": "b"},
    ).json()["data"]["message_template_identifier"]
    assert client.delete(f"/message-templates/{msg}").status_code == 200
    assert client.get(f"/message-templates/{msg}").status_code == 404
    assert client.post(f"/message-templates/{msg}/restore").status_code == 200
    assert client.get(f"/message-templates/{msg}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/message-templates/MSG-404").status_code == 404
