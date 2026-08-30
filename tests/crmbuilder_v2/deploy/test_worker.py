"""Deploy worker tests — PI-419 (REQ-522).

``run_once`` claims across engagements and executes inside the run's own
scope; nothing queued means nothing ran; a stale run is reclaimed; the
lifespan starts an in-process worker only when configured to.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import DeployRun
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.deploy import worker as worker_module
from crmbuilder_v2.deploy.worker import DeployWorker
from sqlalchemy import select


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def _fake_run_deploy(calls):
    def _run(identifier, *, engagement_id, worker_id, deps=None):
        calls.append((identifier, engagement_id, worker_id))
        with session_scope() as s:
            deploy_runs.finish(s, identifier, status="succeeded")
        return "succeeded"

    return _run


def test_run_once_claims_and_executes_in_engagement_scope(v2_env, monkeypatch):
    calls = []
    monkeypatch.setattr(worker_module, "run_deploy", _fake_run_deploy(calls))
    w = DeployWorker(worker_id="test-worker", heartbeat_seconds=1)
    assert w.run_once() is False  # nothing queued
    with session_scope() as s:
        deploy_runs.create_deploy_run(s, spec={"domain": "crm.example.org"})
    assert w.run_once() is True
    assert calls == [("DEP-001", "ENG-001", "test-worker")]
    with session_scope() as s:
        assert deploy_runs.get_deploy_run(s, "DEP-001")["deploy_run_status"] == "succeeded"
    assert w.current_run is None and w.last_poll_at is not None


def test_run_once_reclaims_a_stale_run(v2_env, monkeypatch):
    calls = []
    monkeypatch.setattr(worker_module, "run_deploy", _fake_run_deploy(calls))
    with session_scope() as s:
        deploy_runs.create_deploy_run(s, spec={"domain": "crm.example.org"})
        deploy_runs.claim_next_run(s, worker_id="dead-worker")
        row = s.scalars(select(DeployRun)).one()
        row.deploy_run_heartbeat_at = datetime.now(UTC) - timedelta(seconds=999)
    w = DeployWorker(worker_id="new-worker", stale_seconds=180)
    assert w.run_once() is True
    assert calls[0][2] == "new-worker"


def test_loop_stops_cleanly(v2_env, monkeypatch):
    monkeypatch.setattr(worker_module, "run_deploy", _fake_run_deploy([]))
    w = DeployWorker(worker_id="loop", poll_seconds=1)
    w.start()
    assert w.alive
    w.stop(timeout=5)
    assert not w.alive


def test_lifespan_starts_worker_only_when_configured(v2_env, monkeypatch):
    from crmbuilder_v2.api.main import create_app
    from crmbuilder_v2.api.routers import deploy_runs as dr_router
    from fastapi.testclient import TestClient

    monkeypatch.setenv("CRMBUILDER_V2_DEPLOY_WORKER_INPROCESS", "false")
    from crmbuilder_v2 import config
    config.get_settings.cache_clear() if hasattr(config.get_settings, "cache_clear") else None
    with TestClient(create_app()) as client:
        client.headers.update({"X-Engagement": "ENG-001"})
        assert client.get("/deploy-runs/worker").json()["data"]["worker_active"] is False

    monkeypatch.setenv("CRMBUILDER_V2_DEPLOY_WORKER_INPROCESS", "true")
    config.get_settings.cache_clear() if hasattr(config.get_settings, "cache_clear") else None
    with TestClient(create_app()) as client:
        client.headers.update({"X-Engagement": "ENG-001"})
        data = client.get("/deploy-runs/worker").json()["data"]
        assert data["worker_active"] is True and data["worker_id"]
    assert dr_router._worker_ref["worker"] is None
