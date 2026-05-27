"""PI-074 — add executive_summary column to planning_items, decisions, sessions

Revision ID: 0020_pi_074_executive_summary
Revises: 0019_v0_5_entity_kind_and_variants
Create Date: 2026-05-27

PI-074 satisfier. Adds one TEXT NULL column ``executive_summary`` to
each of the three governance record types — ``planning_items``,
``decisions``, ``sessions`` — so a product manager or executive
reviewing the governance log can read the gist of every record
without parsing implementer-facing detail.

The column is nullable in this migration; PI-075 backfills the field
on all existing rows and adds the NOT NULL constraint in a follow-on
migration. A CHECK constraint enforces length 200..800 inclusive
*when the value is set*, so newly-authored records and re-edits land
inside the audience-readable length budget immediately; existing
rows carrying NULL pre-PI-075 backfill bypass the CHECK by the
``IS NULL OR`` short-circuit.

Operations, in order:

1. ``planning_items.executive_summary`` — TEXT NULL with CHECK
   ``ck_planning_executive_summary_length`` enforcing
   ``executive_summary IS NULL OR length(executive_summary) BETWEEN 200 AND 800``.
2. ``decisions.executive_summary`` — same column shape, CHECK
   ``ck_decision_executive_summary_length``.
3. ``sessions.executive_summary`` — same column shape, CHECK
   ``ck_session_executive_summary_length``.

Reversibility: ``downgrade()`` drops the CHECK and the column in
reverse order. Any executive_summary content authored before
downgrade is lost (documented behavior — this is a recovery
operation, not a routine reversal).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_pi_074_executive_summary"
down_revision: Union[str, None] = "0019_v0_5_entity_kind_and_variants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# CHECK admits NULL (deferred backfill per PI-075) or any TEXT whose
# length sits in [200, 800] inclusive. The length budget is the
# PI-074 audience-facing summary contract.
def _length_check(column: str) -> str:
    return (
        f"{column} IS NULL OR "
        f"(length({column}) >= 200 AND length({column}) <= 800)"
    )


def upgrade() -> None:
    # SQLite batch_alter_table copies the table and drops the original;
    # the drop trips FK enforcement on tables with self-FKs (decisions
    # has supersedes_id / superseded_by_id). FK enforcement is disabled
    # for the duration of every migration in migrations/env.py.

    # 1. planning_items
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("executive_summary", sa.Text(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_planning_executive_summary_length",
            _length_check("executive_summary"),
        )

    # 2. decisions
    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("executive_summary", sa.Text(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_decision_executive_summary_length",
            _length_check("executive_summary"),
        )

    # 3. sessions
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("executive_summary", sa.Text(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_session_executive_summary_length",
            _length_check("executive_summary"),
        )


def downgrade() -> None:
    """Drop the executive_summary column and its CHECK from the three tables.

    Any content authored under PI-074+ is lost. Per PI-074's
    reversibility posture this is a recovery operation, not a
    routine reversal; row content loss is documented behavior.
    """
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_session_executive_summary_length", type_="check"
        )
        batch_op.drop_column("executive_summary")

    with op.batch_alter_table("decisions", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_decision_executive_summary_length", type_="check"
        )
        batch_op.drop_column("executive_summary")

    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_planning_executive_summary_length", type_="check"
        )
        batch_op.drop_column("executive_summary")
