"""Decisions repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import decisions

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def _make(s, identifier="DEC-001", **kw):
    payload = dict(
        identifier=identifier,
        title=f"{identifier} title",
        decision_date="05-07-26",
        status="Active",
        executive_summary=_VALID_EXEC_SUMMARY,
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


def test_delete_is_soft(v2_env):
    """delete() sets status='Deleted' rather than physically removing the row.

    The row stays in the database (so references continue to resolve via
    get()). list_all() filters it out by default.
    """
    with session_scope() as s:
        _make(s, identifier="DEC-099")
    with session_scope() as s:
        decisions.delete(s, "DEC-099")
    with session_scope() as s:
        row = decisions.get(s, "DEC-099")
    assert row["status"] == "Deleted"
    assert row["identifier"] == "DEC-099"


def test_list_all_excludes_deleted_by_default(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002")
        decisions.delete(s, "DEC-002")
    with session_scope() as s:
        visible = decisions.list_all(s)
    assert [r["identifier"] for r in visible] == ["DEC-001"]


def test_list_all_include_deleted_returns_everything(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002")
        decisions.delete(s, "DEC-002")
    with session_scope() as s:
        all_rows = decisions.list_all(s, include_deleted=True)
    assert {r["identifier"] for r in all_rows} == {"DEC-001", "DEC-002"}
    statuses = {r["identifier"]: r["status"] for r in all_rows}
    assert statuses["DEC-002"] == "Deleted"


def test_get_returns_deleted_row(v2_env):
    """get() does not filter — references can still resolve a soft-deleted decision."""
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        decisions.delete(s, "DEC-001")
    with session_scope() as s:
        row = decisions.get(s, "DEC-001")
    assert row["status"] == "Deleted"


def test_redelete_is_idempotent(v2_env):
    """Deleting an already-Deleted row is a no-op (no extra change_log entry)."""
    from crmbuilder_v2.access.models import ChangeLog
    from sqlalchemy import select

    with session_scope() as s:
        _make(s, identifier="DEC-001")
    with session_scope() as s:
        decisions.delete(s, "DEC-001")
    with session_scope() as s:
        decisions.delete(s, "DEC-001")
    with session_scope() as s:
        rows = s.scalars(
            select(ChangeLog)
            .where(ChangeLog.entity_identifier == "DEC-001")
            .order_by(ChangeLog.id)
        ).all()
    operations = [r.operation for r in rows]
    assert operations == ["insert", "update"], (
        "expected insert + one update (the soft-delete); the second "
        "delete should be a no-op, not emit another change_log entry"
    )


def test_supersedes_resolves_after_target_soft_deleted(v2_env):
    """References pointing at a soft-deleted decision still resolve."""
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002", supersedes="DEC-001")
        decisions.delete(s, "DEC-001")
    with session_scope() as s:
        d2 = decisions.get(s, "DEC-002")
    assert d2["supersedes_identifier"] == "DEC-001"


def test_update_supersedes_empty_string_clears_fk(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002", supersedes="DEC-001")
    with session_scope() as s:
        decisions.update(s, "DEC-002", supersedes="")
    with session_scope() as s:
        row = decisions.get(s, "DEC-002")
    assert row["supersedes_identifier"] is None


def test_update_supersedes_identifier_sets_fk(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002")
    with session_scope() as s:
        decisions.update(s, "DEC-002", supersedes="DEC-001")
    with session_scope() as s:
        row = decisions.get(s, "DEC-002")
    assert row["supersedes_identifier"] == "DEC-001"


def test_update_supersedes_none_does_not_touch_fk(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
        _make(s, identifier="DEC-002", supersedes="DEC-001")
    with session_scope() as s:
        decisions.update(s, "DEC-002", supersedes=None, status="Active")
    with session_scope() as s:
        row = decisions.get(s, "DEC-002")
    assert row["supersedes_identifier"] == "DEC-001"


def test_update_supersedes_unknown_identifier_raises(v2_env):
    with session_scope() as s:
        _make(s, identifier="DEC-001")
    with session_scope() as s, pytest.raises(ValidationError):
        decisions.update(s, "DEC-001", supersedes="DEC-DOES-NOT-EXIST")


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


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = decisions.create(
            s, title="Auto", decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "DEC-001"
    with session_scope() as s:
        row2 = decisions.create(
            s, title="Auto2", decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row2["identifier"] == "DEC-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = decisions.create(
            s, identifier="DEC-042", title="Explicit",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "DEC-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        decisions.create(
            s, identifier="DEC-1", title="Bad",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_create_with_empty_string_identifier_rejected(v2_env):
    """Empty string is distinct from omitted (None) — it fails format."""
    with session_scope() as s, pytest.raises(UnprocessableError):
        decisions.create(
            s, identifier="", title="Bad",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        decisions.create(
            s, identifier="DEC-001", title="First",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s, pytest.raises(ConflictError):
        decisions.create(
            s, identifier="DEC-001", title="Second",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    """Pre-create DEC-001, force compute_next_identifier to return it
    anyway, and verify the SAVEPOINT-retry helper lands on DEC-002."""
    with session_scope() as s:
        decisions.create(
            s, identifier="DEC-001", title="First",
            decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    monkeypatch.setattr(decisions, "compute_next_identifier", lambda _s: "DEC-001")
    with session_scope() as s:
        row = decisions.create(
            s, title="Second", decision_date="05-25-26", status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    assert row["identifier"] == "DEC-002"


def test_upsert_idempotent(v2_env):
    with session_scope() as s:
        decisions.upsert(
            s,
            identifier="DEC-007",
            title="Topics table",
            decision_date="05-06-26",
            status="Active",
            context="ctx",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
        decisions.upsert(
            s,
            identifier="DEC-007",
            title="Topics table",
            decision_date="05-06-26",
            status="Active",
            context="ctx",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s:
        rows = decisions.list_all(s)
    assert len(rows) == 1
    assert rows[0]["identifier"] == "DEC-007"
