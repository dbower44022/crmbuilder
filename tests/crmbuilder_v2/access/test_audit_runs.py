"""Audit-run repository tests — PI-448 (REQ-551 / DEC-994).

The job record's lifecycle in the deploy-run shape: created queued with an
ARN- identifier; one active run per (instance, area); an atomic claim that
also reclaims a stale heartbeat; heartbeat conflict once lost; progress and
log accretion; terminal finish retaining everything.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, UnprocessableError
from crmbuilder_v2.access.models import AuditRun
from crmbuilder_v2.access.repositories import audit_runs
from sqlalchemy import select


def _create(s, instance="INST-001", area="utilization"):
    return audit_runs.create_audit_run(s, instance_identifier=instance, area=area)


def test_create_assigns_arn_identifier_and_queued_status(v2_env):
    with session_scope() as s:
        row = _create(s)
        assert row["audit_run_identifier"] == "ARN-001"
        assert row["audit_run_status"] == "queued"
        assert row["audit_run_area"] == "utilization"
        assert row["audit_run_progress"] == {}
        assert _create(s, instance="INST-002")["audit_run_identifier"] == "ARN-002"


def test_unknown_area_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            _create(s, area="entities")


def test_active_run_lookup_sees_queued_and_running_only(v2_env):
    with session_scope() as s:
        row = _create(s)
        active = audit_runs.active_run_for(
            s, instance_identifier="INST-001", area="utilization"
        )
        assert active["audit_run_identifier"] == row["audit_run_identifier"]
        audit_runs.claim_next_run(s, worker_id="w1")
        assert audit_runs.active_run_for(
            s, instance_identifier="INST-001", area="utilization"
        )
        audit_runs.finish(s, row["audit_run_identifier"], status="succeeded")
        assert (
            audit_runs.active_run_for(
                s, instance_identifier="INST-001", area="utilization"
            )
            is None
        )


def test_claim_marks_running_and_stamps_worker(v2_env):
    with session_scope() as s:
        _create(s)
        claimed = audit_runs.claim_next_run(s, worker_id="w1")
        assert claimed["audit_run_status"] == "running"
        assert claimed["audit_run_worker_id"] == "w1"
        assert claimed["audit_run_started_at"] is not None
        # nothing else claimable
        assert audit_runs.claim_next_run(s, worker_id="w2") is None


def test_stale_heartbeat_is_reclaimed(v2_env):
    with session_scope() as s:
        row = _create(s)
        audit_runs.claim_next_run(s, worker_id="dead")
        db_row = s.scalars(select(AuditRun)).one()
        db_row.audit_run_heartbeat_at = datetime.now(UTC) - timedelta(seconds=999)
        reclaimed = audit_runs.claim_next_run(
            s, worker_id="alive", stale_after_seconds=180
        )
        assert reclaimed["audit_run_identifier"] == row["audit_run_identifier"]
        assert reclaimed["audit_run_worker_id"] == "alive"
        # the dead worker's heartbeat now conflicts
        with pytest.raises(ConflictError):
            audit_runs.heartbeat(s, row["audit_run_identifier"], worker_id="dead")


def test_progress_merges_and_log_appends_capped(v2_env):
    with session_scope() as s:
        row = _create(s)
        arn = row["audit_run_identifier"]
        audit_runs.set_progress(s, arn, {"entities_done": 0, "entities_total": 5})
        out = audit_runs.set_progress(s, arn, {"entities_done": 3})
        assert out["audit_run_progress"] == {"entities_done": 3, "entities_total": 5}
        n = audit_runs.append_log(s, arn, [["info", "a"], ["warning", "b"]])
        assert n == 2
        n = audit_runs.append_log(s, arn, [["info", "c"]], cap=2)
        assert n == 2  # capped: oldest line dropped
        log = audit_runs.get_audit_run(s, arn)["audit_run_log"]
        assert [line[2] for line in log] == ["b", "c"]


def test_finish_lands_terminal_and_retains_everything(v2_env):
    with session_scope() as s:
        row = _create(s)
        arn = row["audit_run_identifier"]
        audit_runs.claim_next_run(s, worker_id="w1")
        audit_runs.set_progress(s, arn, {"entities_done": 5, "entities_total": 5})
        done = audit_runs.finish(
            s, arn, status="succeeded", summary={"evidence_rows": 12}
        )
        assert done["audit_run_status"] == "succeeded"
        assert done["audit_run_summary"] == {"evidence_rows": 12}
        assert done["audit_run_progress"]["entities_done"] == 5
        assert done["audit_run_ended_at"] is not None
        with pytest.raises(UnprocessableError):
            audit_runs.finish(s, arn, status="queued")
