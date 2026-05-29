"""PI-077 — add claimed_by / claimed_at columns to planning_items

Revision ID: 0025_pi_077_planning_item_claim
Revises: 0024_pi_076_planning_item_area
Create Date: 2026-05-29

PI-077 satisfier. Adds two nullable columns to ``planning_items`` so the
parallel-agent orchestrator (WS-012) can mark an item as "currently
being worked on by a specific agent" and guarantee two agents never grab
the same item at once.

* ``claimed_by`` — TEXT NULL. Holds the **conversation** identifier
  (``CONV-NNN``) of the agent holding the claim. The design-doc open
  question (orchestrator-planning.md §6) is resolved here in favour of
  the conversation identifier over the session identifier: under
  DEC-248 each child agent owns one conversation + one session, and the
  *conversation* is the unit of coherent work, so it is the semantically
  accurate claim-holder. Stored as a free-form string (no cross-table
  FK) because the column may, in principle, also carry a session
  identifier and SQLite identifier-column FKs add no real safety here.
* ``claimed_at`` — DATETIME NULL. When the claim was taken.

CHECK constraint ``ck_planning_claim_pairing`` enforces the both-or-
neither invariant: a row is either unclaimed (both NULL) or claimed
(both set). The atomic claim/release transitions live at the access
layer (``repositories/planning_items.py`` — ``claim_planning_item`` /
``release_planning_item``) with optimistic concurrency.

No backfill: existing rows stay unclaimed (both NULL).

Reversibility: ``downgrade()`` drops the CHECK and both columns. Any
live claims are lost on downgrade (documented — a recovery operation).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_pi_077_planning_item_claim"
down_revision: Union[str, None] = "0024_pi_076_planning_item_area"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CLAIM_PAIRING_CHECK = (
    "(claimed_by IS NULL AND claimed_at IS NULL) OR "
    "(claimed_by IS NOT NULL AND claimed_at IS NOT NULL)"
)


def upgrade() -> None:
    # FK enforcement is disabled for the duration of every migration in
    # migrations/env.py; SQLite batch_alter_table copies the table.
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("claimed_by", sa.String(length=64), nullable=True))
        batch_op.add_column(
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_planning_claim_pairing",
            _CLAIM_PAIRING_CHECK,
        )


def downgrade() -> None:
    """Drop the claim columns and their CHECK from planning_items.

    Any live claims are lost. Per PI-077's reversibility posture this is
    a recovery operation, not a routine reversal.
    """
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_planning_claim_pairing", type_="check")
        batch_op.drop_column("claimed_at")
        batch_op.drop_column("claimed_by")
