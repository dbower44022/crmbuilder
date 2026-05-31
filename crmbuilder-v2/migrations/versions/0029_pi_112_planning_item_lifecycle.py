"""PI-112 Phase 3 — Planning Item six-state lifecycle

Revision ID: 0029_pi_112_planning_item_lifecycle
Revises: 0028_pi_112_area_two_tier
Create Date: 2026-05-30

DEC-346. Replaces the Open/Resolved/Deferred status set with the phase-agnostic
six-state lifecycle (Draft, Decomposed, Ready, In Progress, In Review, Resolved)
plus the Deferred and Cancelled terminals. Legacy ``Open`` maps to ``Draft``.

Operations (CHECK dropped around the data rewrite — the old CHECK forbids
``Draft`` and the new one forbids ``Open``, so neither can be in force while
the data is mid-rewrite):
  1. drop ``ck_planning_status``
  2. ``UPDATE planning_items SET status='Draft' WHERE status='Open'``
  3. recreate ``ck_planning_status`` with the eight-value set

Reversible: ``downgrade`` collapses any non-{Resolved, Deferred} status back to
``Open`` (a recovery mapping — items that progressed past Draft lose their
finer state, documented like prior data-bearing reversals) and restores the
three-value CHECK.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_pi_112_planning_item_lifecycle"
down_revision: Union[str, None] = "0028_pi_112_area_two_tier"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_CHECK = (
    "status IN ('Cancelled', 'Decomposed', 'Deferred', 'Draft', "
    "'In Progress', 'In Review', 'Ready', 'Resolved')"
)
_OLD_CHECK = "status IN ('Deferred', 'Open', 'Resolved')"


def upgrade() -> None:
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_planning_status", type_="check")
    op.get_bind().execute(
        sa.text("UPDATE planning_items SET status = 'Draft' WHERE status = 'Open'")
    )
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_planning_status", _NEW_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint("ck_planning_status", type_="check")
    op.get_bind().execute(
        sa.text(
            "UPDATE planning_items SET status = 'Open' "
            "WHERE status NOT IN ('Resolved', 'Deferred')"
        )
    )
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_planning_status", _OLD_CHECK)
