"""Change-log emission tests."""

from __future__ import annotations

from crmbuilder_v2.access.change_log import current_actor, set_actor
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import ChangeLog
from crmbuilder_v2.access.repositories import decisions
from sqlalchemy import select

_VALID_EXEC_SUMMARY = "PI-102 test executive summary. " * 7


def test_insert_emits_change_log(v2_env):
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-001",
            title="t",
            decision_date="05-07-26",
            status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s:
        rows = s.scalars(select(ChangeLog).order_by(ChangeLog.id)).all()
    assert len(rows) == 1
    assert rows[0].entity_type == "decision"
    assert rows[0].entity_identifier == "DEC-001"
    assert rows[0].operation == "insert"
    assert rows[0].before_payload is None
    assert rows[0].after_payload is not None


def test_update_records_before_and_after(v2_env):
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-001",
            title="t",
            decision_date="05-07-26",
            status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
    with session_scope() as s:
        decisions.update(s, "DEC-001", status="Superseded")
    with session_scope() as s:
        rows = s.scalars(
            select(ChangeLog).where(ChangeLog.operation == "update")
        ).all()
    assert len(rows) == 1
    assert rows[0].before_payload["status"] == "Active"
    assert rows[0].after_payload["status"] == "Superseded"


def test_soft_delete_emits_status_update(v2_env):
    """Soft-delete records the status transition Active → Deleted as an update."""
    with session_scope() as s:
        decisions.create(
            s,
            identifier="DEC-001",
            title="t",
            decision_date="05-07-26",
            status="Active",
            executive_summary=_VALID_EXEC_SUMMARY,
        )
        decisions.delete(s, "DEC-001")
    with session_scope() as s:
        rows = s.scalars(
            select(ChangeLog)
            .where(ChangeLog.entity_identifier == "DEC-001")
            .order_by(ChangeLog.id)
        ).all()
    operations = [r.operation for r in rows]
    assert operations == ["insert", "update"]
    soft_delete = rows[1]
    assert soft_delete.before_payload["status"] == "Active"
    assert soft_delete.after_payload["status"] == "Deleted"


def test_actor_propagation(v2_env):
    set_actor("migration")
    try:
        assert current_actor() == "migration"
        with session_scope() as s:
            decisions.create(
                s,
                identifier="DEC-100",
                title="t",
                decision_date="05-07-26",
                status="Active",
                executive_summary=_VALID_EXEC_SUMMARY,
            )
        with session_scope() as s:
            row = s.scalars(
                select(ChangeLog).where(ChangeLog.entity_identifier == "DEC-100")
            ).one()
        assert row.actor == "migration"
    finally:
        set_actor("claude_session")
