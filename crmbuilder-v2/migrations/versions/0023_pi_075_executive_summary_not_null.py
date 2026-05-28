"""PI-075 — tighten executive_summary to NOT NULL on planning_items, decisions, sessions

Revision ID: 0023_pi_075_executive_summary_not_null
Revises: 0022_pi_080_conversation_orchestrates_conversation
Create Date: 2026-05-27

PI-074 deferred the NOT NULL tightening to PI-075 pending row-level
backfill. PI-096 / PI-097 / PI-098 (executed via SES-102 and SES-104,
resolved via SES-106) delivered the backfill: every live row in
``planning_items``, ``decisions``, and ``sessions`` now carries a
200..800 char executive_summary. The trailing soft-deleted decision
(DEC-312, the Cross Domain Service direct-POST orphan from SES-094)
was also backfilled inline at SES-108 authoring time. With every row
populated, this migration switches the column to NOT NULL.

Tables tightened:

  planning_items.executive_summary           → NOT NULL
  decisions.executive_summary                → NOT NULL
  sessions.session_executive_summary         → NOT NULL

The matching 200..800 length CHECK from PI-074 / PI-073 stays in
place. The CHECK now reads ``length(...) BETWEEN 200 AND 800`` (no
``IS NULL OR`` branch needed) for the three tightened columns; for
clarity the existing CHECK constraint is dropped and replaced with
the stricter form during the same batch operation.

The ``conversations.conversation_executive_summary`` field (added by
PI-073 Phase A as a carry-over of the PI-074 column under the
redesigned conversation entity) is NOT tightened in this migration.
Conversations have not yet been backfilled — many of the migrated
SES-NNN-as-conversation rows have NULL conversation_executive_summary
because the legacy session they came from didn't carry one. A
separate PI captures that work whenever someone picks it up.

Downgrade reverses the tightening: drops the NOT NULL constraint,
restores the original "IS NULL OR length BETWEEN 200 AND 800" CHECK
on all three columns. Lossless.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0023_pi_075_executive_summary_not_null"
down_revision: Union[str, None] = "0022_pi_080_conversation_orchestrates_conversation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # planning_items
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.alter_column(
            "executive_summary",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.drop_constraint(
            "ck_planning_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_planning_executive_summary_length",
            "length(executive_summary) >= 200 "
            "AND length(executive_summary) <= 800",
        )

    # decisions
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.alter_column(
            "executive_summary",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.drop_constraint(
            "ck_decision_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_decision_executive_summary_length",
            "length(executive_summary) >= 200 "
            "AND length(executive_summary) <= 800",
        )

    # sessions (post-PI-073 column name is session_executive_summary)
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.alter_column(
            "session_executive_summary",
            existing_type=sa.Text(),
            nullable=False,
        )
        batch_op.drop_constraint(
            "ck_session_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_session_executive_summary_length",
            "length(session_executive_summary) >= 200 "
            "AND length(session_executive_summary) <= 800",
        )


def downgrade() -> None:
    # Reverse the tightening. Drop the NOT NULL and restore the
    # original "IS NULL OR length BETWEEN ..." CHECK shape from
    # PI-074 / PI-073 Phase A.

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_session_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_session_executive_summary_length",
            "session_executive_summary IS NULL OR "
            "(length(session_executive_summary) >= 200 "
            "AND length(session_executive_summary) <= 800)",
        )
        batch_op.alter_column(
            "session_executive_summary",
            existing_type=sa.Text(),
            nullable=True,
        )

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_decision_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_decision_executive_summary_length",
            "executive_summary IS NULL OR "
            "(length(executive_summary) >= 200 "
            "AND length(executive_summary) <= 800)",
        )
        batch_op.alter_column(
            "executive_summary",
            existing_type=sa.Text(),
            nullable=True,
        )

    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_planning_executive_summary_length", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_planning_executive_summary_length",
            "executive_summary IS NULL OR "
            "(length(executive_summary) >= 200 "
            "AND length(executive_summary) <= 800)",
        )
        batch_op.alter_column(
            "executive_summary",
            existing_type=sa.Text(),
            nullable=True,
        )
