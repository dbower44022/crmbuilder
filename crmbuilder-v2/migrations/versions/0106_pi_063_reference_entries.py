"""REL-016 / PI-063 (REQ-398) — the ``reference_entry`` cross-engagement entity.

Adds the ``reference_entries`` table (Domain Knowledge / Organization Structure /
Inventory Items reference-library records, system|engagement scoped) and admits
the new entity type in the shared CHECKs:

- ``reference_entry`` joins ``ENTITY_TYPES``, so the ``refs`` source/target
  CHECKs and the ``change_log`` entity-type CHECK (which unions ``ENTITY_TYPES``)
  both widen to admit it.

No new relationship kind (reference entries carry no `refs` edges — the loader
matches on ``trigger_keywords``, not edges). All rebuilt CHECKs are supersets,
so no existing row is invalidated.

SQLite chain head 0105 -> 0106. Companion PG-chain delta:
``migrations/pg/versions/0063_pi_063_reference_entries.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain; this migration is the canonical record of the delta,
applied live via ``crmbuilder-v2-bootstrap-db`` (verified on a copy first).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0106_pi_063_reference_entries"
down_revision: str | None = "0105_pi_094_participant_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "reference_entry"
_ENTITY_TYPES_NEW = ENTITY_TYPES
_ENTITY_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_CHANGELOG_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_table() -> None:
    if "reference_entries" in _tables():
        return
    op.create_table(
        "reference_entries",
        sa.Column("identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("applies_to", sa.String(length=255), nullable=True),
        sa.Column("trigger_keywords", sa.JSON(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
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
            "identifier GLOB 'RFE-[0-9][0-9][0-9]'",
            name="ck_reference_entry_identifier_format",
        ),
        sa.CheckConstraint(
            "kind IN ('domain_knowledge', 'organization_structure', 'inventory_items')",
            name="ck_reference_entry_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired')",
            name="ck_reference_entry_status",
        ),
    )
    op.create_index(
        "ix_reference_entries_engagement", "reference_entries", ["engagement_id"]
    )
    op.create_index(
        "ix_reference_entries_kind", "reference_entries", ["kind"]
    )


def _drop_table() -> None:
    if "reference_entries" not in _tables():
        return
    op.drop_index("ix_reference_entries_kind", table_name="reference_entries")
    op.drop_index("ix_reference_entries_engagement", table_name="reference_entries")
    op.drop_table("reference_entries")


def _rebuild_ref_type_checks(entity_types: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_source_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_source_type", _check_in("source_type", entity_types)
        )
        batch.drop_constraint("ck_ref_target_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_target_type", _check_in("target_type", entity_types)
        )


def _rebuild_changelog_check(entity_types: frozenset[str]) -> None:
    if "change_log" not in _tables():
        return
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type", _check_in("entity_type", entity_types)
        )


def upgrade() -> None:
    _create_table()
    _rebuild_ref_type_checks(_ENTITY_TYPES_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE source_type = 'reference_entry' "
            "OR target_type = 'reference_entry'"
        )
    if "change_log" in _tables():
        op.execute("DELETE FROM change_log WHERE entity_type = 'reference_entry'")
    _rebuild_ref_type_checks(_ENTITY_TYPES_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    _drop_table()
