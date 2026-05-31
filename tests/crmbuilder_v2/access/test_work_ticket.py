"""Work ticket repository tests — UI v0.7 Slice A."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import sessions as sr
from crmbuilder_v2.access.repositories import work_tickets as wt
from crmbuilder_v2.access.repositories import projects as ws

_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _conv(s, identifier="CNV-001"):
    # Chain: workstream -> session (session_belongs_to_project) ->
    # conversation (conversation_belongs_to_session). Both parent edges are
    # mandatory under the PI-073 redesign.
    wid = ws.create_project(
        s, name="WS " + identifier, purpose="p", description="d"
    )["project_identifier"]
    # Explicit session identifier so the mandatory membership edge can name
    # the source before the row is server-assigned an id.
    sid = "SES-" + identifier.split("-", 1)[1]
    sr.create_session(
        s, title="S " + identifier, description="d", medium="chat",
        executive_summary=_EXEC_SUMMARY, identifier=sid,
        references=[{
            "source_type": "session", "source_id": sid,
            "target_type": "project", "target_id": wid,
            "relationship": "session_belongs_to_project",
        }],
    )
    return cr.create_conversation(
        s, title="C " + identifier, purpose="p", description="d",
        identifier=identifier,
        references=[{
            "source_type": "conversation", "source_id": identifier,
            "target_type": "session", "target_id": sid,
            "relationship": "conversation_belongs_to_session",
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


def _session_consume_edge(ses_id, wt_id):
    return {
        "source_type": "session", "source_id": ses_id,
        "target_type": "work_ticket", "target_id": wt_id,
        "relationship": "session_opens_against_work_ticket",
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


def test_consumed_accepts_session_opens_edge(v2_env):
    with session_scope() as s:
        _make(s)
        wt.patch_work_ticket(s, "WT-001", status="ready")
        # Build the session chain (workstream → session) without a conversation;
        # the PI-073 successor edge originates from the session itself.
        wid = ws.create_project(
            s, name="WS sess-consume", purpose="p", description="d"
        )["project_identifier"]
        sid = "SES-900"
        sr.create_session(
            s, title="S sess-consume", description="d", medium="chat",
            executive_summary=_EXEC_SUMMARY, identifier=sid,
            references=[{
                "source_type": "session", "source_id": sid,
                "target_type": "project", "target_id": wid,
                "relationship": "session_belongs_to_project",
            }],
        )
        wt.patch_work_ticket(
            s, "WT-001",
            status="consumed",
            references=[_session_consume_edge(sid, "WT-001")],
        )
        row = wt.get_work_ticket(s, "WT-001")
        assert row["work_ticket_status"] == "consumed"
        assert row["work_ticket_consumed_at"]


def test_single_use_violation(v2_env):
    with session_scope() as s:
        _make(s)
        c1 = _conv(s, "CNV-001")
        wt.patch_work_ticket(s, "WT-001", references=[_consume_edge(c1, "WT-001")])
        _conv(s, "CNV-002")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        wt.patch_work_ticket(s, "WT-001", references=[_consume_edge("CNV-002", "WT-001")])
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
