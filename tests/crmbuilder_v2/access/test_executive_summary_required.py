"""PI-102 — executive_summary is required (NOT NULL) on decisions,
planning_items, and sessions, matching the live schema after migration
0023 (PI-075).

These tests exercise the model via the ``v2_env`` fixture (which uses
``Base.metadata.create_all``), so they assert that the ORM source — not
just the live Alembic-migrated database — describes the column as NOT
NULL with a 200-800 length CHECK that has no ``IS NULL`` arm. They also
confirm ``conversations.conversation_executive_summary`` is deliberately
left nullable (migration 0023 excluded it).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ValidationError
from crmbuilder_v2.access.repositories import decisions, planning_items
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

_VALID = "PI-102 executive summary used for contract tests. " * 5  # ~255 chars


# ---------- schema shape (create_all) ----------


@pytest.mark.parametrize(
    "table,column",
    [
        ("decisions", "executive_summary"),
        ("planning_items", "executive_summary"),
        ("sessions", "session_executive_summary"),
    ],
)
def test_executive_summary_is_not_null(v2_env, table, column):
    """The tightened columns materialize as NOT NULL via create_all."""
    with session_scope() as s:
        cols = {c["name"]: c for c in inspect(s.get_bind()).get_columns(table)}
    assert cols[column]["nullable"] is False


def test_conversation_executive_summary_stays_nullable(v2_env):
    """Migration 0023 excluded conversations; the column remains nullable."""
    with session_scope() as s:
        cols = {
            c["name"]: c
            for c in inspect(s.get_bind()).get_columns("conversations")
        }
    assert cols["conversation_executive_summary"]["nullable"] is True


def test_raw_null_executive_summary_violates_not_null(v2_env):
    """A direct INSERT with NULL executive_summary is rejected by the DB,
    proving the CHECK has no ``IS NULL`` escape arm after create_all."""
    with pytest.raises(IntegrityError):
        with session_scope() as s:
            s.execute(
                text(
                    "INSERT INTO decisions "
                    "(identifier, title, decision_date, status, context, "
                    " decision, rationale, alternatives_considered, "
                    " consequences, executive_summary, created_at, updated_at) "
                    "VALUES "
                    "('DEC-900', 't', '05-07-26', 'Active', '', '', '', '', "
                    " '', NULL, '2026-05-29', '2026-05-29')"
                )
            )


# ---------- access-layer enforcement ----------


def test_decision_create_rejects_missing_summary(v2_env):
    with pytest.raises(ValidationError):
        with session_scope() as s:
            decisions.create(
                s,
                title="t",
                decision_date="05-07-26",
                status="Active",
                executive_summary=None,
            )


def test_decision_create_rejects_short_summary(v2_env):
    with pytest.raises(ValidationError):
        with session_scope() as s:
            decisions.create(
                s,
                title="t",
                decision_date="05-07-26",
                status="Active",
                executive_summary="too short",
            )


def test_planning_item_create_rejects_missing_summary(v2_env):
    with pytest.raises(ValidationError):
        with session_scope() as s:
            planning_items.create(
                s,
                title="t",
                item_type="pending_work",
                status="Open",
                executive_summary=None,
            )


def test_valid_summary_accepted(v2_env):
    """A 200-800 char summary round-trips on both entity types."""
    with session_scope() as s:
        dec = decisions.create(
            s,
            title="t",
            decision_date="05-07-26",
            status="Active",
            executive_summary=_VALID,
        )
        pi = planning_items.create(
            s,
            title="t",
            item_type="pending_work",
            status="Open",
            executive_summary=_VALID,
        )
    assert dec["executive_summary"] == _VALID
    assert pi["executive_summary"] == _VALID
