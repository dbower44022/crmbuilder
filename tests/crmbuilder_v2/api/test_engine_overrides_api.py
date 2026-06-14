"""Engine-override REST endpoint tests — PRJ-025 PI-189 slice 1.

Exercises the eight ``/engine-overrides`` routes through the TestClient, the
``{data, meta, errors}`` envelope, JSON value round-trip, and the key
validation surfaces (bad engine, uniqueness conflict).
"""

from __future__ import annotations


def test_create_get_list_override(client):
    resp = client.post(
        "/engine-overrides",
        json={
            "override_target_engine": "espocrm",
            "override_subject_type": "field",
            "override_subject_identifier": "FLD-001",
            "override_attribute": "formula",
            "override_value": {"expr": "concat(a, b)"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["errors"] is None
    ovr = body["data"]["override_identifier"]
    assert ovr == "OVR-001"
    assert body["data"]["override_value"] == {"expr": "concat(a, b)"}

    got = client.get(f"/engine-overrides/{ovr}")
    assert got.status_code == 200
    assert got.json()["data"]["override_attribute"] == "formula"

    listed = client.get("/engine-overrides?target_engine=espocrm")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1


def test_next_identifier(client):
    resp = client.get("/engine-overrides/next-identifier")
    assert resp.status_code == 200
    assert resp.json()["data"]["next"] == "OVR-001"


def test_create_rejects_bad_engine(client):
    resp = client.post(
        "/engine-overrides",
        json={
            "override_target_engine": "salesforce",
            "override_subject_type": "entity",
            "override_subject_identifier": "ENT-001",
            "override_attribute": "internal_name",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["errors"] is not None


def test_create_rejects_bad_subject_type(client):
    resp = client.post(
        "/engine-overrides",
        json={
            "override_target_engine": "espocrm",
            "override_subject_type": "domain",
            "override_subject_identifier": "DOM-001",
            "override_attribute": "x",
        },
    )
    assert resp.status_code == 422


def test_uniqueness_conflict_is_409(client):
    payload = {
        "override_target_engine": "espocrm",
        "override_subject_type": "entity",
        "override_subject_identifier": "ENT-001",
        "override_attribute": "internal_name",
    }
    assert client.post("/engine-overrides", json=payload).status_code == 201
    dup = client.post("/engine-overrides", json={**payload, "override_value": "x"})
    assert dup.status_code == 409


def test_patch_value_and_notes(client):
    ovr = client.post(
        "/engine-overrides",
        json={
            "override_target_engine": "espocrm",
            "override_subject_type": "entity",
            "override_subject_identifier": "ENT-001",
            "override_attribute": "internal_name",
        },
    ).json()["data"]["override_identifier"]
    patched = client.patch(
        f"/engine-overrides/{ovr}",
        json={"override_value": "CMentor", "override_notes": "pin"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["override_value"] == "CMentor"
    assert patched.json()["data"]["override_notes"] == "pin"


def test_delete_and_restore(client):
    ovr = client.post(
        "/engine-overrides",
        json={
            "override_target_engine": "espocrm",
            "override_subject_type": "entity",
            "override_subject_identifier": "ENT-001",
            "override_attribute": "internal_name",
        },
    ).json()["data"]["override_identifier"]
    assert client.delete(f"/engine-overrides/{ovr}").status_code == 200
    assert client.get(f"/engine-overrides/{ovr}").status_code == 404
    assert client.post(f"/engine-overrides/{ovr}/restore").status_code == 200
    assert client.get(f"/engine-overrides/{ovr}").status_code == 200


def test_get_missing_is_404(client):
    assert client.get("/engine-overrides/OVR-404").status_code == 404
