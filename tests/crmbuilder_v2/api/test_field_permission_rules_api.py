"""Field-permission-rule REST endpoint tests — PI-051 / REQ-129 (DEC-698).

Exercises the eight ``/field-permission-rules`` routes through the TestClient,
the ``{data, meta, errors}`` envelope, and the key validation surfaces.
"""

from __future__ import annotations


def _seed_role(client, name: str) -> str:
    resp = client.post("/roles", json={"role_name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["role_identifier"]


def _seed_field(client, name: str) -> str:
    e = client.post(
        "/entities",
        json={"entity_name": f"Ent-{name}", "entity_description": "seed"},
    )
    assert e.status_code == 201, e.text
    eid = e.json()["data"]["entity_identifier"]
    f = client.post(
        "/fields",
        json={
            "field_belongs_to_entity_identifier": eid,
            "field_name": name,
            "field_description": "seed",
            "field_type": "text",
        },
    )
    assert f.status_code == 201, f.text
    return f.json()["data"]["field_identifier"]


def test_create_get_list(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "backgroundCheck")
    resp = client.post(
        "/field-permission-rules",
        json={
            "field_permission_rule_name": "Mentor — backgroundCheck",
            "field_permission_rule_role": r,
            "field_permission_rule_target_field": f,
            "field_permission_rule_permission_level": "read_only",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    fpr = body["data"]["field_permission_rule_identifier"]
    assert fpr == "FPR-001"
    assert body["data"]["field_permission_rule_status"] == "candidate"
    assert body["data"]["field_permission_rule_deployment_status"] == "pending"

    got = client.get(f"/field-permission-rules/{fpr}")
    assert got.status_code == 200
    assert (
        got.json()["data"]["field_permission_rule_permission_level"]
        == "read_only"
    )

    listed = client.get("/field-permission-rules")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/field-permission-rules/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "FPR-001"


def test_create_rejects_bad_permission_level(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    resp = client.post(
        "/field-permission-rules",
        json={
            "field_permission_rule_name": "x",
            "field_permission_rule_role": r,
            "field_permission_rule_target_field": f,
            "field_permission_rule_permission_level": "write_only",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_dead_field(client):
    r = _seed_role(client, "Mentor")
    resp = client.post(
        "/field-permission-rules",
        json={
            "field_permission_rule_name": "x",
            "field_permission_rule_role": r,
            "field_permission_rule_target_field": "FLD-999",
            "field_permission_rule_permission_level": "read_only",
        },
    )
    assert resp.status_code == 422


def test_patch_status_and_deploy_gate(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    fpr = client.post(
        "/field-permission-rules",
        json={
            "field_permission_rule_name": "x",
            "field_permission_rule_role": r,
            "field_permission_rule_target_field": f,
            "field_permission_rule_permission_level": "read_only",
        },
    ).json()["data"]["field_permission_rule_identifier"]

    # deploy-before-confirmed is rejected.
    bad = client.patch(
        f"/field-permission-rules/{fpr}",
        json={"field_permission_rule_deployment_status": "deployed"},
    )
    assert bad.status_code == 422

    ok = client.patch(
        f"/field-permission-rules/{fpr}",
        json={"field_permission_rule_status": "confirmed"},
    )
    assert ok.status_code == 200
    deployed = client.patch(
        f"/field-permission-rules/{fpr}",
        json={"field_permission_rule_deployment_status": "deployed"},
    )
    assert deployed.status_code == 200
    assert (
        deployed.json()["data"]["field_permission_rule_deployment_status"]
        == "deployed"
    )


def test_delete_and_restore(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    fpr = client.post(
        "/field-permission-rules",
        json={
            "field_permission_rule_name": "x",
            "field_permission_rule_role": r,
            "field_permission_rule_target_field": f,
            "field_permission_rule_permission_level": "read_only",
        },
    ).json()["data"]["field_permission_rule_identifier"]
    assert client.delete(f"/field-permission-rules/{fpr}").status_code == 200
    assert client.get(f"/field-permission-rules/{fpr}").status_code == 404
    assert (
        client.post(f"/field-permission-rules/{fpr}/restore").status_code
        == 200
    )
    assert client.get(f"/field-permission-rules/{fpr}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/field-permission-rules/FPR-404").status_code == 404
