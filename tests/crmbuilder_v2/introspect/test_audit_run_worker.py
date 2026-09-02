"""Audit-run worker tests — PI-448 (REQ-551 / DEC-994).

``run_once`` claims across engagements and executes inside the run's own
scope; nothing queued means nothing ran; a stale run is reclaimed; and
``run_audit_run`` drives the reconciler to a terminal status with progress,
log and summary on the record — including the aborted-before-anything case
landing as failed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import AuditRun
from crmbuilder_v2.access.repositories import audit_runs
from crmbuilder_v2.api.routers import instances as instances_router
from crmbuilder_v2.introspect import audit_run_worker as worker_module
from crmbuilder_v2.introspect.audit_run_worker import AuditRunWorker, run_audit_run
from sqlalchemy import select


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


def _queue(instance="INST-001"):
    with session_scope() as s:
        return audit_runs.create_audit_run(
            s, instance_identifier=instance, area="utilization"
        )["audit_run_identifier"]


def _fake_run(calls, status="succeeded"):
    def _run(identifier, *, engagement_id, worker_id):
        calls.append((identifier, engagement_id, worker_id))
        with session_scope() as s:
            audit_runs.finish(s, identifier, status=status)
        return status

    return _run


def test_run_once_claims_and_executes_in_engagement_scope(v2_env, monkeypatch):
    calls = []
    monkeypatch.setattr(worker_module, "run_audit_run", _fake_run(calls))
    w = AuditRunWorker(worker_id="test-worker", heartbeat_seconds=1)
    assert w.run_once() is False  # nothing queued
    _queue()
    assert w.run_once() is True
    assert calls == [("ARN-001", "ENG-001", "test-worker")]
    with session_scope() as s:
        assert (
            audit_runs.get_audit_run(s, "ARN-001")["audit_run_status"] == "succeeded"
        )
    assert w.current_run is None and w.last_poll_at is not None


def test_run_once_reclaims_a_stale_run(v2_env, monkeypatch):
    calls = []
    monkeypatch.setattr(worker_module, "run_audit_run", _fake_run(calls))
    _queue()
    with session_scope() as s:
        audit_runs.claim_next_run(s, worker_id="dead-worker")
        row = s.scalars(select(AuditRun)).one()
        row.audit_run_heartbeat_at = datetime.now(UTC) - timedelta(seconds=999)
    w = AuditRunWorker(worker_id="new-worker", stale_seconds=180)
    assert w.run_once() is True
    assert calls[0][2] == "new-worker"


def test_run_audit_run_executes_reconciler_with_progress_and_summary(
    v2_env, monkeypatch
):
    monkeypatch.setattr(
        instances_router, "_audit_introspection_client", lambda _id: object()
    )

    def fake_reconcile(session, *, instance_identifier, client, progress, counters):
        counters(0, 2)
        progress("profiling CEngagement")
        counters(2, 2)
        return {"entities": 2, "fields": 5, "evidence_rows": 7, "aborted": False,
                "anomalies": [], "deposit_event_identifier": "DEP-009"}

    monkeypatch.setattr(
        "crmbuilder_v2.introspect.utilization.reconcile_utilization", fake_reconcile
    )
    arn = _queue()
    with session_scope() as s:
        audit_runs.claim_next_run(s, worker_id="w1")
    status = run_audit_run(arn, engagement_id="ENG-001", worker_id="w1")
    assert status == "succeeded"
    with session_scope() as s:
        row = audit_runs.get_audit_run(s, arn)
    assert row["audit_run_status"] == "succeeded"
    assert row["audit_run_progress"] == {"entities_done": 2, "entities_total": 2}
    assert row["audit_run_summary"]["deposit_event_identifier"] == "DEP-009"
    assert any("CEngagement" in line[2] for line in row["audit_run_log"])


def test_run_audit_run_aborted_before_anything_is_failed(v2_env, monkeypatch):
    monkeypatch.setattr(
        instances_router, "_audit_introspection_client", lambda _id: object()
    )
    monkeypatch.setattr(
        "crmbuilder_v2.introspect.utilization.reconcile_utilization",
        lambda session, **kw: {"entities": 0, "fields": 0, "evidence_rows": 0,
                               "aborted": True, "anomalies": [],
                               "deposit_event_identifier": "DEP-010"},
    )
    arn = _queue()
    with session_scope() as s:
        audit_runs.claim_next_run(s, worker_id="w1")
    assert run_audit_run(arn, engagement_id="ENG-001", worker_id="w1") == "failed"
    with session_scope() as s:
        row = audit_runs.get_audit_run(s, arn)
    assert row["audit_run_status"] == "failed"
    assert "aborted" in row["audit_run_error"]


def test_run_audit_run_credential_failure_is_failed(v2_env, monkeypatch):
    def boom(_id):
        raise RuntimeError("no credentials")

    monkeypatch.setattr(instances_router, "_audit_introspection_client", boom)
    arn = _queue()
    with session_scope() as s:
        audit_runs.claim_next_run(s, worker_id="w1")
    assert run_audit_run(arn, engagement_id="ENG-001", worker_id="w1") == "failed"
    with session_scope() as s:
        assert (
            "no credentials"
            in audit_runs.get_audit_run(s, arn)["audit_run_error"]
        )
