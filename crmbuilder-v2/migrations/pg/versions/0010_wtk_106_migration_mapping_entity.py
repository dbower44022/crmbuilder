"""WTK-106 (PG chain) — migration_mappings table + CHECK rebuilds.

Companion to the SQLite-chain ``0048``. Creates the ``migration_mappings``
table, rebuilds ``ck_changelog_entity_type`` and the ``refs``
``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs to admit the new
``migration_mapping`` entity type, and rebuilds ``ck_ref_relationship`` to
admit the two new edge kinds
``migration_mapping_migrates_from_record`` /
``migration_mapping_migrates_to_record`` on Postgres deployments
materialised from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from
the live ORM models, so a freshly-built PG DB already carries the new table
and the vocab-derived CHECK predicates — the table create is inspector-
guarded and the constraint rebuilds are same-text no-op-equivalents there;
on a pre-existing PG store they are real changes. Supersets, so no existing
row is invalidated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import MigrationMapping
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0010_wtk_106_migration_mapping_entity"
down_revision: str | None = "0009_wtk_089_deposit_event_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "migration_mapping"
_NEW_KINDS = frozenset(
    {
        "migration_mapping_migrates_from_record",
        "migration_mapping_migrates_to_record",
    }
)

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    types: frozenset[str], log_types: frozenset[str]
) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type",
        "change_log",
        _check_in("entity_type", log_types),
    )
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", types)
    )


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if MigrationMapping.__tablename__ not in _tables():
        MigrationMapping.__table__.create(bind)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type = 'migration_mapping' "
        "OR target_type = 'migration_mapping' "
        "OR relationship_kind IN "
        "('migration_mapping_migrates_from_record', "
        "'migration_mapping_migrates_to_record')"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'migration_mapping'")
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if MigrationMapping.__tablename__ in _tables():
        MigrationMapping.__table__.drop(bind)
