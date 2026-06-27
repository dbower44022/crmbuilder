"""PI-294 (PRJ-051 / REQ-331/332) — release_execution_mode column on releases.

Adds the durable per-release switch selecting how the release is driven through the
lanes: ``automated`` (default — the agent pipeline) or ``manual`` (a human driver
delivering the work by hand, with the post-freeze gates relaxed). A plain (non-batch)
``ADD COLUMN`` with an ``automated`` server default — so existing rows keep the
automated behaviour and the releases partial-unique lane index is preserved (no table
recreate). Column-exists guarded for the create_all-then-upgrade-head test path.
SQLite head 0093 -> 0094; companion PG ``migrations/pg/versions/0051_...``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0094_pi_294_release_execution_mode"
down_revision: str | None = "0093_pi_326_release_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # Back-fill only: the releases-create migration builds the table from the ORM
    # model, so a chain-upgraded DB already has release_execution_mode (+ its CHECK)
    # by the time we get here and this is a guarded no-op. The ADD matters for a DB
    # materialised before the model carried the column (e.g. the live v2-unified.db).
    if "release_execution_mode" not in _columns("releases"):
        op.add_column(
            "releases",
            sa.Column(
                "release_execution_mode", sa.String(16),
                nullable=False, server_default="automated",
            ),
        )


def downgrade() -> None:
    # No-op by design. On the chain the column is owned by the model-based releases
    # create and is removed when that table is dropped; here a DROP COLUMN would fail
    # anyway (SQLite refuses to drop a column referenced by the
    # ck_release_execution_mode CHECK). This migration only back-fills the column.
    pass
