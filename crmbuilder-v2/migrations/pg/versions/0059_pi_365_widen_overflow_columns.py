"""PI-365 (REQ-425, PG) — widen four VARCHAR columns that overran on Postgres.

Companion to the SQLite-chain ``0102``. Four columns hold live data longer than
their declared VARCHAR length (SQLite never enforced it, Postgres does), which
blocked the SQLite→PG cutover: ``planning_items.resolution_reference``,
``refs.source_id``, ``refs.target_id`` (all VARCHAR(64)), and
``artifact_versions.artifact_identifier`` (VARCHAR(32)). Widen each to ``TEXT``.
The model now declares them ``Text`` too, so a fresh ``create_all`` PG already
builds them wide; this ALTER brings an existing PG to the same shape.

PG chain head 0058 -> 0059.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_pi_365_widen_overflow_columns"
down_revision: str | None = "0058_pi_364_project_run_claim"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WIDEN = [
    ("planning_items", "resolution_reference"),
    ("refs", "source_id"),
    ("refs", "target_id"),
    ("artifact_versions", "artifact_identifier"),
]


def upgrade() -> None:
    for table, column in _WIDEN:
        op.alter_column(table, column, type_=sa.Text())


def downgrade() -> None:
    op.alter_column("artifact_versions", "artifact_identifier", type_=sa.String(32))
    op.alter_column("refs", "target_id", type_=sa.String(64))
    op.alter_column("refs", "source_id", type_=sa.String(64))
    op.alter_column("planning_items", "resolution_reference", type_=sa.String(64))
