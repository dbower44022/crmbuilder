"""soft-delete decisions

Revision ID: 0002_soft_delete_decisions
Revises: 0001_initial_schema
Create Date: 2026-05-09

Adds 'Deleted' to the allowed decision statuses so that
decisions.delete() can soft-delete by status update instead of
physical removal. References pointing at the soft-deleted decision
continue to resolve through get(), preserving referential integrity
by construction.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002_soft_delete_decisions"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_constraint("ck_decision_status", type_="check")
        batch_op.create_check_constraint(
            "ck_decision_status",
            "status IN ('Active', 'Deleted', 'Superseded', 'Withdrawn')",
        )


def downgrade() -> None:
    # Pre-condition: no rows with status='Deleted'. The downgrade does
    # not auto-rewrite those rows; an operator must clean up first.
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_constraint("ck_decision_status", type_="check")
        batch_op.create_check_constraint(
            "ck_decision_status",
            "status IN ('Active', 'Superseded', 'Withdrawn')",
        )
