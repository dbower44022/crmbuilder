"""PI-364 (REQ-423) — project build-run claim columns (heartbeat lease).

Adds ``project_claimed_by`` + ``project_claimed_at`` to ``projects`` so one runtime
can claim a project's build exclusively before driving it (a second runtime is
refused while the claim is fresh) and a crashed runtime's lease goes stale and is
reclaimable. Plain guarded ``ADD COLUMN`` (nullable, no default) — the
both-or-neither pairing is enforced in the access layer, not a DB CHECK, so this
needs no table rebuild and preserves the projects indexes/constraints.

SQLite chain head 0100 -> 0101. Companion PG ``migrations/pg/versions/0058_...``.

NOTE (live application): the live store is stamped, so ``crmbuilder-v2-bootstrap-db``
applies this via ``alembic upgrade head``. Verify on a copy first.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0101_pi_364_project_run_claim"
down_revision: str | None = "0100_pi_361_delivered_off_pipeline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "projects" not in sa.inspect(op.get_bind()).get_table_names():
        return
    cols = _columns("projects")
    if "project_claimed_by" not in cols:
        op.add_column(
            "projects", sa.Column("project_claimed_by", sa.String(64), nullable=True)
        )
    if "project_claimed_at" not in cols:
        op.add_column(
            "projects",
            sa.Column("project_claimed_at", sa.DateTime(timezone=True), nullable=True),
        )


def downgrade() -> None:
    # No-op: a DROP COLUMN here is unnecessary (the columns are nullable and unused
    # by older code) and SQLite drop-column is a table rebuild. Left as a back-fill.
    pass
