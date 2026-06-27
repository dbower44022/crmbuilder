"""PI-294 (PG chain) — release_execution_mode column on releases.

Companion to the SQLite-chain ``0094``. Adds the per-release execution-mode switch
(``automated`` default / ``manual``) on Postgres deployments materialised from an
earlier baseline. The PG baseline is ``create_all`` from the live models, so a fresh
PG DB already carries it — the add is column-exists-guarded. Never replay the SQLite
chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_pi_294_release_execution_mode"
down_revision: str | None = "0050_pi_326_release_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    # Back-fill only: the PG baseline is create_all from the models, so a fresh PG DB
    # already carries release_execution_mode and this is a guarded no-op; it matters
    # only for a PG DB materialised before the model carried the column.
    if "release_execution_mode" not in _columns("releases"):
        op.add_column(
            "releases",
            sa.Column(
                "release_execution_mode", sa.String(16),
                nullable=False, server_default="automated",
            ),
        )


def downgrade() -> None:
    # No-op by design — the column is owned by the baseline create, not this
    # back-fill migration; it is removed when the releases table is dropped.
    pass
