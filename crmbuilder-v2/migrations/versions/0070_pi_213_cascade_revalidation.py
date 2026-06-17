"""PI-213 (PRJ-034) — area-reopen cascade re-validation columns.

Adds ``cascade_areas`` and ``revalidated_areas`` (JSON, the RW4 cascade) to
``area_reopens``. Both nullable with a server default of an empty JSON array; no
CHECK changes. Column-adds are guarded so the migration is a no-op on a
create_all-materialised DB (the test path). SQLite head 0069 -> 0070; companion PG
delta ``migrations/pg/versions/0027_pi_213_cascade_revalidation.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0070_pi_213_cascade_revalidation"
down_revision: str | None = "0069_pi_212_area_reopens"
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
    to_add = [c for c in _COLUMNS if c not in have]
    if not to_add:
        return
    with op.batch_alter_table("area_reopens") as batch:
        for col in to_add:
            batch.add_column(
                sa.Column(col, sa.JSON(), nullable=False, server_default="[]")
            )


def downgrade() -> None:
    have = _existing()
    to_drop = [c for c in _COLUMNS if c in have]
    if not to_drop:
        return
    with op.batch_alter_table("area_reopens") as batch:
        for col in to_drop:
            batch.drop_column(col)
