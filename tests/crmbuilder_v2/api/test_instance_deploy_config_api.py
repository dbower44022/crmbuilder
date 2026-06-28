"""Instance deploy-config API tests — PI-201 (REQ-172, PRJ-027).

Exercises GET/PUT /instances/{id}/deploy-config: the round-trip, the keyring
secret boundary (password auth + db root password become opaque refs, key auth
stores the path inline), partial updates, and the 404 / empty cases.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def client(v2_env):
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


def _instance(client) -> str:
    body = {
        "instance_name": "prod", "instance_url": "https://crm.example.org",
        "instance_role": "target", "secret": "api-key",
    }
    return client.post("/instances", json=body).json()["data"][
        "instance_identifier"
    ]


def test_put_get_roundtrip_and_secret_boundary(client):
    iid = _instance(client)
    r = client.put(f"/instances/{iid}/deploy-config", json={
        "scenario": "self_hosted", "ssh_host": "147.182.135.50", "ssh_port": 22,
        "ssh_username": "root", "ssh_auth_type": "password",
        "ssh_credential": "sshpass", "domain": "crm.example.org",
        "letsencrypt_email": "ops@example.org", "db_root_password": "dbpass",
        "current_espocrm_version": "9.3.4",
    })
    assert r.status_code == 200, r.text
    cfg = r.json()["data"]
    assert cfg["ssh_host"] == "147.182.135.50"
    assert cfg["domain"] == "crm.example.org"
    assert cfg["current_espocrm_version"] == "9.3.4"
    # Secrets are keyring refs, never the plaintext, and the write-only inputs
    # are not echoed back.
    assert cfg["ssh_credential_ref"].startswith(secrets.REF_PREFIX)
    assert cfg["db_root_password_ref"].startswith(secrets.REF_PREFIX)
    assert "ssh_credential" not in cfg
    assert "db_root_password" not in cfg
    # The stored refs resolve to the original secrets.
    assert secrets.get_secret(cfg["ssh_credential_ref"]) == "sshpass"
    assert secrets.get_secret(cfg["db_root_password_ref"]) == "dbpass"
    # GET returns the same config.
    got = client.get(f"/instances/{iid}/deploy-config").json()["data"]
    assert got["ssh_host"] == "147.182.135.50"


def test_key_auth_stores_path_inline(client):
    iid = _instance(client)
    r = client.put(f"/instances/{iid}/deploy-config", json={
        "ssh_auth_type": "key", "ssh_credential": "/home/u/.ssh/id_ed25519",
        "ssh_host": "h", "ssh_username": "root", "domain": "d",
    })
    cfg = r.json()["data"]
    # A key path is stored inline (not keyring) — paths are not sensitive.
    assert cfg["ssh_credential_ref"] == "/home/u/.ssh/id_ed25519"
    assert not cfg["ssh_credential_ref"].startswith(secrets.REF_PREFIX)


def test_partial_update_preserves_unchanged(client):
    iid = _instance(client)
    client.put(f"/instances/{iid}/deploy-config", json={
        "ssh_host": "1.2.3.4", "domain": "d", "current_espocrm_version": "9.3.4",
    })
    # A later partial PUT touches only the version.
    client.put(f"/instances/{iid}/deploy-config", json={
        "current_espocrm_version": "9.3.6",
    })
    cfg = client.get(f"/instances/{iid}/deploy-config").json()["data"]
    assert cfg["current_espocrm_version"] == "9.3.6"
    assert cfg["ssh_host"] == "1.2.3.4"  # preserved


def test_get_none_and_404(client):
    iid = _instance(client)
    assert client.get(f"/instances/{iid}/deploy-config").json()["data"] is None
    assert client.get("/instances/INST-999/deploy-config").status_code == 404
    assert client.put(
        "/instances/INST-999/deploy-config", json={"domain": "d"}
    ).status_code == 404


def test_bad_ssh_auth_type_rejected(client):
    iid = _instance(client)
    r = client.put(f"/instances/{iid}/deploy-config", json={
        "ssh_auth_type": "telnet", "ssh_host": "h",
    })
    assert r.status_code == 422
