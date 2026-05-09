"""References repository tests (DEC-006 universal pattern)."""

from __future__ import annotations

import pytest

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import references


def _add(s, **kw):
    return references.create(
        s,
        source_type="session",
        source_id="SES-001",
        target_type="decision",
        target_id="DEC-001",
        relationship="decided_in",
        **kw,
    )


def test_create_and_list_from(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s:
        rows = references.list_from(s, source_type="session", source_id="SES-001")
    assert len(rows) == 1
    assert rows[0]["target_id"] == "DEC-001"
    assert rows[0]["relationship"] == "decided_in"


def test_unknown_relationship_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        references.create(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="vibes_with",
        )


def test_unknown_entity_type_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        references.create(
            s,
            source_type="alien",
            source_id="A",
            target_type="decision",
            target_id="DEC-001",
            relationship="is_about",
        )


def test_duplicate_reference_rejected(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s, pytest.raises(ConflictError):
        _add(s)


def test_list_to_and_touching(v2_env):
    with session_scope() as s:
        _add(s)
        references.create(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-002",
            relationship="decided_in",
        )
        references.create(
            s,
            source_type="decision",
            source_id="DEC-001",
            target_type="topic",
            target_id="TOPIC-001",
            relationship="is_about",
        )
    with session_scope() as s:
        to_dec1 = references.list_to(s, target_type="decision", target_id="DEC-001")
        touching = references.list_touching(
            s, entity_type="decision", entity_id="DEC-001"
        )
    assert len(to_dec1) == 1
    assert len(touching["as_source"]) == 1
    assert len(touching["as_target"]) == 1


def test_delete(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s:
        references.delete(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )
    with session_scope() as s, pytest.raises(NotFoundError):
        references.delete(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )


def test_upsert_idempotent(v2_env):
    with session_scope() as s:
        first = _add(s)
    with session_scope() as s:
        second = references.upsert(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )
    assert first["id"] == second["id"]


def test_delete_by_id_removes_row(v2_env):
    with session_scope() as s:
        created = _add(s)
    ref_id = created["id"]
    with session_scope() as s:
        before = references.delete_by_id(s, ref_id)
    assert before["id"] == ref_id
    with session_scope() as s, pytest.raises(NotFoundError):
        references.get(s, ref_id)


def test_delete_by_id_unknown_id_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        references.delete_by_id(s, 999_999)
