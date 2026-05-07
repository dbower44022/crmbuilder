"""Sessions repository tests."""

from __future__ import annotations

import pytest

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
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
