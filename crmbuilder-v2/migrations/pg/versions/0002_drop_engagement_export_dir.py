"""PI-beta follow-on (PG chain) — drop the vestigial ``engagement_export_dir``.

Companion to the SQLite-chain ``0040_pi_beta_drop_engagement_export_dir``. PI-beta
left ``engagements.engagement_export_dir`` a dead column; this drops it from
Postgres deployments materialised from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the
live ORM models, which no longer declare the column — so a freshly-built PG DB
never has it. The drop is therefore guarded by an inspector check so this revision
is a clean no-op on a fresh baseline and a real drop on a pre-existing PG store.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_drop_engagement_export_dir"
down_revision: str | None = "0001_pg_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _has_column("engagements", "engagement_export_dir"):
        op.drop_column("engagements", "engagement_export_dir")


def downgrade() -> None:
    if not _has_column("engagements", "engagement_export_dir"):
        op.add_column(
            "engagements",
            sa.Column("engagement_export_dir", sa.Text(), nullable=True),
        )
