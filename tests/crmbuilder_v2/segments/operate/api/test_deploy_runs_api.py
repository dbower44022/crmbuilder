"""Deploy-run API tests — PI-419 (REQ-522).

Queueing validates the spec, requires both provider credentials, stores the
passwords as refs (never echoed), auto-generates DB passwords, refuses a
second run for a domain in flight and the production host; polling with
``log_after`` returns only new lines; cancel / retry follow the repository
rules; and the surface is admin-only when auth is on.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access import principal as P
from crmbuilder_v2.access import rbac
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.api import principal_middleware, scope_middleware

BODY = {
    "instance_name": "Chapter CRM",
    "region": "nyc3",
    "size": "s-2vcpu-4gb",
    "image": "ubuntu-24-04-x64",
    "ssh_key_ids": [11],
    "zone_id": "z1",
    "zone_name": "Example.org",
    "subdomain": "CRM",
    "letsencrypt_email": "ops@example.org",
    "admin_email": "admin@example.org",
    "admin_password": "Adm1n!pass",
}


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def _creds(client):
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    client.put("/provider-credentials/cloudflare", json={"token": "cf"})


def test_create_requires_provider_credentials(client):
    r = client.post("/deploy-runs", json=BODY)
    assert r.status_code == 422
    codes = {e["code"] for e in r.json()["errors"]}
    assert codes == {"missing_provider_credential"}


def test_create_queues_run_with_refs_and_generated_db_passwords(client):
    _creds(client)
    r = client.post("/deploy-runs", json=BODY)
    assert r.status_code == 202, r.text
    data = r.json()["data"]
    assert data["deploy_run_identifier"] == "DEP-001"
    assert data["deploy_run_status"] == "queued"
    # PI-442 (REQ-544): the history row names its hosting provider.
    assert data["deploy_run_provider"] == "digitalocean"
    assert data["deploy_run_spec"]["domain"] == "crm.example.org"
    assert data["deploy_run_spec"]["admin_username"] == "admin"
    assert "deploy_run_secret_refs" not in data
    assert data["secrets_configured"] == ["admin_password", "db_password", "db_root_password"]
    assert "Adm1n!pass" not in r.text and "crmbuilder:" not in r.text
    with session_scope() as s:
        refs = deploy_runs.get_deploy_run(s, "DEP-001")["deploy_run_secret_refs"]
    assert secrets.get_secret(refs["admin_password"]) == "Adm1n!pass"
    assert len(secrets.get_secret(refs["db_password"])) >= 16
    assert secrets.get_secret(refs["db_password"]) != secrets.get_secret(refs["db_root_password"])


def test_create_rejects_second_run_for_domain_and_bad_specs(client):
    _creds(client)
    assert client.post("/deploy-runs", json=BODY).status_code == 202
    dup = client.post("/deploy-runs", json=BODY)
    assert dup.status_code == 422
    assert dup.json()["errors"][0]["code"] == "run_in_progress"

    bad = client.post("/deploy-runs", json={**BODY, "subdomain": "bad_label!", "admin_email": "nope"})
    assert bad.status_code == 422
    fields = {e["field"] for e in bad.json()["errors"]}
    assert {"subdomain", "admin_email"} <= fields

    prod = client.post("/deploy-runs", json={**BODY, "zone_name": "crmbuilder.ai", "subdomain": "api"})
    assert prod.status_code == 422
    assert prod.json()["errors"][0]["code"] == "protected_host"

    assert client.post("/deploy-runs", json={**BODY, "admin_password": " "}).status_code == 422
    assert client.post("/deploy-runs", json={**BODY, "extra": 1}).status_code == 422


def test_get_list_poll_cancel_retry(client):
    _creds(client)
    client.post("/deploy-runs", json=BODY)
    with session_scope() as s:
        deploy_runs.append_log(s, "DEP-001", [("info", "one"), ("info", "two"), ("info", "three")])

    listed = client.get("/deploy-runs").json()["data"]
    assert [r["deploy_run_identifier"] for r in listed] == ["DEP-001"]
    assert "deploy_run_log" not in listed[0]

    full = client.get("/deploy-runs/DEP-001").json()["data"]
    assert full["log_length"] == 3 and len(full["deploy_run_log"]) == 3
    tail = client.get("/deploy-runs/DEP-001?log_after=2").json()["data"]
    assert [e[2] for e in tail["deploy_run_log"]] == ["three"] and tail["log_length"] == 3
    assert client.get("/deploy-runs/DEP-999").status_code == 404

    cancelled = client.post("/deploy-runs/DEP-001/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["deploy_run_status"] == "cancelled"
    again = client.post("/deploy-runs/DEP-001/cancel")
    assert again.status_code == 409

    retried = client.post("/deploy-runs/DEP-001/retry")
    assert retried.status_code == 200
    assert retried.json()["data"]["deploy_run_status"] == "queued"
    assert client.post("/deploy-runs/DEP-001/retry").status_code == 409
    assert client.post("/deploy-runs/DEP-404/retry").status_code == 404

    # The domain is in flight again, so a duplicate is refused.
    assert client.post("/deploy-runs", json=BODY).status_code == 422
    assert client.get("/deploy-runs?status=queued").json()["data"][0]["deploy_run_identifier"] == "DEP-001"


def test_worker_status_without_a_worker(client):
    data = client.get("/deploy-runs/worker").json()["data"]
    assert data["worker_active"] is False


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
    vh = {"Authorization": f"Bearer {vtok.plaintext}"}
    oh = {"Authorization": f"Bearer {otok.plaintext}"}
    assert client.get("/deploy-runs", headers=vh).status_code == 403
    assert client.post("/deploy-runs", json=BODY, headers=vh).status_code == 403
    assert client.get("/deploy-runs", headers=oh).status_code == 200
    _creds_ok = client.put("/provider-credentials/digitalocean", json={"token": "do"}, headers=oh)
    assert _creds_ok.status_code == 200
    client.put("/provider-credentials/cloudflare", json={"token": "cf"}, headers=oh)
    r = client.post("/deploy-runs", json=BODY, headers=oh)
    assert r.status_code == 202
    assert r.json()["data"]["deploy_run_requested_by"] == owner.principal_id


# --- Manual DNS (PI-566 / REQ-642) ------------------------------------------

MANUAL_BODY = {
    **{k: v for k, v in BODY.items() if k not in ("zone_id", "zone_name", "subdomain")},
    "dns_mode": "manual",
    "domain": "CRM.bbmentors.org.",
}


def test_manual_dns_queues_with_only_the_digitalocean_credential(client):
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    r = client.post("/deploy-runs", json=MANUAL_BODY)
    assert r.status_code == 202, r.text
    spec = r.json()["data"]["deploy_run_spec"]
    assert spec["dns_mode"] == "manual"
    assert spec["domain"] == "crm.bbmentors.org"
    assert spec["zone_id"] == "" and spec["zone_name"] == "" and spec["subdomain"] == ""


def test_manual_dns_still_needs_digitalocean_and_a_full_address(client):
    r = client.post("/deploy-runs", json=MANUAL_BODY)
    assert r.status_code == 422
    assert {(e["field"], e["code"]) for e in r.json()["errors"]} == {
        ("digitalocean", "missing_provider_credential")
    }
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    for domain, code in (("", "required"), ("crm", "invalid"), ("api.crmbuilder.ai", "protected_host")):
        r = client.post("/deploy-runs", json={**MANUAL_BODY, "domain": domain})
        assert r.status_code == 422, domain
        assert ("domain", code) in {(e["field"], e["code"]) for e in r.json()["errors"]}
    r = client.post("/deploy-runs", json={**MANUAL_BODY, "dns_mode": "route53"})
    assert r.status_code == 422
    assert "dns_mode" in {e["field"] for e in r.json()["errors"]}


def test_cloudflare_mode_still_requires_the_cloudflare_credential(client):
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    r = client.post("/deploy-runs", json=BODY)
    assert r.status_code == 422
    assert {(e["field"], e["code"]) for e in r.json()["errors"]} == {
        ("cloudflare", "missing_provider_credential")
    }


# --- PI-571 (REQ-648, REQ-650): the address lookup and Try again with a
# corrected address --------------------------------------------------------


def test_dns_lookup_describes_the_address(client, monkeypatch):
    from crmbuilder_v2.deploy import dns_check

    from tests.crmbuilder_v2.deploy.fakes import FakeDnsLookup

    lookup = FakeDnsLookup(zone="bbmentors.org", name_servers=("ns51.domaincontrol.com",),
                           records={("crm.bbmentors.org", "A"): ["198.51.100.9"]})
    monkeypatch.setattr(dns_check, "PublicDnsLookup", lambda: lookup)
    r = client.get("/deploy-runs/dns-lookup?domain=CRM.bbmentors.org")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["dns_host"] == "GoDaddy" and data["zone"] == "bbmentors.org"
    assert data["record_name"] == "crm" and data["existing_records"] == {"A": ["198.51.100.9"]}
    assert client.get("/deploy-runs/dns-lookup?domain=crm").status_code == 422
    assert client.get("/deploy-runs/dns-lookup?domain=api.crmbuilder.ai").status_code == 422


def test_try_again_accepts_a_corrected_address_and_validates_it(client):
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    client.post("/deploy-runs", json={**MANUAL_BODY, "domain": "crm.bbmentor.org"})
    with session_scope() as s:
        deploy_runs.set_phase(s, "DEP-001", "install_espocrm", phase_status="done")
        deploy_runs.set_phase(s, "DEP-001", "check_dns", phase_status="needs_action")
        deploy_runs.finish(s, "DEP-001", status="needs_action")

    bad = client.post("/deploy-runs/DEP-001/retry", json={"domain": "crm"})
    assert bad.status_code == 422
    assert ("domain", "invalid") in {(e["field"], e["code"]) for e in bad.json()["errors"]}

    r = client.post("/deploy-runs/DEP-001/retry", json={"domain": "CRM.bbmentors.org"})
    assert r.status_code == 200, r.text
    run = r.json()["data"]
    assert run["deploy_run_status"] == "queued"
    assert run["deploy_run_spec"]["domain"] == "crm.bbmentors.org"
    state = run["deploy_run_state"]
    assert state["installed_domain"] == "crm.bbmentor.org"  # the CRM is renamed, not reinstalled
    assert state["phases"]["install_espocrm"]["status"] == "retry"
    assert state["phases"]["check_dns"]["status"] == "retry"


def test_try_again_without_a_body_keeps_the_request(client):
    client.put("/provider-credentials/digitalocean", json={"token": "do"})
    client.post("/deploy-runs", json=MANUAL_BODY)
    with session_scope() as s:
        deploy_runs.finish(s, "DEP-001", status="needs_action")
    r = client.post("/deploy-runs/DEP-001/retry")
    assert r.status_code == 200
    assert r.json()["data"]["deploy_run_spec"]["domain"] == "crm.bbmentors.org"


def test_check_dns_endpoint(client, monkeypatch):
    from crmbuilder_v2.deploy import dns_followup

    seen = []
    monkeypatch.setattr(dns_followup, "check_instance_dns",
                        lambda ident: seen.append(ident) or {"instance_identifier": ident, "open_items": []})
    assert client.post("/instances/INST-404/check-dns").status_code == 404
    created = client.post("/instances", json={
        "instance_name": "Chapter CRM", "instance_url": "https://crm.example.org",
        "instance_vendor": "espocrm", "instance_role": "both", "instance_auth_method": "basic",
    })
    assert created.status_code == 201, created.text
    ident = created.json()["data"]["instance_identifier"]
    r = client.post(f"/instances/{ident}/check-dns")
    assert r.status_code == 200 and r.json()["data"]["open_items"] == [] and seen == [ident]
