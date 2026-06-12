"""PI-123 Slice 2 (DEC-375 / D2) — add the nullable engagement_id discriminator

Adds ``engagement_id VARCHAR(32)`` (nullable) to every **engagement-scoped**
table — the ~30 governance + methodology tables (``pi-123-unified-db-architecture.md``
§6). The catalog (``catalog_*``) tables and the ``engagements`` tenant table are
deliberately excluded (system/shared bucket + the FK target).

Purely additive: the column is NULL on every existing row, so this changes no
behaviour in the current single-engagement-per-file runtime. No FK, no index, no
NOT NULL yet — Slice 3's batch rebuild adds the FK to
``engagements.engagement_identifier`` + ``NOT NULL`` + the composite
``(engagement_id, identifier)`` uniqueness once the Data Migration phase has
backfilled the column. The central read-filter / write-stamp that key on this
column stay dormant until then.

Idempotent (skips a table that already has the column). Reversible (drops it).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_pi_123_engagement_id_discriminator_nullable"
down_revision: str | None = "0037_pi_123_engagements_table_in_unified_db"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The 30 engagement-scoped tables (everything except catalog_* and engagements).
# Kept as an explicit list (not reflection) so the migration is a stable,
# reviewable record of exactly which tables were scoped.
SCOPED_TABLES: tuple[str, ...] = (
    "charter",
    "status",
    "decisions",
    "sessions",
    "risks",
    "planning_items",
    "engagement_areas",
    "topics",
    "domains",
    "entities",
    "fields",
    "requirements",
    "personas",
    "processes",
    "manual_configs",
    "test_specs",
    "crm_candidates",
    "projects",
    "workstreams",
    "work_tasks",
    "conversations",
    "reference_books",
    "reference_book_versions",
    "work_tickets",
    "close_out_payloads",
    "deposit_events",
    "commits",
    "refs",
    "change_log",
    "identifier_reservations",
)


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _existing_tables()
    for table in SCOPED_TABLES:
        if table not in existing:
            continue  # absent when the chain is entered mid-stream (isolated-migration tests)
        if "engagement_id" in _columns(table):
            continue  # idempotent
        op.add_column(
            table,
            sa.Column("engagement_id", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    existing = _existing_tables()
    for table in SCOPED_TABLES:
        if table not in existing:
            continue
        if "engagement_id" not in _columns(table):
            continue
        with op.batch_alter_table(table) as batch:
            batch.drop_column("engagement_id")
