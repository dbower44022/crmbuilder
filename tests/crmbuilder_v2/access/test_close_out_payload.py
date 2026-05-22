"""Close-out payload repository tests — UI v0.7 Slice A."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import close_out_payloads as cop
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import workstreams as ws
from sqlalchemy import inspect


def _conv(s, identifier="CONV-001"):
    wid = ws.create_workstream(s, name="WS", purpose="p", description="d")[
        "workstream_identifier"
    ]
    return cr.create_conversation(
        s, title="C " + identifier, purpose="p", description="d",
        identifier=identifier,
        references=[{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    )["conversation_identifier"]


def _produced_edge(cop_id, conv_id):
    return {
        "source_type": "close_out_payload", "source_id": cop_id,
        "target_type": "conversation", "target_id": conv_id,
        "relationship": "close_out_payload_produced_by_conversation",
    }


def _make(s, identifier="COP-001", status="drafted", conv=None):
    conv = conv or _conv(s)
    return cop.create_close_out_payload(
        s, title="Payload " + identifier, description="d",
        file_path="close-out-payloads/ses_049.json",
        identifier=identifier, status=status,
        references=[_produced_edge(identifier, conv)],
    )


def test_table_has_thirteen_columns(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("close_out_payloads")}
    assert len(cols) == 13
    assert "close_out_payload_applied_at" in cols


def test_production_edge_required(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cop.create_close_out_payload(
            s, title="No producer", description="d",
            file_path="close-out-payloads/x.json",
        )
    assert exc.value.errors[0].code == "payload_requires_producing_conversation_edge"


def test_applied_requires_successful_deposit(v2_env):
    with session_scope() as s:
        _make(s, status="ready")
    # Direct PATCH to applied without a success deposit edge -> 422.
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cop.patch_close_out_payload(s, "COP-001", status="applied")
    assert exc.value.errors[0].code == (
        "applied_payload_requires_successful_deposit_event_edge"
    )


def test_terminal_and_supersession(v2_env):
    with session_scope() as s:
        c = _conv(s)
        _make(s, identifier="COP-001", conv=c)
        _make(s, identifier="COP-002", conv=c)
        cop.patch_close_out_payload(s, "COP-001", status="cancelled")
    with session_scope() as s, pytest.raises(StatusTransitionError):
        cop.patch_close_out_payload(s, "COP-001", status="ready")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cop.patch_close_out_payload(s, "COP-002", status="superseded")
    assert exc.value.errors[0].code == "superseded_payload_requires_successor_edge"


def test_lifecycle_timestamps_and_list_filter(v2_env):
    with session_scope() as s:
        _make(s, status="ready")
        assert cop.get_close_out_payload(s, "COP-001")["close_out_payload_ready_at"]
        assert len(cop.list_close_out_payloads(s, status="ready")) == 1


def test_soft_delete_restore(v2_env):
    with session_scope() as s:
        _make(s)
        cop.delete_close_out_payload(s, "COP-001")
        assert cop.get_close_out_payload(s, "COP-001") is None
        cop.restore_close_out_payload(s, "COP-001")
        assert cop.get_close_out_payload(s, "COP-001") is not None
