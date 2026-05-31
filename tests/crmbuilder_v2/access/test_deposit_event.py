"""Deposit event repository tests — UI v0.7 Slice A.

Born-terminal append-only: POST + GET only. Atomic POST creates the record,
parent + wrote_record edges, drives the first-success ready->applied
transition, and lazy-creates the target close_out_payload when absent.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import close_out_payloads as cop
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import deposit_events as dep
from crmbuilder_v2.access.repositories import references as refs
from crmbuilder_v2.access.repositories import sessions as sess
from crmbuilder_v2.access.repositories import projects as ws
from sqlalchemy import inspect

_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _ready_cop(s, identifier="COP-001"):
    wid = ws.create_project(s, name="WS", purpose="p", description="d")[
        "project_identifier"
    ]
    # Under PI-073, conversations nest within a session via a mandatory
    # conversation_belongs_to_session edge. Create the containing session
    # (anchored to the workstream) first.
    sid = sess.create_session(
        s, title="S", description="d", medium="chat",
        executive_summary=_EXEC_SUMMARY, identifier="SES-001",
        references=[{
            "source_type": "session", "source_id": "SES-001",
            "target_type": "project", "target_id": wid,
            "relationship": "session_belongs_to_project",
        }],
    )["session_identifier"]
    conv = cr.create_conversation(
        s, title="C", purpose="p", description="d", identifier="CNV-001",
        references=[{
            "source_type": "conversation", "source_id": "CNV-001",
            "target_type": "session", "target_id": sid,
            "relationship": "conversation_belongs_to_session",
        }],
    )["conversation_identifier"]
    cop.create_close_out_payload(
        s, title="P", description="d", file_path="close-out-payloads/x.json",
        identifier=identifier, status="ready",
        references=[{
            "source_type": "close_out_payload", "source_id": identifier,
            "target_type": "conversation", "target_id": conv,
            "relationship": "close_out_payload_produced_by_conversation",
        }],
    )
    return identifier


def _parent(cop_id):
    return {
        "target_type": "close_out_payload", "target_id": cop_id,
        "relationship": "deposit_event_applies_close_out_payload",
    }


def test_table_omits_updated_and_deleted(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("deposit_events")}
    assert "deposit_event_updated_at" not in cols
    assert "deposit_event_deleted_at" not in cols
    assert "deposit_event_created_at" in cols
    assert len(cols) == 9


def test_success_drives_first_transition_and_back_references(v2_env):
    with session_scope() as s:
        cid = _ready_cop(s)
        d = dep.create_deposit_event(
            s, title="Apply", description="ok", outcome="success",
            records_summary={"sessions": 1}, apply_context={"runner": "test"},
            log_file_path="deposit-event-logs/dep_001.log",
            references=[
                _parent(cid),
                {"target_type": "session", "target_id": "SES-049",
                 "relationship": "deposit_event_wrote_record"},
            ],
        )
        assert d["deposit_event_identifier"] == "DEP-001"
        assert cop.get_close_out_payload(s, cid)["close_out_payload_status"] == "applied"
        # parent + one wrote_record edge created.
        wrote = [
            r for r in refs.list_from(
                s, source_type="deposit_event", source_id="DEP-001"
            )
            if r["relationship"] == "deposit_event_wrote_record"
        ]
        assert len(wrote) == 1


def test_error_info_conditional(v2_env):
    with session_scope() as s:
        _ready_cop(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        dep.create_deposit_event(
            s, title="t", description="d", outcome="success",
            records_summary={"sessions": 0}, apply_context={},
            log_file_path="deposit-event-logs/d.log", error_info={"x": 1},
            references=[_parent("COP-001")],
        )
    assert "success" in exc.value.errors[0].code
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        dep.create_deposit_event(
            s, title="t", description="d", outcome="failure",
            records_summary={"sessions": 0}, apply_context={},
            log_file_path="deposit-event-logs/d.log",
            references=[_parent("COP-001")],
        )
    assert "failure" in exc.value.errors[0].code


def test_parent_edge_required_and_single(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        dep.create_deposit_event(
            s, title="t", description="d", outcome="success",
            records_summary={"sessions": 0}, apply_context={},
            log_file_path="deposit-event-logs/d.log", references=[],
        )
    assert exc.value.errors[0].code == (
        "deposit_event_requires_applies_close_out_payload_edge"
    )


def test_records_summary_cross_check(v2_env):
    with session_scope() as s:
        _ready_cop(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        dep.create_deposit_event(
            s, title="t", description="d", outcome="success",
            records_summary={"sessions": 3}, apply_context={},
            log_file_path="deposit-event-logs/d.log", references=[_parent("COP-001")],
        )
    assert exc.value.errors[0].code == "records_summary_count_mismatch"


def test_failure_does_not_transition(v2_env):
    with session_scope() as s:
        cid = _ready_cop(s)
        dep.create_deposit_event(
            s, title="Failed", description="boom", outcome="failure",
            records_summary={"sessions": 0}, apply_context={"runner": "test"},
            error_info={"kind": "http_error", "message": "x", "step": "decisions"},
            log_file_path="deposit-event-logs/dep_001.log",
            references=[_parent(cid)],
        )
        assert cop.get_close_out_payload(s, cid)["close_out_payload_status"] == "ready"


def test_lazy_close_out_payload_creation(v2_env):
    with session_scope() as s:
        dep.create_deposit_event(
            s, title="Lazy", description="d", outcome="success",
            records_summary={"sessions": 0}, apply_context={"runner": "backfill_script"},
            log_file_path="deposit-event-logs/dep_001.log",
            references=[_parent("COP-099")],
        )
        lazy = cop.get_close_out_payload(s, "COP-099")
        assert lazy is not None
        assert lazy["close_out_payload_status"] == "applied"


def test_outcome_filter_and_descending_sort(v2_env):
    with session_scope() as s:
        c1 = _ready_cop(s, "COP-001")
        dep.create_deposit_event(
            s, title="A", description="d", outcome="success",
            records_summary={"sessions": 0}, apply_context={},
            log_file_path="deposit-event-logs/dep_001.log", references=[_parent(c1)],
        )
        dep.create_deposit_event(
            s, title="B", description="d", outcome="failure",
            records_summary={"sessions": 0}, apply_context={},
            error_info={"kind": "x", "message": "y", "step": "z"},
            log_file_path="deposit-event-logs/dep_002.log", references=[_parent(c1)],
        )
        assert len(dep.list_deposit_events(s, outcome="failure")) == 1
        ordered = dep.list_deposit_events(s)
        assert ordered[0]["deposit_event_identifier"] == "DEP-002"  # descending


def test_no_mutation_helpers_exposed(v2_env):
    # Born-terminal append-only: no update/patch/delete/restore functions.
    for name in ("update_deposit_event", "patch_deposit_event",
                 "delete_deposit_event", "restore_deposit_event"):
        assert not hasattr(dep, name)
