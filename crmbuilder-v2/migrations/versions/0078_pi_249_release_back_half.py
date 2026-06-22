"""PI-249 (PRJ-041 / REQ-295, Decision 3) — release_back_half column on releases.

Adds the durable per-release switch selecting which back half the scheduler runs the
development stage through: ``per_pi`` (legacy default) or ``per_area`` (the matrix).
A plain (non-batch) ``ADD COLUMN`` with a ``per_pi`` server default — so existing
rows get the legacy mode and the releases partial-unique lane index is preserved
(no table recreate). Column-exists guarded for the create_all-then-upgrade-head test
path. SQLite head 0077 -> 0078; companion PG ``migrations/pg/versions/0035_...``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0078_pi_249_release_back_half"
down_revision: str | None = "0077_pi_244_area_specs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # Back-fill only: the releases-create migration (0063) builds the table from the
    # ORM model, so a chain-upgraded DB already has release_back_half (+ its CHECK)
    # by the time we get here and this is a guarded no-op. The ADD matters for a DB
    # materialised before the model carried the column (e.g. the live v2-unified.db).
    if "release_back_half" not in _columns("releases"):
        op.add_column(
            "releases",
            sa.Column(
                "release_back_half", sa.String(16),
                nullable=False, server_default="per_pi",
            ),
        )


def downgrade() -> None:
    # No-op by design. On the chain the column is owned by 0063 (the model-based
    # releases create) and is removed when that table is dropped; here a DROP COLUMN
    # would fail anyway (SQLite refuses to drop a column referenced by the
    # ck_release_back_half CHECK). This migration only back-fills; it does not own
    # the column.
    pass
