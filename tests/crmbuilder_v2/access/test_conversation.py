"""Conversation repository tests — PI-073 / DEC-314 redesign.

Under the redesign a ``conversation`` (``CNV-NNN``) is a topical sub-unit
nested within a ``session``. Mandatory parent linkage is a single
``conversation_belongs_to_session`` edge required at every live status
(not deferred to ``complete`` as the legacy v0.7 model did). The lifecycle
is the six-status ``planned → in_flight`` forward path plus the
``complete`` / ``cancelled`` / ``not_started`` / ``superseded`` terminals.
"""

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

# A session identifier the conversations are nested within. The references
# layer does not require the target row to exist, so a stable literal is
# sufficient to satisfy the mandatory membership edge.
_SESSION_ID = "CONV-049"


def _ws(s):
    return ws.create_workstream(s, name="WS", purpose="p", description="d")[
        "workstream_identifier"
    ]


def _member_edge(conv_id, session_id=_SESSION_ID):
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "session",
        "target_id": session_id,
        "relationship": "conversation_belongs_to_session",
    }


def _conv(s, ws_id, title="Conv A", identifier="CNV-001", status="planned", refs=None):
    references = [_member_edge(identifier)] + (refs or [])
    return cr.create_conversation(
        s, title=title, purpose="p", description="d",
        identifier=identifier, status=status, references=references,
    )


def test_table_has_sixteen_columns(v2_env):
    cols = {c["name"] for c in inspect(get_engine()).get_columns("conversations")}
    assert len(cols) == 16
    assert "conversation_executive_summary" in cols


def test_membership_required(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cr.create_conversation(s, title="No session", purpose="p", description="d")
    assert exc.value.errors[0].code == "missing_session_membership_edge"


def test_forward_only_lifecycle(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid)
        cr.patch_conversation(s, "CNV-001", status="in_flight")
        assert cr.get_conversation(s, "CNV-001")[
            "conversation_in_flight_at"
        ]
    with session_scope() as s, pytest.raises(StatusTransitionError):
        cr.patch_conversation(s, "CNV-001", status="planned")  # regression


def test_complete_keeps_membership_edge(v2_env):
    # Under the redesign there is no "complete-requires-session-edge" rule:
    # the conversation_belongs_to_session edge is mandatory from create, so a
    # conversation that already carries it advances to complete directly.
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid)
        cr.patch_conversation(s, "CNV-001", status="in_flight")
    with session_scope() as s:
        cr.patch_conversation(s, "CNV-001", status="complete")
        assert cr.get_conversation(s, "CNV-001")["conversation_status"] == "complete"


def test_supersession_requires_edge(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="A", identifier="CNV-001")
        _conv(s, wid, title="B", identifier="CNV-002")
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        cr.patch_conversation(s, "CNV-001", status="superseded")
    assert exc.value.errors[0].code == "supersession_requires_successor_edge"
    with session_scope() as s:
        cr.patch_conversation(
            s, "CNV-001", status="superseded",
            references=[{
                "source_type": "conversation", "source_id": "CNV-001",
                "target_type": "conversation", "target_id": "CNV-002",
                "relationship": "supersedes",
            }],
        )
        assert cr.get_conversation(s, "CNV-001")["conversation_status"] == "superseded"


def test_list_filters(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="A", identifier="CNV-001")
        _conv(s, wid, title="B", identifier="CNV-002")
        cr.patch_conversation(s, "CNV-001", status="in_flight")
        assert len(cr.list_conversations(s, session_identifier=_SESSION_ID)) == 2
        assert len(cr.list_conversations(s, status="in_flight")) == 1


def test_title_uniqueness_and_soft_delete(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _conv(s, wid, title="Dup", identifier="CNV-001")
    with session_scope() as s, pytest.raises(UnprocessableError):
        cr.create_conversation(
            s, title="dup", purpose="p", description="d", identifier="CNV-002",
            references=[_member_edge("CNV-002")],
        )
    with session_scope() as s:
        cr.delete_conversation(s, "CNV-001")
        assert cr.get_conversation(s, "CNV-001") is None
        cr.restore_conversation(s, "CNV-001")
        assert cr.get_conversation(s, "CNV-001") is not None
