"""Sessions repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import sessions


def _make(s, identifier="SES-001", **kw):
    payload = dict(
        identifier=identifier,
        title=f"{identifier} title",
        session_date="05-07-26",
        status="Complete",
    )
    payload.update(kw)
    return sessions.create(s, **payload)


def test_create_and_get(v2_env):
    with session_scope() as s:
        _make(s, identifier="SES-001", summary="hi")
    with session_scope() as s:
        row = sessions.get(s, "SES-001")
    assert row["summary"] == "hi"


def test_no_update_method():
    """Append-only per DEC-013: there is no update method."""
    assert not hasattr(sessions, "update")


def test_invalid_status(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, status="bogus")


def test_duplicate_identifier(v2_env):
    with session_scope() as s:
        _make(s, identifier="SES-001")
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, identifier="SES-001")


def test_list_with_limit(v2_env):
    with session_scope() as s:
        _make(s, identifier="SES-001", session_date="05-01-26")
        _make(s, identifier="SES-002", session_date="05-07-26")
    with session_scope() as s:
        rows = sessions.list_all(s, limit=1)
    assert len(rows) == 1
    # Most recent first.
    assert rows[0]["identifier"] == "SES-002"


def test_delete(v2_env):
    with session_scope() as s:
        _make(s, identifier="SES-001")
    with session_scope() as s:
        sessions.delete(s, "SES-001")
    with session_scope() as s, pytest.raises(NotFoundError):
        sessions.get(s, "SES-001")


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = sessions.create(
            s, title="Auto", session_date="05-25-26", status="Complete"
        )
    assert row["identifier"] == "SES-001"
    with session_scope() as s:
        row2 = sessions.create(
            s, title="Auto2", session_date="05-25-26", status="Complete"
        )
    assert row2["identifier"] == "SES-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = sessions.create(
            s, identifier="SES-042", title="Explicit",
            session_date="05-25-26", status="Complete",
        )
    assert row["identifier"] == "SES-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        sessions.create(
            s, identifier="SES-1", title="Bad",
            session_date="05-25-26", status="Complete",
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        sessions.create(
            s, identifier="", title="Bad",
            session_date="05-25-26", status="Complete",
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        _make(s, identifier="SES-001")
    with session_scope() as s, pytest.raises(ConflictError):
        sessions.create(
            s, identifier="SES-001", title="Second",
            session_date="05-25-26", status="Complete",
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        _make(s, identifier="SES-001")
    monkeypatch.setattr(sessions, "compute_next_identifier", lambda _s: "SES-001")
    with session_scope() as s:
        row = sessions.create(
            s, title="Second", session_date="05-25-26", status="Complete"
        )
    assert row["identifier"] == "SES-002"
