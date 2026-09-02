"""Audit-run API tests — PI-448 (REQ-551 / DEC-994).

Starting the utilization pass returns a job identifier immediately (202);
its record is pollable while queued and afterwards; one active run per
(instance, area); the synchronous per-area endpoint now refuses the opt-in
area with a pointer to the job endpoints while structural areas keep their
synchronous path.
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
def client(v2_env, monkeypatch):
    monkeypatch.setattr(
        instances_router, "_audit_introspection_client", lambda _id: object()
    )
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


def _make_instance(client, name="cbmtest") -> str:
    response = client.post(
        "/instances",
        json={
            "instance_name": name,
            "instance_url": f"https://{name}.example.org",
            "instance_role": "both",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["instance_identifier"]


def test_start_returns_identifier_immediately_and_is_pollable(client):
    inst = _make_instance(client)
    started = client.post(f"/instances/{inst}/audit-runs")
    assert started.status_code == 202, started.text
    run = started.json()["data"]
    arn = run["audit_run_identifier"]
    assert arn.startswith("ARN-")
    assert run["audit_run_status"] == "queued"

    polled = client.get(f"/audit-runs/{arn}")
    assert polled.status_code == 200
    body = polled.json()["data"]
    assert body["audit_run_status"] == "queued"
    assert body["instance_identifier"] == inst
    assert body["audit_run_area"] == "utilization"

    listing = client.get(f"/audit-runs?instance={inst}")
    assert [r["audit_run_identifier"] for r in listing.json()["data"]] == [arn]


def test_one_active_run_per_instance_and_area(client):
    inst = _make_instance(client)
    assert client.post(f"/instances/{inst}/audit-runs").status_code == 202
    second = client.post(f"/instances/{inst}/audit-runs")
    assert second.status_code == 422
    assert second.json()["errors"][0]["code"] == "run_in_progress"
    # a different instance is unaffected
    other = _make_instance(client, name="other")
    assert client.post(f"/instances/{other}/audit-runs").status_code == 202


def test_structural_area_is_not_a_background_job(client):
    inst = _make_instance(client)
    response = client.post(f"/instances/{inst}/audit-runs?area=entities")
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "invalid_value"


def test_sync_utilization_endpoint_points_at_the_job(client):
    inst = _make_instance(client)
    response = client.post(f"/instances/{inst}/audit/utilization")
    assert response.status_code == 422
    error = response.json()["errors"][0]
    assert error["code"] == "background_job_required"
    assert "audit-runs" in error["message"]


def test_get_unknown_run_404(client):
    assert client.get("/audit-runs/ARN-999").status_code == 404
