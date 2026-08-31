"""Deploy-run repository tests — PI-419 (REQ-522, PRJ-111).

Covers the table shape, ``DEP-NNN`` auto-assignment, the queued → running →
terminal lifecycle, the atomic claim (queued, stale-heartbeat reclaim, and the
non-stale run that must *not* be reclaimed), progress writes (log cap, phase
checkpoint), cancel, and the retry that keeps the checkpoint (DEC-945).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import ConflictError, UnprocessableError
from crmbuilder_v2.access.models import DeployRun
from crmbuilder_v2.access.repositories import deploy_runs
from sqlalchemy import inspect, select

_EXPECTED_COLUMNS = {
    "id",
    "deploy_run_identifier",
    "instance_identifier",
    "deploy_run_status",
    "deploy_run_phase",
    "deploy_run_spec",
    "deploy_run_secret_refs",
    "deploy_run_state",
    "deploy_run_log",
    "deploy_run_error",
    "deploy_run_provider",
    "deploy_run_requested_by",
    "deploy_run_worker_id",
    "deploy_run_heartbeat_at",
    "deploy_run_started_at",
    "deploy_run_ended_at",
    "created_at",
    "updated_at",
    "engagement_id",
}

_SPEC = {"domain": "crm.example.org", "region": "nyc3", "size": "s-2vcpu-4gb"}


def _queue(s, **kw):
    return deploy_runs.create_deploy_run(s, spec=kw.pop("spec", _SPEC), **kw)


def test_table_shape(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("deploy_runs")}
    assert cols == _EXPECTED_COLUMNS


def test_create_is_queued_and_increments(v2_env):
    with session_scope() as s:
        a = _queue(s, secret_refs={"admin_password": "crmbuilder:abc"},
                   requested_by="PRN-001", provider="digitalocean")
        b = _queue(s)
    assert a["deploy_run_identifier"] == "DEP-001"
    assert b["deploy_run_identifier"] == "DEP-002"
    assert a["deploy_run_status"] == "queued"
    assert a["deploy_run_spec"] == _SPEC
    assert a["deploy_run_secret_refs"] == {"admin_password": "crmbuilder:abc"}
    assert a["deploy_run_state"] == {"phases": {}}
    assert a["deploy_run_log"] == []
    assert a["deploy_run_requested_by"] == "PRN-001"
    # PI-442 (REQ-544): the history row names its hosting provider.
    assert a["deploy_run_provider"] == "digitalocean"
    assert b["deploy_run_provider"] is None
    assert a["instance_identifier"] is None


def test_create_rejects_empty_spec(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        deploy_runs.create_deploy_run(s, spec={})


def test_list_omits_log_and_filters(v2_env):
    with session_scope() as s:
        _queue(s)
        _queue(s, instance_identifier="INST-009")
        deploy_runs.append_log(s, "DEP-001", [("info", "hello")])
    with session_scope() as s:
        rows = deploy_runs.list_deploy_runs(s)
        assert [r["deploy_run_identifier"] for r in rows] == ["DEP-002", "DEP-001"]
        assert all("deploy_run_log" not in r for r in rows)
        only = deploy_runs.list_deploy_runs(s, instance_identifier="INST-009")
        assert [r["deploy_run_identifier"] for r in only] == ["DEP-002"]
        queued = deploy_runs.list_deploy_runs(s, status="queued", limit=1)
        assert len(queued) == 1
        with_log = deploy_runs.list_deploy_runs(s, include_log=True)
        assert with_log[1]["deploy_run_log"][0][1:] == ["info", "hello"]
        assert deploy_runs.get_deploy_run(s, "DEP-001")["deploy_run_log"]
        assert deploy_runs.get_deploy_run(s, "DEP-999") is None


def test_active_run_for_domain(v2_env):
    with session_scope() as s:
        _queue(s)
        assert deploy_runs.active_run_for_domain(s, "crm.example.org")["deploy_run_identifier"] == "DEP-001"
        assert deploy_runs.active_run_for_domain(s, "other.example.org") is None
        deploy_runs.request_cancel(s, "DEP-001")
        assert deploy_runs.active_run_for_domain(s, "crm.example.org") is None


def test_claim_takes_queued_run_once(v2_env):
    with session_scope() as s:
        _queue(s)
        first = deploy_runs.claim_next_run(s, worker_id="w1")
        assert first["deploy_run_identifier"] == "DEP-001"
        assert first["deploy_run_status"] == "running"
        assert first["deploy_run_worker_id"] == "w1"
        assert first["deploy_run_started_at"] is not None
        assert first["deploy_run_heartbeat_at"] is not None
        # A second worker sees nothing claimable while the heartbeat is fresh.
        assert deploy_runs.claim_next_run(s, worker_id="w2") is None


def test_claim_reclaims_stale_running_run(v2_env):
    with session_scope() as s:
        _queue(s)
        deploy_runs.claim_next_run(s, worker_id="w1")
        started = deploy_runs.get_deploy_run(s, "DEP-001")["deploy_run_started_at"]
        row = s.scalars(select(DeployRun)).one()
        row.deploy_run_heartbeat_at = datetime.now(UTC) - timedelta(seconds=600)
        s.flush()
        taken = deploy_runs.claim_next_run(s, worker_id="w2", stale_after_seconds=180)
        assert taken["deploy_run_identifier"] == "DEP-001"
        assert taken["deploy_run_worker_id"] == "w2"
        # The original start time is preserved; only the claim moved.
        assert taken["deploy_run_started_at"] == started


def test_claim_prefers_oldest(v2_env):
    with session_scope() as s:
        _queue(s)
        _queue(s)
        assert deploy_runs.claim_next_run(s, worker_id="w1")["deploy_run_identifier"] == "DEP-001"
        assert deploy_runs.claim_next_run(s, worker_id="w1")["deploy_run_identifier"] == "DEP-002"


def test_heartbeat_refuses_a_run_held_by_another_worker(v2_env):
    with session_scope() as s:
        _queue(s)
        deploy_runs.claim_next_run(s, worker_id="w1")
        deploy_runs.heartbeat(s, "DEP-001", worker_id="w1")
        with pytest.raises(ConflictError):
            deploy_runs.heartbeat(s, "DEP-001", worker_id="w2")


def test_append_log_caps_and_stamps(v2_env):
    with session_scope() as s:
        _queue(s)
        n = deploy_runs.append_log(s, "DEP-001", [("info", f"line {i}") for i in range(5)], cap=3)
        assert n == 3
        log = deploy_runs.get_deploy_run(s, "DEP-001")["deploy_run_log"]
        assert [e[2] for e in log] == ["line 2", "line 3", "line 4"]
        assert all(len(e) == 3 and e[0] for e in log)


def test_set_phase_merges_checkpoint(v2_env):
    with session_scope() as s:
        _queue(s)
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", phase_status="running")
        row = deploy_runs.set_phase(
            s, "DEP-001", "create_droplet",
            state={"droplet_id": "12345"}, phase_status="done",
        )
        assert row["deploy_run_phase"] == "create_droplet"
        st = row["deploy_run_state"]
        assert st["droplet_id"] == "12345"
        assert st["phases"]["create_droplet"]["status"] == "done"
        assert st["phases"]["create_droplet"]["started_at"]
        assert st["phases"]["create_droplet"]["ended_at"]
        with pytest.raises(UnprocessableError):
            deploy_runs.set_phase(s, "DEP-001", "not_a_phase")


def test_finish_keeps_checkpoint_and_sets_instance(v2_env):
    with session_scope() as s:
        _queue(s)
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", state={"droplet_id": "1"}, phase_status="done")
        row = deploy_runs.finish(s, "DEP-001", status="failed", error="dns timed out")
        assert row["deploy_run_status"] == "failed"
        assert row["deploy_run_error"] == "dns timed out"
        assert row["deploy_run_ended_at"] is not None
        assert row["deploy_run_state"]["droplet_id"] == "1"
        ok = deploy_runs.finish(s, "DEP-001", status="succeeded", instance_identifier="INST-003")
        assert ok["instance_identifier"] == "INST-003"
        with pytest.raises(UnprocessableError):
            deploy_runs.finish(s, "DEP-001", status="running")


def test_cancel_queued_is_immediate_and_running_is_a_flag(v2_env):
    with session_scope() as s:
        _queue(s)
        _queue(s)
        assert deploy_runs.request_cancel(s, "DEP-001")["deploy_run_status"] == "cancelled"
        deploy_runs.claim_next_run(s, worker_id="w1")  # takes DEP-002
        row = deploy_runs.request_cancel(s, "DEP-002")
        assert row["deploy_run_status"] == "running"
        assert row["deploy_run_state"]["cancel_requested"] is True
        with pytest.raises(ConflictError):
            deploy_runs.request_cancel(s, "DEP-001")


def test_requeue_resets_run_but_keeps_completed_phases(v2_env):
    with session_scope() as s:
        _queue(s)
        deploy_runs.claim_next_run(s, worker_id="w1")
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", state={"droplet_id": "9"}, phase_status="done")
        deploy_runs.set_phase(s, "DEP-001", "create_dns", phase_status="failed", error="403")
        deploy_runs.finish(s, "DEP-001", status="failed", error="403")
        row = deploy_runs.requeue(s, "DEP-001")
        assert row["deploy_run_status"] == "queued"
        assert row["deploy_run_error"] is None
        assert row["deploy_run_worker_id"] is None
        assert row["deploy_run_heartbeat_at"] is None
        assert row["deploy_run_ended_at"] is None
        phases = row["deploy_run_state"]["phases"]
        assert phases["create_droplet"]["status"] == "done"
        assert phases["create_dns"]["status"] == "retry"
        assert "error" not in phases["create_dns"]
        assert row["deploy_run_state"]["droplet_id"] == "9"
        # It is claimable again.
        assert deploy_runs.claim_next_run(s, worker_id="w3")["deploy_run_identifier"] == "DEP-001"
        with pytest.raises(ConflictError):
            deploy_runs.requeue(s, "DEP-001")
