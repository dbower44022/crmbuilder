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
