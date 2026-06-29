"""PI-364 (PG chain) — project build-run claim columns (heartbeat lease).

Companion to the SQLite-chain ``0101``. Adds ``project_claimed_by`` +
``project_claimed_at`` to ``projects`` for the exclusive per-project build claim
(REQ-423). Plain ``ADD COLUMN`` (nullable); the both-or-neither pairing is enforced
in the access layer, not a DB CHECK.

PG chain head 0057 -> 0058.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058_pi_364_project_run_claim"
down_revision: str | None = "0057_pi_361_delivered_off_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects", sa.Column("project_claimed_by", sa.String(64), nullable=True)
    )
    op.add_column(
        "projects",
        sa.Column("project_claimed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "project_claimed_at")
    op.drop_column("projects", "project_claimed_by")
