"""PI-076 — add area column to planning_items (multi-valued JSON, vocabulary-checked)

Revision ID: 0024_pi_076_planning_item_area
Revises: 0023_pi_075_executive_summary_not_null
Create Date: 2026-05-29

PI-076 satisfier. Adds one JSON column ``area`` to ``planning_items``
so each planning item can declare which areas of the codebase or
methodology it touches. The parallel-agent orchestrator (WS-012) uses
these labels to partition the open backlog into file-disjoint clusters
that can be dispatched to concurrent child agents without two agents
editing the same files (DEC-246 area-level parallelism; DEC-247
multi-valued area sets).

The column is **nullable** in this migration; PI-083 backfills ``area``
on every currently-open planning item and then tightens the column to
NOT NULL in a follow-on migration. Area is meaningful only for open
work the orchestrator might dispatch, so closed/resolved rows are not
required to carry it.

CHECK constraint ``ck_planning_area_nonempty_array`` enforces, *when the
value is set*, that ``area`` is a valid JSON array with at least one
element. The element-level vocabulary constraint (every element must be
a registered ``AREAS`` value) cannot be expressed in a SQLite CHECK —
CHECK constraints may not contain subqueries, so iterating ``json_each``
against the value set is impossible. Vocabulary membership is therefore
enforced at the access layer (``repositories/planning_items.py`` via
``crmbuilder_v2.access._helpers.validate_optional_value_list`` against
``crmbuilder_v2.access.vocab.AREAS``), which the PI-076 scope requires
independently. The DB CHECK is the structural belt; the
access-layer validator is the semantic braces.

Operations:

1. ``planning_items.area`` — JSON NULL with CHECK
   ``ck_planning_area_nonempty_array`` enforcing
   ``area IS NULL OR (json_valid(area) AND json_type(area) = 'array'
   AND json_array_length(area) >= 1)``.

Reversibility: ``downgrade()`` drops the CHECK and the column. Any area
content authored under PI-076+ is lost on downgrade (documented
behavior — a recovery operation, not a routine reversal).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_pi_076_planning_item_area"
down_revision: Union[str, None] = "0023_pi_075_executive_summary_not_null"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Structural CHECK: admit NULL (deferred backfill per PI-083) or a valid
# non-empty JSON array. Vocabulary membership is enforced at the access
# layer because SQLite CHECK constraints cannot iterate array elements
# (no subqueries).
_AREA_CHECK = (
    "area IS NULL OR ("
    "json_valid(area) AND json_type(area) = 'array' "
    "AND json_array_length(area) >= 1"
    ")"
)


def upgrade() -> None:
    # SQLite batch_alter_table copies the table; FK enforcement is
    # disabled for the duration of every migration in migrations/env.py.
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("area", sa.JSON(), nullable=True))
        batch_op.create_check_constraint(
            "ck_planning_area_nonempty_array",
            _AREA_CHECK,
        )


def downgrade() -> None:
    """Drop the area column and its CHECK from planning_items.

    Any area content authored under PI-076+ is lost. Per PI-076's
    reversibility posture this is a recovery operation, not a routine
    reversal; row content loss is documented behavior.
    """
    with op.batch_alter_table("planning_items", schema=None) as batch_op:
        batch_op.drop_constraint(
            "ck_planning_area_nonempty_array", type_="check"
        )
        batch_op.drop_column("area")
