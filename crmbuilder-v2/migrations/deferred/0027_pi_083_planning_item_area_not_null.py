"""PI-083 — tighten planning_items.area to NOT NULL (DEFERRED)

Revision ID: 0027_pi_083_planning_item_area_not_null
Revises: 0026_pi_078_identifier_reservations
Create Date: 2026-05-29

!!! DEFERRED — DO NOT MOVE INTO migrations/versions/ UNTIL THE AREA
    BACKFILL HAS COMPLETED. !!!

This file lives under ``migrations/deferred/`` (which Alembic does NOT
scan) on purpose. PI-076 added ``planning_items.area`` as nullable and
deferred the NOT NULL tightening to PI-083 because every existing row
starts with ``area = NULL``. Applying this migration before
``scripts/backfill_pi_083_area.py`` has given every Open planning item an
area would fail (NOT NULL violation) and would block the whole migration
chain.

Activation procedure (after backfill):

1. Confirm no NULL areas remain on rows that must carry one. Note: PI-076
   deferred NOT NULL precisely because closed/resolved rows were never
   required to have an area. If any historical Resolved/Deferred rows
   still carry NULL, either backfill them too or keep the column nullable
   — decide at activation time. The safest tightening only proceeds when
   *all* rows have a non-null area.
2. ``git mv crmbuilder-v2/migrations/deferred/0027_pi_083_planning_item_area_not_null.py``
   ``crmbuilder-v2/migrations/versions/``
3. ``uv run alembic upgrade head`` (or ``run_engagement_migrations`` for
   the live engagement DB).

The SQLite ``batch_alter_table`` recreates the table with the column
redefined NOT NULL while preserving the existing CHECK.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_pi_083_planning_item_area_not_null"
down_revision: Union[str, None] = "0026_pi_078_identifier_reservations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guard: refuse to tighten while any NULL area remains, with a clear
    # message rather than an opaque NOT NULL violation mid-rebuild.
    bind = op.get_bind()
    null_count = bind.execute(
        sa.text("SELECT COUNT(*) FROM planning_items WHERE area IS NULL")
    ).scalar()
    if null_count:
        raise RuntimeError(
            f"{null_count} planning_items still have area IS NULL; run "
            "scripts/backfill_pi_083_area.py before applying this migration."
        )
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.alter_column("area", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.alter_column("area", existing_type=sa.JSON(), nullable=True)
