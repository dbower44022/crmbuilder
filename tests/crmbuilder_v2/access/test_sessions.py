"""Sessions repository tests.

Updated for the PI-073 / DEC-314 session redesign and the PI-074/PI-075
required ``session_executive_summary`` column. ``sessions.create()`` is the
removed pre-redesign shim; the live entry point is ``create_session()`` with
the medium-agnostic shape (title, description, medium, executive_summary,
[status, ...]). Every live session requires exactly one outbound
``session_belongs_to_workstream`` edge, supplied here via ``references``.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import sessions
from crmbuilder_v2.access.repositories import workstreams as ws

# A valid 200-800 char executive summary reused across fixtures.
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _ws(s, name="WS"):
    return ws.create_workstream(s, name=name, purpose="p", description="d")[
        "workstream_identifier"
    ]


def _member_edge(session_identifier, ws_id):
    return {
        "source_type": "session",
        "source_id": session_identifier,
        "target_type": "workstream",
        "target_id": ws_id,
        "relationship": "session_belongs_to_workstream",
    }


def _make(s, ws_id, identifier="SES-001", **kw):
    """Create a session in the new PI-073 shape with a workstream edge.

    Defaults to ``planned`` status (the only status that requires nothing
    beyond the membership edge). The membership edge is added automatically
    using ``identifier`` so callers only override what each test cares about.
    """
    extra_refs = kw.pop("references", [])
    payload = dict(
        identifier=identifier,
        title=kw.pop("title", f"{identifier} title"),
        description="d",
        medium="chat",
        status="planned",
        executive_summary=_EXEC_SUMMARY,
    )
    payload.update(kw)
    references = [_member_edge(payload["identifier"], ws_id)] + list(extra_refs)
    return sessions.create_session(s, references=references, **payload)


def test_create_and_get(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
    with session_scope() as s:
        row = sessions.get(s, "SES-001")
    # The pre-redesign ``summary`` field is removed; the audience-facing
    # ``session_executive_summary`` is its required successor.
    assert row["session_executive_summary"] == _EXEC_SUMMARY


def test_update_and_patch_methods_exist():
    """PI-073 / DEC-314 superseded the DEC-013 append-only rule.

    The legacy ``update`` name was never reintroduced; the redesign exposes
    ``update_session`` (full replace) and ``patch_session`` (partial).
    """
    assert not hasattr(sessions, "update")
    assert hasattr(sessions, "update_session")
    assert hasattr(sessions, "patch_session")


def test_invalid_status(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        wid = _ws(s)
        _make(s, wid, status="bogus")


def test_invalid_medium(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        wid = _ws(s)
        _make(s, wid, medium="carrier_pigeon")


def test_duplicate_identifier(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
    with session_scope() as s, pytest.raises(ConflictError):
        wid = _ws(s, name="WS2")
        _make(s, wid, identifier="SES-001", title="distinct title")


def test_list_with_limit(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
        _make(s, wid, identifier="SES-002")
    with session_scope() as s:
        rows = sessions.list_all(s, limit=1)
    assert len(rows) == 1
    # list_all orders by identifier ascending; first is the lowest.
    assert rows[0]["session_identifier"] == "SES-001"


def test_delete(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
    with session_scope() as s:
        sessions.delete(s, "SES-001")
    with session_scope() as s, pytest.raises(NotFoundError):
        sessions.get(s, "SES-001")


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    # The membership edge source_id must match the assigned identifier, so
    # resolve it via next_session_identifier before the create (the same
    # read-then-write pattern clients use against /sessions/next-identifier).
    with session_scope() as s:
        wid = _ws(s)
        nxt = sessions.next_session_identifier(s)
        row = sessions.create_session(
            s,
            title="Auto",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge(nxt, wid)],
        )
    assert row["session_identifier"] == "SES-001"
    with session_scope() as s:
        wid = _ws(s, name="WS2")
        nxt = sessions.next_session_identifier(s)
        row2 = sessions.create_session(
            s,
            title="Auto2",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge(nxt, wid)],
        )
    assert row2["session_identifier"] == "SES-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        row = sessions.create_session(
            s,
            identifier="SES-042",
            title="Explicit",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge("SES-042", wid)],
        )
    assert row["session_identifier"] == "SES-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        wid = _ws(s)
        sessions.create_session(
            s,
            identifier="SES-1",
            title="Bad",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge("SES-1", wid)],
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        wid = _ws(s)
        sessions.create_session(
            s,
            identifier="",
            title="Bad",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge("", wid)],
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
    with session_scope() as s, pytest.raises(ConflictError):
        wid = _ws(s, name="WS2")
        sessions.create_session(
            s,
            identifier="SES-001",
            title="Second",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge("SES-001", wid)],
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        wid = _ws(s)
        _make(s, wid, identifier="SES-001")
    # Force the first auto-assign candidate to collide with SES-001; the
    # savepoint-retry helper advances to SES-002. The membership edge is
    # applied after the row insert, so it targets the final identifier.
    monkeypatch.setattr(
        sessions, "next_session_identifier", lambda _s: "SES-001"
    )
    with session_scope() as s:
        wid = _ws(s, name="WS2")
        row = sessions.create_session(
            s,
            title="Second",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC_SUMMARY,
            references=[_member_edge("SES-002", wid)],
        )
    assert row["session_identifier"] == "SES-002"
