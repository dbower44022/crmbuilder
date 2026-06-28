"""Record-export API tests — PI-234 (REQ-130, DEC-693)."""

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

    def get_records(self, entity, *, max_size=200, offset=0):
        return (200, {"total": 1, "list": [{"id": "1", "name": entity}]})


def _create(client, **over):
    body = {"instance_name": "src", "instance_url": "https://src.example.org",
            "instance_role": "source", "secret": "api-key"}
    body.update(over)
    return client.post("/instances", json=body).json()["data"]


def test_export_records_endpoint(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    r = client.post(f"/instances/{iid}/export-records",
                    json={"entities": ["CMentorProfile", "CDues"]})
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    art = data["artifact"]
    assert art["summary"]["record_count"] == 2
    assert art["entities"]["CMentorProfile"]["records"][0]["name"] == "CMentorProfile"
    assert data["log"] == []


def test_export_target_role_rejected(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="target")["instance_identifier"]
    r = client.post(f"/instances/{iid}/export-records", json={"entities": ["X"]})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "not_auditable"


def test_export_missing_instance_404(client):
    assert client.post(
        "/instances/INST-999/export-records", json={"entities": ["X"]}
    ).status_code == 404
