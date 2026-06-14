"""Instance audit + membership API tests — PI-185 (PRJ-027).

Exercises POST /instances/{id}/audit (entity reconcile via a monkeypatched
introspection client) and GET /instances/{id}/memberships, plus the role and
credential gates.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.routers import instances as instances_router
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


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_all_scopes(self):
        cust = {"entity": True, "customizable": True, "isCustom": True}
        return (200, {
            "CEngagement": {**cust, "stream": False},
            "CDues": {**cust, "stream": True},
            "Account": {"entity": True, "customizable": True, "isCustom": False},
        })


def _create(client, **over):
    body = {
        "instance_name": "src",
        "instance_url": "https://src.example.org",
        "instance_role": "source",
        "secret": "api-key",
    }
    body.update(over)
    return client.post("/instances", json=body).json()["data"]


def test_audit_reconciles_and_lists_memberships(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client)
    iid = inst["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]
    assert summary["created"] == 2 and summary["present"] == 2
    # Memberships listed.
    rows = client.get(f"/instances/{iid}/memberships").json()["data"]
    assert len(rows) == 2
    assert all(row["member_type"] == "entity" for row in rows)
    assert all(row["state"] == "present" for row in rows)


def test_audit_target_role_rejected(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client, instance_role="target")
    r = client.post(f"/instances/{inst['instance_identifier']}/audit")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "not_auditable"


def test_audit_missing_credentials_rejected(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client, secret=None)
    r = client.post(f"/instances/{inst['instance_identifier']}/audit")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "missing_credentials"


def test_audit_missing_instance_404(client):
    assert client.post("/instances/INST-999/audit").status_code == 404
    assert client.get("/instances/INST-999/memberships").status_code == 404
