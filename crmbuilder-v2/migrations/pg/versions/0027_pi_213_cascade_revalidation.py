"""PI-213 (PG chain) — area-reopen cascade re-validation columns.

Companion to the SQLite-chain ``0070``. Adds ``cascade_areas`` and
``revalidated_areas`` (JSONB) to ``area_reopens`` on Postgres deployments
materialised from an earlier baseline. Column-adds are guarded (no-op when
create_all already made them). Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0027_pi_213_cascade_revalidation"
down_revision: str | None = "0026_pi_212_area_reopens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("cascade_areas", "revalidated_areas")


def _existing() -> set[str]:
    insp = sa.inspect(op.get_bind())
    if "area_reopens" not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns("area_reopens")}


def upgrade() -> None:
    have = _existing()
    for col in (c for c in _COLUMNS if c not in have):
        op.add_column(
            "area_reopens",
            sa.Column(col, JSONB(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    have = _existing()
    for col in (c for c in _COLUMNS if c in have):
        op.drop_column("area_reopens", col)
