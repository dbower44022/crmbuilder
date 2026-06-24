"""Field-visibility-rule REST endpoint tests — PI-051 / REQ-128 (DEC-698).

Exercises the eight ``/field-visibility-rules`` routes through the TestClient,
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
    f = _seed_field(client, "salaryBand")
    resp = client.post(
        "/field-visibility-rules",
        json={
            "field_visibility_rule_name": "Mentor — salaryBand hidden",
            "field_visibility_rule_role": r,
            "field_visibility_rule_target_field": f,
            "field_visibility_rule_visible": False,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    fvr = body["data"]["field_visibility_rule_identifier"]
    assert fvr == "FVR-001"
    assert body["data"]["field_visibility_rule_status"] == "candidate"
    assert body["data"]["field_visibility_rule_deployment_status"] == "pending"
    assert body["data"]["field_visibility_rule_visible"] is False

    got = client.get(f"/field-visibility-rules/{fvr}")
    assert got.status_code == 200
    assert got.json()["data"]["field_visibility_rule_visible"] is False

    listed = client.get("/field-visibility-rules")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/field-visibility-rules/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "FVR-001"


def test_create_rejects_missing_visible(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    # ``field_visibility_rule_visible`` is required (no default).
    resp = client.post(
        "/field-visibility-rules",
        json={
            "field_visibility_rule_name": "x",
            "field_visibility_rule_role": r,
            "field_visibility_rule_target_field": f,
        },
    )
    assert resp.status_code == 422


def test_create_rejects_dead_role(client):
    f = _seed_field(client, "fld")
    resp = client.post(
        "/field-visibility-rules",
        json={
            "field_visibility_rule_name": "x",
            "field_visibility_rule_role": "ROL-999",
            "field_visibility_rule_target_field": f,
            "field_visibility_rule_visible": True,
        },
    )
    assert resp.status_code == 422


def test_patch_status_and_deploy_gate(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    fvr = client.post(
        "/field-visibility-rules",
        json={
            "field_visibility_rule_name": "x",
            "field_visibility_rule_role": r,
            "field_visibility_rule_target_field": f,
            "field_visibility_rule_visible": True,
        },
    ).json()["data"]["field_visibility_rule_identifier"]

    bad = client.patch(
        f"/field-visibility-rules/{fvr}",
        json={"field_visibility_rule_deployment_status": "not_supported"},
    )
    assert bad.status_code == 422

    ok = client.patch(
        f"/field-visibility-rules/{fvr}",
        json={"field_visibility_rule_status": "confirmed"},
    )
    assert ok.status_code == 200
    deployed = client.patch(
        f"/field-visibility-rules/{fvr}",
        json={"field_visibility_rule_deployment_status": "not_supported"},
    )
    assert deployed.status_code == 200
    assert (
        deployed.json()["data"]["field_visibility_rule_deployment_status"]
        == "not_supported"
    )


def test_delete_and_restore(client):
    r = _seed_role(client, "Mentor")
    f = _seed_field(client, "fld")
    fvr = client.post(
        "/field-visibility-rules",
        json={
            "field_visibility_rule_name": "x",
            "field_visibility_rule_role": r,
            "field_visibility_rule_target_field": f,
            "field_visibility_rule_visible": True,
        },
    ).json()["data"]["field_visibility_rule_identifier"]
    assert client.delete(f"/field-visibility-rules/{fvr}").status_code == 200
    assert client.get(f"/field-visibility-rules/{fvr}").status_code == 404
    assert (
        client.post(f"/field-visibility-rules/{fvr}/restore").status_code
        == 200
    )
    assert client.get(f"/field-visibility-rules/{fvr}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/field-visibility-rules/FVR-404").status_code == 404
