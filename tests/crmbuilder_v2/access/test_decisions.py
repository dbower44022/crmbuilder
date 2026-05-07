"""Decisions repository tests."""

from __future__ import annotations

import pytest

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import decisions


def _make(s, identifier="DEC-001", **kw):
    payload = dict(
        identifier=identifier,
        title=f"{identifier} title",
        decision_date="05-07-26",
        status="Active",
    )
    payload.update(kw)
    return decisions.create(s, **payload)


def test_create_and_get(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001", context="context", decision="do this")
    with session_scope() as s:
        row = decisions.get(s, "DEC-001")
    assert row["identifier"] == "DEC-001"
    assert row["context"] == "context"
    assert row["status"] == "Active"


def test_invalid_status_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, status="InvalidStatus")


def test_missing_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, identifier="")


def test_duplicate_identifier_rejects(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
    with session_scope() as s, pytest.raises(ConflictError):
        _make(s, identifier="DEC-001")


def test_update_status(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
    with session_scope() as s:
        decisions.update(s, "DEC-001", status="Superseded")
    with session_scope() as s:
        assert decisions.get(s, "DEC-001")["status"] == "Superseded"


def test_update_unknown_field_rejected(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
    with session_scope() as s, pytest.raises(ValidationError):
        decisions.update(s, "DEC-001", not_a_real_field="x")


def test_delete(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-099")
    with session_scope() as s:
        decisions.delete(s, "DEC-099")
    with session_scope() as s, pytest.raises(NotFoundError):
        decisions.get(s, "DEC-099")


def test_supersedes_chain(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002", supersedes="DEC-001")
        decisions.update(s, "DEC-001", superseded_by="DEC-002")
    with session_scope() as s:
        d1 = decisions.get(s, "DEC-001")
        d2 = decisions.get(s, "DEC-002")
    assert d1["superseded_by_identifier"] == "DEC-002"
    assert d2["supersedes_identifier"] == "DEC-001"


def test_supersedes_unknown_target_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        _make(s, identifier="DEC-001", supersedes="DEC-999")


def test_upsert_idempotent(v2_env):
    with session_scope() as s:
        decisions.upsert(
            s,
            identifier="DEC-007",
            title="Topics table",
            decision_date="05-06-26",
            status="Active",
            context="ctx",
        )
        decisions.upsert(
            s,
            identifier="DEC-007",
            title="Topics table",
            decision_date="05-06-26",
            status="Active",
            context="ctx",
        )
    with session_scope() as s:
        rows = decisions.list_all(s)
    assert len(rows) == 1
    assert rows[0]["identifier"] == "DEC-007"
