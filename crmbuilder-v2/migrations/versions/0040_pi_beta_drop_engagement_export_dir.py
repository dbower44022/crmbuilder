"""PI-beta follow-on — drop the vestigial ``engagements.engagement_export_dir``.

PI-beta killed the JSON-snapshot / db-export machinery and the write-time export
gate, leaving ``engagement_export_dir`` a dead column nothing reads or writes.
This is the schema-change pass PI-beta deferred: drop the column, its model field,
its validation, and its UI.

SQLite chain: a batch-mode column drop (head 0039 -> 0040). The companion PG-chain
delta lives at ``migrations/pg/versions/0002_drop_engagement_export_dir.py`` (the
PI-alpha dual-head posture: PG is not replayed through this batch chain).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_pi_beta_drop_engagement_export_dir"
down_revision: str | None = "0039_pi_alpha_widen_text_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # Guarded so this is a clean no-op when the schema was materialised from
    # the current ORM models (which no longer declare the column) — the path
    # the migration-from-create_all tests exercise via ``upgrade head``.
    if _has_column("engagements", "engagement_export_dir"):
        with op.batch_alter_table("engagements") as batch:
            batch.drop_column("engagement_export_dir")
        # SQLite batch mode recreates the table from reflected metadata, and
        # reflection cannot round-trip expression indexes — the recreate
        # silently drops 0037's two functional unique indexes. Restore them
        # (IF NOT EXISTS keeps this idempotent where the recreate never ran).
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_engagements_code_lower "
            "ON engagements (LOWER(engagement_code))"
        )
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_engagements_name_lower "
            "ON engagements (LOWER(engagement_name))"
        )


def downgrade() -> None:
    if not _has_column("engagements", "engagement_export_dir"):
        with op.batch_alter_table("engagements") as batch:
            batch.add_column(
                sa.Column("engagement_export_dir", sa.Text(), nullable=True)
            )
