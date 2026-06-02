"""PI-123 Slice 1 (DEC-375 / D1) — fold the engagements registry into the unified DB

Creates the ``engagements`` tenant table in the **main** Alembic chain so the
unified multi-engagement DB holds the engagement registry that the separate
"meta DB" (``data/engagements.db``, its own ``MetaBase`` + chain) held before.
This is the first, additive step of the per-engagement-DB → unified-DB migration
(``pi-123-unified-db-architecture.md`` §8 / Slice 1): it adds the table only —
no ``engagement_id`` discriminator yet (that is Slice 2), no data consolidation
(that is the Data Migration phase).

Safe on the live per-engagement DBs: it adds an empty, currently-unused table.
The legacy runtime still serves ``/engagements/*`` from the meta DB until the
Deployment cutover; this table becomes the live registry only once the unified
DB is the active DB.

Idempotent: skips creation if ``engagements`` already exists (e.g. a DB that was
materialised via ``Base.metadata.create_all`` at the new head). Reversible:
``downgrade`` drops the table.

Schema mirrors ``access/models.py``'s ``EngagementRow`` (== ``meta_models``'s,
pinned equal by ``test_engagements_model_parity``): 10 columns, 2 CHECKs,
2 unique LOWER() expression indexes, 3 plain indexes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_pi_123_engagements_table_in_unified_db"
down_revision: str | None = "0036_ado_workstream_state_model_substrate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return sa.inspect(bind).has_table(name)


def upgrade() -> None:
    if _has_table("engagements"):
        # Already present (unified DB built via create_all at head, or a
        # partial re-run). Nothing to do — keep the step idempotent.
        return

    op.create_table(
        "engagements",
        sa.Column("engagement_identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_code", sa.String(length=16), nullable=False),
        sa.Column("engagement_name", sa.String(length=255), nullable=False),
        sa.Column("engagement_purpose", sa.Text(), nullable=False),
        sa.Column("engagement_status", sa.String(length=16), nullable=False),
        sa.Column(
            "engagement_last_opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("engagement_export_dir", sa.Text(), nullable=True),
        sa.Column(
            "engagement_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "engagement_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "engagement_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "engagement_identifier GLOB 'ENG-[0-9][0-9][0-9]'",
            name="ck_engagement_identifier_format",
        ),
        sa.CheckConstraint(
            "engagement_status IN ('active', 'paused', 'archived')",
            name="ck_engagement_status",
        ),
        sa.PrimaryKeyConstraint("engagement_identifier"),
    )
    # Unique case-insensitive indexes on code and name (mirrors meta DB).
    op.create_index(
        "ux_engagements_code_lower",
        "engagements",
        [sa.text("LOWER(engagement_code)")],
        unique=True,
    )
    op.create_index(
        "ux_engagements_name_lower",
        "engagements",
        [sa.text("LOWER(engagement_name)")],
        unique=True,
    )
    op.create_index("ix_engagements_status", "engagements", ["engagement_status"])
    op.create_index(
        "ix_engagements_last_opened_at",
        "engagements",
        ["engagement_last_opened_at"],
    )
    op.create_index(
        "ix_engagements_deleted_at", "engagements", ["engagement_deleted_at"]
    )


def downgrade() -> None:
    if not _has_table("engagements"):
        return
    op.drop_index("ix_engagements_deleted_at", table_name="engagements")
    op.drop_index("ix_engagements_last_opened_at", table_name="engagements")
    op.drop_index("ix_engagements_status", table_name="engagements")
    op.drop_index("ux_engagements_name_lower", table_name="engagements")
    op.drop_index("ux_engagements_code_lower", table_name="engagements")
    op.drop_table("engagements")
