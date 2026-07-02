"""REL-016 / PI-063 (REQ-398, PG chain) — the ``reference_entry`` entity.

Companion to the SQLite-chain ``0106``. Adds the ``reference_entries`` table and
admits ``reference_entry`` in the shared CHECKs (``refs`` source/target +
``change_log`` entity-type). Supersets, so no existing row is invalidated.
Identifier/kind/status CHECKs use the dialect-aware ``_IdentifierFormatCheck`` /
``_check_in`` helpers (``~``-regex + ``IN`` on Postgres).

PG chain head 0062 -> 0063.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _IdentifierFormatCheck
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_ENTRY_KINDS,
    REGISTRY_STATUSES,
    _check_in,
)

revision: str = "0063_pi_063_reference_entries"
down_revision: str | None = "0062_pi_094_participant_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "reference_entry"
_ENTITY_TYPES_NEW = ENTITY_TYPES
_ENTITY_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_CHANGELOG_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


def _create_table() -> None:
    op.create_table(
        "reference_entries",
        sa.Column("identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("applies_to", sa.String(length=255), nullable=True),
        sa.Column(
            "trigger_keywords",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "content",
            sa.JSON().with_variant(sa.dialects.postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identifier"),
        sa.CheckConstraint(
            _IdentifierFormatCheck("identifier", ["RFE"]),
            name="ck_reference_entry_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("kind", REFERENCE_ENTRY_KINDS),
            name="ck_reference_entry_kind",
        ),
        sa.CheckConstraint(
            _check_in("status", REGISTRY_STATUSES),
            name="ck_reference_entry_status",
        ),
    )
    op.create_index(
        "ix_reference_entries_engagement", "reference_entries", ["engagement_id"]
    )
    op.create_index("ix_reference_entries_kind", "reference_entries", ["kind"])


def _rebuild_ref_type_checks(entity_types: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", entity_types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", entity_types)
    )


def _rebuild_changelog_check(entity_types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type",
        "change_log",
        _check_in("entity_type", entity_types),
    )


def upgrade() -> None:
    _create_table()
    _rebuild_ref_type_checks(_ENTITY_TYPES_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE source_type = 'reference_entry' "
        "OR target_type = 'reference_entry'"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'reference_entry'")
    _rebuild_ref_type_checks(_ENTITY_TYPES_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    op.drop_index("ix_reference_entries_kind", table_name="reference_entries")
    op.drop_index(
        "ix_reference_entries_engagement", table_name="reference_entries"
    )
    op.drop_table("reference_entries")
