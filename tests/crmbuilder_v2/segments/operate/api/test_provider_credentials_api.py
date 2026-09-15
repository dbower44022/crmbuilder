"""Provider-credential API tests — PI-419 (REQ-522).

The token never comes back; the store is exercised in memory; the live
catalog endpoints are driven through a faked provider client; and the admin
gate is asserted with auth on (viewer 403, owner 200).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api import principal_middleware, scope_middleware
from crmbuilder_v2.api.routers import provider_credentials as router_module
from crmbuilder_v2.deploy.errors import ProviderError


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def test_put_get_list_delete_never_echo_token(client):
    r = client.put(
        "/provider-credentials/digitalocean",
        json={"token": "dop_v1_secret", "label": "CRMBuilder DO"},
    )
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body == {
        "provider": "digitalocean", "label": "CRMBuilder DO", "configured": True,
        "created_at": body["created_at"], "updated_at": body["updated_at"],
    }
    assert "dop_v1_secret" not in r.text and "crmbuilder:" not in r.text

    with session_scope() as s:
        from crmbuilder_v2.access.repositories import provider_credentials as repo
        ref = repo.get_provider_credential(s, "digitalocean")["token_ref"]
    assert secrets.is_ref(ref)
    assert secrets.get_secret(ref) == "dop_v1_secret"

    # Replacing rotates the secret and drops the old one.
    r = client.put("/provider-credentials/digitalocean", json={"token": "dop_v1_new"})
    assert r.status_code == 200
    with session_scope() as s:
        new_ref = repo.get_provider_credential(s, "digitalocean")["token_ref"]
    assert new_ref != ref
    assert secrets.get_secret(new_ref) == "dop_v1_new"
    with pytest.raises(KeyError):
        secrets.get_secret(ref)

    listed = client.get("/provider-credentials").json()["data"]
    assert [c["provider"] for c in listed] == ["digitalocean"]
    assert client.get("/provider-credentials/digitalocean").status_code == 200
    assert client.get("/provider-credentials/cloudflare").status_code == 404

    assert client.delete("/provider-credentials/digitalocean").status_code == 200
    assert client.get("/provider-credentials/digitalocean").status_code == 404
    with pytest.raises(KeyError):
        secrets.get_secret(new_ref)


def test_validation_errors(client):
    assert client.put("/provider-credentials/aws", json={"token": "x"}).status_code == 422
    assert client.put("/provider-credentials/cloudflare", json={"token": "  "}).status_code == 422
    assert client.put("/provider-credentials/cloudflare", json={"nope": 1}).status_code == 422


def test_options_require_a_configured_credential(client):
    r = client.get("/provider-credentials/digitalocean/options")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "missing_provider_credential"


def test_options_and_zones_use_the_stored_token(client, monkeypatch):
    seen = {}

    class FakeDO:
        def __init__(self, token, **_):
            seen["do"] = token

        def list_regions(self):
            return [{"slug": "nyc3", "name": "New York 3"}]

        def list_sizes(self):
            return [{"slug": "s-2vcpu-4gb"}]

        def list_images(self):
            return [{"slug": "ubuntu-24-04-x64"}]

        def list_ssh_keys(self):
            return [{"id": 1, "name": "k", "fingerprint": "aa"}]

    class FakeCF:
        def __init__(self, token, **_):
            seen["cf"] = token

        def list_zones(self):
            return [{"id": "z1", "name": "example.org"}]

    monkeypatch.setattr(router_module, "DigitalOceanClient", FakeDO)
    monkeypatch.setattr(router_module, "CloudflareClient", FakeCF)
    client.put("/provider-credentials/digitalocean", json={"token": "do-tok"})
    client.put("/provider-credentials/cloudflare", json={"token": "cf-tok"})

    opts = client.get("/provider-credentials/digitalocean/options")
    assert opts.status_code == 200, opts.text
    assert seen["do"] == "do-tok"
    assert set(opts.json()["data"]) == {"regions", "sizes", "images", "ssh_keys"}

    zones = client.get("/provider-credentials/cloudflare/zones")
    assert zones.status_code == 200
    assert seen["cf"] == "cf-tok"
    assert zones.json()["data"] == [{"id": "z1", "name": "example.org"}]


def test_provider_failure_is_a_422_not_a_500(client, monkeypatch):
    class BadDO:
        def __init__(self, token, **_):
            pass

        def list_regions(self):
            raise ProviderError("digitalocean", "Unable to authenticate you", status=401)

    monkeypatch.setattr(router_module, "DigitalOceanClient", BadDO)
    client.put("/provider-credentials/digitalocean", json={"token": "bad"})
    r = client.get("/provider-credentials/digitalocean/options")
    assert r.status_code == 422
    err = r.json()["errors"][0]
    assert err["code"] == "provider_error"
    assert "Unable to authenticate you" in err["message"]


class _Settings:
    def __init__(self, on: bool) -> None:
        self.principal_auth_enabled = on
        self.engagement_scoping_enabled = True


def test_admin_only_when_auth_on(client, monkeypatch):
    stub = lambda: _Settings(True)  # noqa: E731
    monkeypatch.setattr(principal_middleware, "get_settings", stub)
    monkeypatch.setattr(scope_middleware, "get_settings", stub)
    monkeypatch.setattr(rbac, "get_settings", stub)
    with session_scope() as s:
        viewer = P.create_principal(s, kind="human", display_name="V", identity="v@x.com")
        P.assign_role(s, principal_id=viewer.principal_id, engagement_id="ENG-001", role="viewer")
        vtok = P.mint_token(s, principal_id=viewer.principal_id)
        owner = P.create_principal(s, kind="human", display_name="O", identity="o@x.com")
        P.assign_role(s, principal_id=owner.principal_id, engagement_id="ENG-001", role="owner")
        otok = P.mint_token(s, principal_id=owner.principal_id)

    denied = client.get(
        "/provider-credentials", headers={"Authorization": f"Bearer {vtok.plaintext}"}
    )
    assert denied.status_code == 403
    denied = client.put(
        "/provider-credentials/cloudflare", json={"token": "x"},
        headers={"Authorization": f"Bearer {vtok.plaintext}"},
    )
    assert denied.status_code == 403
    allowed = client.get(
        "/provider-credentials", headers={"Authorization": f"Bearer {otok.plaintext}"}
    )
    assert allowed.status_code == 200


def test_put_with_the_encrypted_store_on_sqlite(client, monkeypatch):
    """PI-419 live-proof finding: storing the token must not nest a second
    write transaction inside the request's own — on SQLite that deadlocks
    until the busy timeout and surfaces as a 500 ``database is locked``."""
    from crmbuilder_v2.config import reset_settings_cache
    from cryptography.fernet import Fernet

    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    monkeypatch.setenv("CRMBUILDER_V2_SECRET_KEY", Fernet.generate_key().decode())
    reset_settings_cache()
    try:
        assert secrets.store_available()
        r = client.put("/provider-credentials/digitalocean", json={"token": "dop_v1_first"})
        assert r.status_code == 200, r.text
        r = client.put("/provider-credentials/digitalocean", json={"token": "dop_v1_second"})
        assert r.status_code == 200, r.text
        with session_scope() as s:
            from crmbuilder_v2.access.repositories import provider_credentials as repo
            ref = repo.get_provider_credential(s, "digitalocean")["token_ref"]
        assert secrets.get_secret(ref) == "dop_v1_second"
    finally:
        reset_settings_cache()
