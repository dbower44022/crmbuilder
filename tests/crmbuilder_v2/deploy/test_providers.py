"""Provider client tests — PI-419 (REQ-522).

Run against a fake ``requests.Session``: no network. Asserts the calls the
runner depends on — the DNS-only A record, the idempotent upserts, the
droplet summary shape, and that provider errors surface as ``ProviderError``
with the provider's own message.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.deploy.errors import ProviderError
from crmbuilder_v2.deploy.providers.cloudflare import CloudflareClient
from crmbuilder_v2.deploy.providers.digitalocean import (
    CRMBUILDER_TAG,
    DigitalOceanClient,
)

from tests.crmbuilder_v2.deploy.fakes import FakeResponse, FakeSession

_DROPLET = {
    "id": 4242,
    "name": "crm.example.org",
    "status": "active",
    "region": {"slug": "nyc3"},
    "size": {"slug": "s-2vcpu-4gb"},
    "tags": ["crmbuilder", "DEP-001"],
    "networks": {"v4": [
        {"type": "private", "ip_address": "10.0.0.5"},
        {"type": "public", "ip_address": "203.0.113.7"},
    ]},
}


def test_do_token_is_a_bearer_header_and_catalog_reads_map():
    session = FakeSession({
        ("GET", "/account"): FakeResponse(200, {"account": {"email": "ops@example.org"}}),
        ("GET", "/regions"): FakeResponse(200, {"regions": [
            {"slug": "nyc3", "name": "New York 3", "available": True},
            {"slug": "old1", "name": "Gone", "available": False},
        ]}),
        ("GET", "/sizes"): FakeResponse(200, {"sizes": [
            {"slug": "s-2vcpu-4gb", "description": "Basic", "memory": 4096, "vcpus": 2,
             "disk": 80, "price_monthly": 24.0, "regions": ["nyc3"], "available": True},
        ]}),
        ("GET", "/images"): FakeResponse(200, {"images": [
            {"slug": "ubuntu-24-04-x64", "name": "24.04 LTS x64", "distribution": "Ubuntu"},
            {"slug": "debian-12-x64", "name": "12 x64", "distribution": "Debian"},
            {"slug": None, "name": "snapshot", "distribution": "Ubuntu"},
        ]}),
        ("GET", "/account/keys"): FakeResponse(200, {"ssh_keys": [
            {"id": 1, "name": "laptop", "fingerprint": "aa:bb"},
        ]}),
    })
    do = DigitalOceanClient("tok-secret", session=session)
    assert session.headers["Authorization"] == "Bearer tok-secret"
    assert do.verify_token()["email"] == "ops@example.org"
    assert do.list_regions() == [{"slug": "nyc3", "name": "New York 3"}]
    assert do.list_sizes()[0]["slug"] == "s-2vcpu-4gb"
    assert [i["slug"] for i in do.list_images()] == ["ubuntu-24-04-x64"]
    assert do.list_ssh_keys() == [{"id": 1, "name": "laptop", "fingerprint": "aa:bb"}]


def test_do_create_droplet_tags_run_and_summarizes():
    session = FakeSession({
        ("POST", "/droplets"): FakeResponse(202, {"droplet": {**_DROPLET, "status": "new", "networks": {"v4": []}}}),
        ("GET", "/droplets/4242"): FakeResponse(200, {"droplet": _DROPLET}),
        ("GET", "/droplets"): FakeResponse(200, {"droplets": [_DROPLET]}),
    })
    do = DigitalOceanClient("t", session=session)
    created = do.create_droplet(
        name="crm.example.org", region="nyc3", size="s-2vcpu-4gb",
        image="ubuntu-24-04-x64", ssh_key_ids=[1, "aa:bb"], tags=["DEP-001"],
    )
    payload = session.calls[0]["json"]
    assert payload["tags"] == sorted({CRMBUILDER_TAG, "DEP-001"})
    assert payload["ssh_keys"] == [1, "aa:bb"]
    assert payload["backups"] is False
    assert created["id"] == 4242 and created["status"] == "new" and created["ip"] is None
    active = do.get_droplet(4242)
    assert active == {
        "id": 4242, "name": "crm.example.org", "status": "active", "ip": "203.0.113.7",
        "region": "nyc3", "size": "s-2vcpu-4gb", "tags": ["crmbuilder", "DEP-001"],
    }
    found = do.find_droplets_by_tag("DEP-001")
    assert session.calls[-1]["params"]["tag_name"] == "DEP-001"
    assert found[0]["ip"] == "203.0.113.7"


def test_do_add_ssh_key_is_idempotent_on_422():
    session = FakeSession({
        ("POST", "/account/keys"): FakeResponse(422, {"id": "unprocessable_entity", "message": "SSH Key is already in use on your account"}),
        ("GET", "/account/keys"): FakeResponse(200, {"ssh_keys": [
            {"id": 7, "name": "crmbuilder-DEP-001", "fingerprint": "cc:dd"},
        ]}),
    })
    do = DigitalOceanClient("t", session=session)
    assert do.add_ssh_key(name="crmbuilder-DEP-001", public_key="ssh-ed25519 AAAA")["id"] == 7


def test_do_errors_carry_provider_message_and_status():
    session = FakeSession({
        ("GET", "/account"): FakeResponse(401, {"id": "Unauthorized", "message": "Unable to authenticate you"}),
    })
    with pytest.raises(ProviderError) as info:
        DigitalOceanClient("bad", session=session).verify_token()
    assert info.value.provider == "digitalocean"
    assert info.value.status == 401
    assert "Unable to authenticate you" in str(info.value)


def test_cf_zones_and_dns_only_create():
    calls = {}

    def _create(params, body):
        calls["create"] = body
        return FakeResponse(200, {"success": True, "result": {"id": "rec1", **body}})

    session = FakeSession({
        ("GET", "/user/tokens/verify"): FakeResponse(200, {"result": {"status": "active"}}),
        ("GET", "/zones"): FakeResponse(200, {"result": [{"id": "z1", "name": "example.org", "status": "active"}]}),
        ("GET", "/zones/z1/dns_records"): FakeResponse(200, {"result": []}),
        ("POST", "/zones/z1/dns_records"): _create,
    })
    cf = CloudflareClient("cf-secret", session=session)
    assert cf.verify_token()["status"] == "active"
    assert cf.list_zones() == [{"id": "z1", "name": "example.org"}]
    rec = cf.upsert_a_record("z1", name="crm.example.org", ip="203.0.113.7")
    assert calls["create"] == {
        "type": "A", "name": "crm.example.org", "content": "203.0.113.7", "ttl": 60, "proxied": False,
    }
    assert rec == {"id": "rec1", "name": "crm.example.org", "type": "A",
                   "content": "203.0.113.7", "ttl": 60, "proxied": False}


def test_cf_upsert_updates_existing_and_skips_when_unchanged():
    existing = {"id": "rec9", "type": "A", "name": "crm.example.org",
                "content": "198.51.100.1", "ttl": 60, "proxied": True}
    patched = {}

    def _patch(params, body):
        patched.update(body)
        return FakeResponse(200, {"result": {**existing, **body}})

    session = FakeSession({
        ("GET", "/zones/z1/dns_records"): FakeResponse(200, {"result": [existing]}),
        ("PATCH", "/zones/z1/dns_records/rec9"): _patch,
    })
    cf = CloudflareClient("t", session=session)
    rec = cf.upsert_a_record("z1", name="crm.example.org", ip="203.0.113.7")
    assert patched["content"] == "203.0.113.7" and patched["proxied"] is False
    assert rec["id"] == "rec9" and rec["proxied"] is False
    # Now unchanged: no write at all.
    session.routes[("GET", "/zones/z1/dns_records")] = FakeResponse(
        200, {"result": [{**existing, "content": "203.0.113.7", "proxied": False}]}
    )
    before = len(session.calls)
    cf.upsert_a_record("z1", name="crm.example.org", ip="203.0.113.7")
    assert [c["method"] for c in session.calls[before:]] == ["GET"]


def test_cf_error_body_is_flattened():
    session = FakeSession({
        ("GET", "/zones"): FakeResponse(403, {"success": False, "errors": [
            {"code": 9109, "message": "Invalid access token"},
        ]}),
    })
    with pytest.raises(ProviderError) as info:
        CloudflareClient("t", session=session).list_zones()
    assert info.value.status == 403
    assert "Invalid access token [9109]" in str(info.value)


def test_transport_failure_is_a_provider_error():
    import requests

    class Boom(FakeSession):
        def request(self, *a, **k):  # type: ignore[override]
            raise requests.exceptions.ConnectionError("dns down")

    with pytest.raises(ProviderError) as info:
        DigitalOceanClient("t", session=Boom()).verify_token()
    assert info.value.status is None and "dns down" in str(info.value)
