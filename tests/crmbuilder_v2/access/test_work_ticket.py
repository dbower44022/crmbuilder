"""Work ticket repository tests — UI v0.7 Slice A."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import work_tickets as wt
from crmbuilder_v2.access.repositories import workstreams as ws


def _conv(s, identifier="CONV-001"):
    wid = ws.create_workstream(
        s, name="WS " + identifier, purpose="p", description="d"
    )["workstream_identifier"]
    return cr.create_conversation(
        s, title="C " + identifier, purpose="p", description="d",
        identifier=identifier,
        references=[{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "workstream", "target_id": wid,
            "relationship": "conversation_belongs_to_workstream",
        }],
    )["conversation_identifier"]


def _make(s, title="WT A", kind="kickoff_prompt"):
    return wt.create_work_ticket(
        s, title=title, description="d", kind=kind, file_path="PRDs/k.md"
    )


def _consume_edge(conv_id, wt_id):
    return {
        "source_type": "conversation", "source_id": conv_id,
        "target_type": "work_ticket", "target_id": wt_id,
        "relationship": "conversation_opens_against_work_ticket",
    }


def test_kind_enum_and_file_path(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        _make(s, kind="bad_kind")
    with session_scope() as s, pytest.raises(UnprocessableError):
        wt.create_work_ticket(
            s, title="x", description="d", kind="other", file_path="/abs.md"
        )


def test_consumed_requires_edge(v2_env):
    with session_scope() as s:
        _make(s)
        wt.patch_work_ticket(s, "WT-001", status="ready")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        wt.patch_work_ticket(s, "WT-001", status="consumed")
    assert exc.value.errors[0].code == "consumed_work_ticket_requires_consumption_edge"
    with session_scope() as s:
        conv = _conv(s)
        wt.patch_work_ticket(
            s, "WT-001", status="consumed", references=[_consume_edge(conv, "WT-001")]
        )
        assert wt.get_work_ticket(s, "WT-001")["work_ticket_status"] == "consumed"
        assert wt.get_work_ticket(s, "WT-001")["work_ticket_consumed_at"]


def test_single_use_violation(v2_env):
    with session_scope() as s:
        _make(s)
        c1 = _conv(s, "CONV-001")
        wt.patch_work_ticket(s, "WT-001", references=[_consume_edge(c1, "WT-001")])
        _conv(s, "CONV-002")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        wt.patch_work_ticket(s, "WT-001", references=[_consume_edge("CONV-002", "WT-001")])
    assert exc.value.errors[0].code == "work_ticket_single_use_violation"


def test_terminal_and_supersession(v2_env):
    with session_scope() as s:
        _make(s, title="A")
        _make(s, title="B")  # WT-002
        wt.patch_work_ticket(s, "WT-001", status="cancelled")
    with session_scope() as s, pytest.raises(StatusTransitionError):
        wt.patch_work_ticket(s, "WT-001", status="superseded")
    with session_scope() as s, pytest.raises(UnprocessableError):
        wt.patch_work_ticket(s, "WT-002", status="superseded")
    with session_scope() as s:
        wt.patch_work_ticket(
            s, "WT-002", status="superseded",
            references=[{
                "source_type": "work_ticket", "source_id": "WT-002",
                "target_type": "work_ticket", "target_id": "WT-001",
                "relationship": "supersedes",
            }],
        )
        assert wt.get_work_ticket(s, "WT-002")["work_ticket_status"] == "superseded"


def test_list_filters_and_soft_delete(v2_env):
    with session_scope() as s:
        _make(s, title="A", kind="kickoff_prompt")
        _make(s, title="B", kind="claude_code_prompt")
        assert len(wt.list_work_tickets(s, kind="claude_code_prompt")) == 1
        wt.delete_work_ticket(s, "WT-001")
        assert wt.get_work_ticket(s, "WT-001") is None
        wt.restore_work_ticket(s, "WT-001")
        assert wt.get_work_ticket(s, "WT-001") is not None
