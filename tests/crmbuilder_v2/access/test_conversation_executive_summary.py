"""PI-105: conversation_executive_summary persists through create/patch/PUT.

Before PI-105 the API schema accepted conversation_executive_summary but the
access-layer create dropped it silently and the patch path rejected it
(unknown_field). These tests lock in that the field round-trips at every
write path and that the 200-800 length rule (nullable) is enforced.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ValidationError
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import projects as ws

_EXEC = "x" * 250
_EXEC2 = "y" * 300
_SHORT = "z" * 150
_LONG = "w" * 801
_SESSION_ID = "CONV-049"


def _member_edge(conv_id: str) -> dict:
    return {
        "source_type": "conversation",
        "source_id": conv_id,
        "target_type": "session",
        "target_id": _SESSION_ID,
        "relationship": "conversation_belongs_to_session",
    }


def _make_ws(s):
    ws.create_project(s, name="WS", purpose="p", description="d")


def _create(s, *, executive_summary=None, identifier="CNV-001"):
    return cr.create_conversation(
        s,
        title="Conv",
        purpose="p",
        description="d",
        identifier=identifier,
        executive_summary=executive_summary,
        references=[_member_edge(identifier)],
    )


def test_create_persists_executive_summary(v2_env):
    with session_scope() as s:
        _make_ws(s)
        _create(s, executive_summary=_EXEC)
        got = cr.get_conversation(s, "CNV-001")
        assert got["conversation_executive_summary"] == _EXEC


def test_create_without_executive_summary_is_null(v2_env):
    with session_scope() as s:
        _make_ws(s)
        _create(s)
        assert cr.get_conversation(s, "CNV-001")[
            "conversation_executive_summary"
        ] is None


def test_patch_sets_executive_summary(v2_env):
    with session_scope() as s:
        _make_ws(s)
        _create(s)
        cr.patch_conversation(s, "CNV-001", executive_summary=_EXEC2)
        assert cr.get_conversation(s, "CNV-001")[
            "conversation_executive_summary"
        ] == _EXEC2


def test_put_replaces_executive_summary(v2_env):
    with session_scope() as s:
        _make_ws(s)
        _create(s, executive_summary=_EXEC)
        cr.update_conversation(
            s,
            "CNV-001",
            title="Conv",
            purpose="p",
            description="d",
            executive_summary=_EXEC2,
        )
        assert cr.get_conversation(s, "CNV-001")[
            "conversation_executive_summary"
        ] == _EXEC2


@pytest.mark.parametrize("bad", [_SHORT, _LONG])
def test_create_rejects_out_of_range(v2_env, bad):
    with session_scope() as s, pytest.raises(ValidationError):
        _make_ws(s)
        _create(s, executive_summary=bad)


def test_patch_rejects_out_of_range(v2_env):
    with session_scope() as s:
        _make_ws(s)
        _create(s)
    with session_scope() as s, pytest.raises(ValidationError):
        cr.patch_conversation(s, "CNV-001", executive_summary=_SHORT)
