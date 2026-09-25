"""Deployment API tests — PI-576 (REQ-653).

``/deployments`` composes what a deployment holds, stores an instance's
secrets behind the boundary and never echoes them, applies the refusal codes
of the repository as 422s, and lets a deploy run be queued for a deployment
so its credentials and its instance attach to it.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.operate.repositories import (
    provider_credentials as credential_repo,
)


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def seeded(client):
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
        engagement_repo.create_engagement(
            s,
            engagement_code="OTHER",
            engagement_name="Other application",
            engagement_purpose="p",
            engagement_identifier="ENG-002",
            engagement_defining_client="CLI-002",
        )
    return client


def _codes(response) -> list[str]:
    return [e["code"] for e in response.json()["errors"]]


def test_create_with_instance_secrets_and_read_back(seeded):
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-001",
            "deployment_purpose": "client_own",
            "deployment_name": "Cleveland production",
            "instance": {
                "instance_name": "CBM Production",
                "instance_url": "https://crm.example.org",
                "instance_auth_method": "basic",
                "secret": "admin",
                "secret_key": "Adm1n!",
            },
            "deploy_config": {"domain": "crm.example.org", "droplet_id": "42"},
        },
    )
    assert r.status_code == 201, r.text
    d = r.json()["data"]
    assert d["deployment_identifier"] == "DPL-001"
    assert d["deployment_application"] == "ENG-001"  # the active engagement
    assert d["deployment_client"] == "CLI-001"
    assert d["instance"]["instance_identifier"] == "INST-001"
    assert d["deploy_config"]["droplet_id"] == "42"
    assert "Adm1n!" not in r.text and "admin" not in r.json()["data"]["instance"].get(
        "instance_secret_ref", ""
    )
    assert secrets.get_secret(d["instance"]["instance_secret_ref"]) == "admin"
    assert secrets.get_secret(d["instance"]["instance_secret_key_ref"]) == "Adm1n!"

    listed = seeded.get("/deployments").json()["data"]
    assert [x["deployment_identifier"] for x in listed] == ["DPL-001"]
    assert seeded.get("/deployments?client=CLI-002").json()["data"] == []
    assert seeded.get("/deployments?application=ENG-001").json()["data"][0][
        "deployment_identifier"
    ] == "DPL-001"
    one = seeded.get("/deployments/DPL-001").json()["data"]
    assert one["instance"]["instance_url"] == "https://crm.example.org"
    assert seeded.get("/deployments/next-identifier").json()["data"] == {"next": "DPL-002"}
    assert seeded.get("/deployments/DPL-404").status_code == 404

    # The instance path still reads the same instance (a view over the deployment).
    assert seeded.get("/instances/INST-001").json()["data"]["instance_name"] == "CBM Production"


def test_refusals_are_422_with_their_codes(seeded):
    r = seeded.post(
        "/deployments", json={"deployment_client": "CLI-999", "deployment_purpose": "client_own", "deployment_name": "x"}
    )
    assert r.status_code == 422 and _codes(r) == ["client_not_found"]
    r = seeded.post(
        "/deployments",
        json={"deployment_client": "CLI-002", "deployment_purpose": "client_own", "deployment_name": "x"},
    )
    assert r.status_code == 422 and _codes(r) == ["application_private"]
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-001",
            "deployment_purpose": "client_own",
            "deployment_name": "x",
            "deployment_application": "ENG-999",
        },
    )
    assert r.status_code == 422 and _codes(r) == ["application_not_found"]
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-001",
            "deployment_purpose": "client_own",
            "deployment_name": "x",
            "instance_identifier": "INST-777",
        },
    )
    assert r.status_code == 422 and _codes(r) == ["instance_not_found"]
    # A deployment of another application can be created from this engagement.
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-002",
            "deployment_purpose": "client_own",
            "deployment_name": "Other's own",
            "deployment_application": "ENG-002",
        },
    )
    assert r.status_code == 201 and r.json()["data"]["deployment_application"] == "ENG-002"


def test_patch_delete_restore(seeded):
    seeded.post("/deployments", json={"deployment_client": "CLI-001", "deployment_purpose": "client_own", "deployment_name": "A"})
    r = seeded.patch(
        "/deployments/DPL-001",
        json={"deployment_name": "B", "deployment_status": "retired", "deployment_notes": "n"},
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert (d["deployment_name"], d["deployment_status"], d["deployment_notes"]) == ("B", "retired", "n")
    r = seeded.patch("/deployments/DPL-001", json={"deployment_client": "CLI-002"})
    assert r.status_code == 422 and _codes(r) == ["application_private"]
    assert seeded.delete("/deployments/DPL-001").status_code == 200
    assert seeded.get("/deployments/DPL-001").status_code == 404
    assert seeded.get("/deployments/DPL-001?include_deleted=true").status_code == 200
    assert seeded.post("/deployments/DPL-001/restore").status_code == 200
    assert seeded.get("/deployments/DPL-001").status_code == 200


def test_deployment_credentials_never_echo_and_override_the_application(seeded):
    seeded.post("/deployments", json={"deployment_client": "CLI-001", "deployment_purpose": "client_own", "deployment_name": "A"})
    assert seeded.put(
        "/provider-credentials/digitalocean", json={"token": "app-token", "label": "app"}
    ).status_code == 200
    r = seeded.put(
        "/deployments/DPL-001/provider-credentials/digitalocean",
        json={"token": "dpl-token", "label": "Rochester's own"},
    )
    assert r.status_code == 200, r.text
    assert "dpl-token" not in r.text and "crmbuilder:" not in r.text
    creds = r.json()["data"]
    assert [(c["provider"], c["scope"], c["label"]) for c in creds] == [
        ("digitalocean", "deployment", "Rochester's own")
    ]
    assert seeded.get("/deployments/DPL-001/provider-credentials").json()["data"] == creds
    with session_scope() as s:
        own = credential_repo.resolve_provider_credential(
            s, "digitalocean", deployment_identifier="DPL-001"
        )
        assert secrets.get_secret(own["token_ref"]) == "dpl-token"
        # The application-level credential is untouched.
        app = credential_repo.get_provider_credential(s, "digitalocean")
        assert secrets.get_secret(app["token_ref"]) == "app-token"
    # Blank token refused; unknown provider refused.
    assert seeded.put(
        "/deployments/DPL-001/provider-credentials/digitalocean", json={"token": "  "}
    ).status_code == 422
    assert seeded.put(
        "/deployments/DPL-001/provider-credentials/aws", json={"token": "x"}
    ).status_code == 422
    r = seeded.delete("/deployments/DPL-001/provider-credentials/digitalocean")
    assert r.status_code == 200 and r.json()["data"]["scope"] == "deployment"
    assert seeded.delete("/deployments/DPL-001/provider-credentials/digitalocean").status_code == 404
    fallback = seeded.get("/deployments/DPL-001/provider-credentials").json()["data"]
    assert [(c["provider"], c["scope"]) for c in fallback] == [("digitalocean", "application")]


def test_deploy_run_queued_for_a_deployment_carries_it(seeded, monkeypatch):
    seeded.post("/deployments", json={"deployment_client": "CLI-001", "deployment_purpose": "client_own", "deployment_name": "Boston"})
    # Only the deployment holds a DigitalOcean credential; manual DNS needs no Cloudflare.
    seeded.put(
        "/deployments/DPL-001/provider-credentials/digitalocean", json={"token": "dpl-do"}
    )
    body = {
        "instance_name": "Boston CRM",
        "region": "nyc3",
        "size": "s-1vcpu-1gb",
        "image": "ubuntu-24-04-x64",
        "dns_mode": "manual",
        "domain": "crm.bbmentors.org",
        "letsencrypt_email": "ops@example.org",
        "admin_email": "ops@example.org",
        "admin_password": "Adm1n!",
        "deployment_identifier": "DPL-001",
    }
    r = seeded.post("/deploy-runs", json=body)
    assert r.status_code == 202, r.text
    run = r.json()["data"]
    assert run["deployment_identifier"] == "DPL-001"
    listed = seeded.get("/deploy-runs?deployment=DPL-001").json()["data"]
    assert [x["deploy_run_identifier"] for x in listed] == [run["deploy_run_identifier"]]
    assert seeded.get("/deploy-runs?deployment=DPL-999").json()["data"] == []
    # A run for an unknown deployment, or one of another application, is refused.
    r = seeded.post("/deploy-runs", json={**body, "deployment_identifier": "DPL-404", "domain": "b.example.org"})
    assert r.status_code == 422 and _codes(r) == ["deployment_not_found"]
    # Without the deployment the application holds no DigitalOcean credential.
    r = seeded.post("/deploy-runs", json={k: v for k, v in body.items() if k != "deployment_identifier"} | {"domain": "c.example.org"})
    assert r.status_code == 422 and _codes(r) == ["missing_provider_credential"]


def test_purpose_required_demo_test_gate_and_for_client_listing(seeded):
    """PI-577 / REQ-654 at the API: no purpose is a 422, a demo/test
    deployment for the wrong client is a 422 with its code, and
    ``for_client`` returns what a client may see, purpose included."""
    r = seeded.post("/deployments", json={"deployment_client": "CLI-001", "deployment_name": "x"})
    assert r.status_code == 422
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-001",
            "deployment_name": "x",
            "deployment_purpose": "staging",
        },
    )
    assert r.status_code == 422 and _codes(r) == ["invalid_value"]
    # ENG-002 is private to CLI-002: only CLI-002 may run its demo/test.
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-002",
            "deployment_name": "Other try",
            "deployment_purpose": "demo_test",
            "deployment_application": "ENG-002",
        },
    )
    assert r.status_code == 201 and r.json()["data"]["deployment_purpose"] == "demo_test"
    r = seeded.post(
        "/deployments",
        json={
            "deployment_client": "CLI-001",
            "deployment_name": "Cleveland own",
            "deployment_purpose": "client_own",
        },
    )
    assert r.status_code == 201
    r = seeded.patch("/deployments/DPL-002", json={"deployment_purpose": "demo_test"})
    assert r.status_code == 200 and r.json()["data"]["deployment_purpose"] == "demo_test"
    # CLI-001 sees its own (now demo/test) and nothing of CLI-002's private application.
    mine = seeded.get("/deployments?for_client=CLI-001").json()["data"]
    assert [(d["deployment_identifier"], d["deployment_purpose"]) for d in mine] == [
        ("DPL-002", "demo_test")
    ]
    theirs = seeded.get("/deployments?for_client=CLI-002").json()["data"]
    assert [d["deployment_identifier"] for d in theirs] == ["DPL-001"]
    assert seeded.get("/deployments?for_client=CLI-999").status_code == 404
    # Every listing carries the purpose.
    assert all("deployment_purpose" in d for d in seeded.get("/deployments").json()["data"])

