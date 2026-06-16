"""PI-205 (PRJ-031) — releases table + CHECK rebuilds.

Creates the ``releases`` table (the multi-agent release pipeline keystone,
``REL-``) from the ORM ``__table__`` with ``checkfirst`` (idempotent on the
create_all-then-upgrade-head test path), including the ``uq_releases_one_in_lane``
partial unique index that backstops single-occupancy. Rebuilds
``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the new ``release`` entity type, and the
``refs`` ``ck_ref_relationship`` CHECK to admit the two new relationship kinds
(``project_belongs_to_release``, ``release_planned_in_reference_book``). All
predicates derive from current vocab (supersets, no row invalidated); rebuilds
inspect live tables first so the chain is safe to enter mid-stream. SQLite head
0062 -> 0063; companion PG delta ``migrations/pg/versions/0020_pi_205_release_entity.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0063_pi_205_release_entity"
down_revision: str | None = "0062_pi_197_field_derived_formula"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "release"
_NEW_KINDS = frozenset(
    {"project_belongs_to_release", "release_planned_in_reference_book"}
)
_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW}
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW}
_REL_NEW = REFERENCE_RELATIONSHIPS
_REL_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_checks(
    types: frozenset[str], log_types: frozenset[str], rels: frozenset[str]
) -> None:
    existing = _tables()
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", log_types)
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_source_type", _check_in("source_type", types)
            )
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_target_type", _check_in("target_type", types)
            )
            batch.drop_constraint("ck_ref_relationship", type_="check")
            batch.create_check_constraint(
                "ck_ref_relationship", _check_in("relationship_kind", rels)
            )


def upgrade() -> None:
    Release.__table__.create(op.get_bind(), checkfirst=True)
    _rebuild_checks(_TYPES_NEW, _LOG_NEW, _REL_NEW)


def downgrade() -> None:
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'release' "
            "OR target_type = 'release' "
            "OR relationship_kind IN "
            "('project_belongs_to_release', 'release_planned_in_reference_book')"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'release'")
    _rebuild_checks(_TYPES_OLD, _LOG_OLD, _REL_OLD)
    if Release.__tablename__ in _tables():
        Release.__table__.drop(op.get_bind())
