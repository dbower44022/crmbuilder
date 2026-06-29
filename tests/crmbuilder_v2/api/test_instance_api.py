"""Instance REST API tests — PI-186 (PRJ-027).

Exercises the secret boundary end-to-end (REQ-157): a plaintext ``secret`` POST
is stored in the keyring (in-memory fallback for tests) and only the opaque
reference is persisted and returned — the plaintext is never echoed. Also
covers create/get/list/patch/delete/restore and the next-identifier helper.
"""

from __future__ import annotations

import json

import pytest
from crmbuilder_v2 import secrets


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    """Route the keyring at the in-memory fallback for the whole test."""
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def _create(client, **over):
    body = {
        "instance_name": "CBM sandbox",
        "instance_url": "https://sandbox.example.org",
    }
    body.update(over)
    return client.post("/instances", json=body)


def test_create_minimal(client):
    r = _create(client)
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["instance_identifier"] == "INST-001"
    assert data["instance_vendor"] == "espocrm"
    assert data["instance_role"] == "both"
    assert data["instance_secret_ref"] is None


def test_create_with_secret_stores_ref_not_plaintext(client):
    r = _create(
        client,
        instance_auth_method="api_key",
        secret="super-secret-api-key",
    )
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    ref = data["instance_secret_ref"]
    # Persisted value is an opaque keyring reference, never the plaintext.
    assert ref is not None and ref.startswith("crmbuilder:")
    assert secrets.get_secret(ref) == "super-secret-api-key"
    # The plaintext appears nowhere in the response, and no write-only keys leak.
    assert "super-secret-api-key" not in json.dumps(data)
    assert "secret" not in data and "secret_key" not in data


def test_create_hmac_with_both_secrets(client):
    r = _create(
        client,
        instance_auth_method="hmac",
        secret="api-key-val",
        secret_key="hmac-secret-val",
    )
    data = r.json()["data"]
    assert secrets.get_secret(data["instance_secret_ref"]) == "api-key-val"
    assert secrets.get_secret(data["instance_secret_key_ref"]) == "hmac-secret-val"


def test_get_and_next_identifier(client):
    _create(client)
    got = client.get("/instances/INST-001")
    assert got.status_code == 200
    assert got.json()["data"]["instance_name"] == "CBM sandbox"
    nxt = client.get("/instances/next-identifier")
    assert nxt.json()["data"]["next"] == "INST-002"


def test_bad_enum_rejected(client):
    r = _create(client, instance_vendor="hubspot")
    assert r.status_code == 422
    assert r.json()["errors"]


def test_patch_rotates_secret(client):
    data = _create(client, secret="first").json()["data"]
    old_ref = data["instance_secret_ref"]
    assert secrets.get_secret(old_ref) == "first"
    pr = client.patch("/instances/INST-001", json={"secret": "second"})
    assert pr.status_code == 200, pr.text
    new_ref = pr.json()["data"]["instance_secret_ref"]
    assert new_ref != old_ref
    assert secrets.get_secret(new_ref) == "second"
    # The old secret was removed from the store on rotation.
    with pytest.raises(KeyError):
        secrets.get_secret(old_ref)


def test_put_preserves_secret_when_omitted(client):
    data = _create(client, secret="keepme").json()["data"]
    ref = data["instance_secret_ref"]
    pr = client.put(
        "/instances/INST-001",
        json={
            "instance_name": "renamed",
            "instance_url": "https://sandbox.example.org",
            "instance_role": "source",
        },
    )
    assert pr.status_code == 200, pr.text
    out = pr.json()["data"]
    assert out["instance_name"] == "renamed"
    assert out["instance_role"] == "source"
    # Secret is preserved (same ref) because PUT supplied no new plaintext.
    assert out["instance_secret_ref"] == ref
    assert secrets.get_secret(ref) == "keepme"


def test_list_filter_by_role(client):
    _create(client, instance_role="source")
    _create(client, instance_name="b", instance_url="https://b", instance_role="target")
    all_rows = client.get("/instances").json()["data"]
    assert len(all_rows) == 2
    sources = client.get("/instances", params={"role": "source"}).json()["data"]
    assert len(sources) == 1
    assert sources[0]["instance_role"] == "source"


def test_create_explicit_both_role(client):
    """The ``both`` role is settable explicitly (not just the create default)."""
    r = _create(client, instance_role="both")
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    assert data["instance_role"] == "both"
    # And it reads back identically through GET.
    got = client.get("/instances/INST-001")
    assert got.json()["data"]["instance_role"] == "both"


def test_patch_role_to_both(client):
    """A source instance can be re-roled to ``both`` via PATCH."""
    _create(client, instance_role="source")
    pr = client.patch("/instances/INST-001", json={"instance_role": "both"})
    assert pr.status_code == 200, pr.text
    assert pr.json()["data"]["instance_role"] == "both"


def test_put_role_to_both(client):
    """PUT accepts ``both`` as the replacement role."""
    _create(client, instance_role="target")
    pr = client.put(
        "/instances/INST-001",
        json={
            "instance_name": "CBM sandbox",
            "instance_url": "https://sandbox.example.org",
            "instance_role": "both",
        },
    )
    assert pr.status_code == 200, pr.text
    assert pr.json()["data"]["instance_role"] == "both"


def test_list_filter_by_both_role(client):
    """The role filter resolves ``both`` distinctly from source/target."""
    _create(client, instance_role="both")
    _create(client, instance_name="b", instance_url="https://b", instance_role="source")
    both = client.get("/instances", params={"role": "both"}).json()["data"]
    assert len(both) == 1
    assert both[0]["instance_role"] == "both"


def test_bad_role_rejected(client):
    """An unknown role value returns a 422 validation response on the field."""
    r = _create(client, instance_role="mirror")
    assert r.status_code == 422
    errors = r.json()["errors"]
    assert errors
    assert any(e.get("field") == "instance_role" for e in errors)


def test_patch_bad_role_rejected(client):
    """PATCH rejects an unknown role with the same field-level validation."""
    _create(client, instance_role="both")
    r = client.patch("/instances/INST-001", json={"instance_role": "mirror"})
    assert r.status_code == 422
    assert any(
        e.get("field") == "instance_role" for e in r.json()["errors"]
    )


def test_delete_and_restore(client):
    _create(client)
    assert client.delete("/instances/INST-001").status_code == 200
    assert client.get("/instances/INST-001").status_code == 404
    assert client.post("/instances/INST-001/restore").status_code == 200
    assert client.get("/instances/INST-001").status_code == 200


def test_get_missing_404(client):
    r = client.get("/instances/INST-404")
    assert r.status_code == 404
