"""Conversation repository tests — UI v0.7 Slice A."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import get_engine, session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import workstreams as ws
from sqlalchemy import inspect


def _ws(s):
    return ws.create_workstream(s, name="WS", purpose="p", description="d")[
        "workstream_identifier"
    ]


def _member_edge(conv_id, ws_id):
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "workstream",
        "target_id": ws_id,
        "relationship": "conversation_belongs_to_workstream",
    }


def _conv(s, ws_id, title="Conv A", identifier="CONV-001", status="planned", refs=None):
    references = [_member_edge(identifier, ws_id)] + (refs or [])
    return cr.create_conversation(
        s, title=title, purpose="p", description="d",
        identifier=identifier, status=status, references=references,
    )


def test_table_has_fifteen_columns(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("conversations")}
    assert len(cols) == 15
    assert "conversation_kickoff_drafted_at" in cols


def test_membership_required(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cr.create_conversation(s, title="No WS", purpose="p", description="d")
    assert exc.value.errors[0].code == "missing_workstream_membership_edge"


def test_forward_only_planning_lifecycle(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid)
        cr.patch_conversation(s, "CONV-001", status="kickoff_drafted")
        assert cr.get_conversation(s, "CONV-001")[
            "conversation_kickoff_drafted_at"
        ]
    with session_scope() as s, pytest.raises(StatusTransitionError):
        cr.patch_conversation(s, "CONV-001", status="planned")  # regression


def test_complete_requires_session_edge(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid)
        for st in ("kickoff_drafted", "ready", "in_flight"):
            cr.patch_conversation(s, "CONV-001", status=st)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cr.patch_conversation(s, "CONV-001", status="complete")
    assert exc.value.errors[0].code == "complete_conversation_requires_session_edge"
    with session_scope() as s:
        cr.patch_conversation(
            s, "CONV-001", status="complete",
            references=[{
                "source_type": "conversation", "source_id": "CONV-001",
                "target_type": "session", "target_id": "SES-049",
                "relationship": "conversation_records_session",
            }],
        )
        assert cr.get_conversation(s, "CONV-001")["conversation_status"] == "complete"


def test_supersession_requires_edge(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="A", identifier="CONV-001")
        _conv(s, wid, title="B", identifier="CONV-002")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cr.patch_conversation(s, "CONV-001", status="superseded")
    assert exc.value.errors[0].code == "supersession_requires_successor_edge"
    with session_scope() as s:
        cr.patch_conversation(
            s, "CONV-001", status="superseded",
            references=[{
                "source_type": "conversation", "source_id": "CONV-001",
                "target_type": "conversation", "target_id": "CONV-002",
                "relationship": "supersedes",
            }],
        )
        assert cr.get_conversation(s, "CONV-001")["conversation_status"] == "superseded"


def test_list_filters(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="A", identifier="CONV-001")
        _conv(s, wid, title="B", identifier="CONV-002")
        cr.patch_conversation(s, "CONV-001", status="kickoff_drafted")
        assert len(cr.list_conversations(s, workstream_identifier=wid)) == 2
        assert len(cr.list_conversations(s, status="kickoff_drafted")) == 1


def test_title_uniqueness_and_soft_delete(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="Dup", identifier="CONV-001")
    with session_scope() as s, pytest.raises(UnprocessableError):
        cr.create_conversation(
            s, title="dup", purpose="p", description="d", identifier="CONV-002",
            references=[_member_edge("CONV-002", "WS-001")],
        )
    with session_scope() as s:
        cr.delete_conversation(s, "CONV-001")
        assert cr.get_conversation(s, "CONV-001") is None
        cr.restore_conversation(s, "CONV-001")
        assert cr.get_conversation(s, "CONV-001") is not None
