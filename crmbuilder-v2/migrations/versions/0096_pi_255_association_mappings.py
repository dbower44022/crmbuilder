"""PI-255 (PRJ-027 / DEC-654) — association_mappings table.

Adds the relationship-level source-mapping decision entity (``AMP-``,
``association_mappings``), parallel to ``field_mappings``. Creates the table from
the ORM ``__table__`` with ``checkfirst`` (idempotent on the create_all-then-
upgrade-head test path) and rebuilds ``ck_changelog_entity_type`` and the ``refs``
``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs to admit the new
``association_mapping`` entity type — the known gotcha (tests build via create_all
and miss it, the live DB 500s without it; see 0034 / 0043 / 0081).

CHECK predicates derive from current vocab; rebuilds are supersets so no existing
row is invalidated, and every rebuild inspects the live tables first so the chain
is safe to enter mid-stream. SQLite chain head 0095 -> 0096; companion PG delta
``migrations/pg/versions/0053_pi_255_association_mappings.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AssociationMapping
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0096_pi_255_association_mappings"
down_revision: str | None = "0095_pi_255_drop_membership_candidate_states"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "association_mapping"

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    types: frozenset[str], log_types: frozenset[str]
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


def upgrade() -> None:
    AssociationMapping.__table__.create(op.get_bind(), checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)


def downgrade() -> None:
    existing = _tables()
    if "refs" in existing:
        op.execute(
            f"DELETE FROM refs WHERE source_type = '{_NEW_TYPE}' "
            f"OR target_type = '{_NEW_TYPE}'"
        )
    if "change_log" in existing:
        op.execute(
            f"DELETE FROM change_log WHERE entity_type = '{_NEW_TYPE}'"
        )
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    if AssociationMapping.__tablename__ in _tables():
        AssociationMapping.__table__.drop(op.get_bind())
