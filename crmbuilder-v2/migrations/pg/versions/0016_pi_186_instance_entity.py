"""PI-186 (PG chain) — instances table + entity-type CHECK rebuilds.

Companion to the SQLite-chain ``0054``. Creates the ``instances`` table and
rebuilds ``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the new ``instance`` entity type on
Postgres deployments materialised from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the
live ORM models, so a freshly-built PG DB already carries the new table and the
vocab-derived CHECK predicates — the table create is inspector-guarded and the
constraint rebuilds are same-text no-op-equivalents there; on a pre-existing PG
store they are real changes. No new relationship kinds (membership lands in
PI-185), so ``ck_ref_relationship`` is untouched. Supersets, so no existing row
is invalidated. Never replay the SQLite chain on a Postgres DB; the two files
are siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Instance
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0016_pi_186_instance_entity"
down_revision: str | None = "0015_pi_183_execution_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "instance"

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}


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


def upgrade() -> None:
    bind = op.get_bind()
    if Instance.__tablename__ not in _tables():
        Instance.__table__.create(bind)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_TYPES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type = 'instance' "
        "OR target_type = 'instance'"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'instance'")
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_TYPES_OLD)
    if Instance.__tablename__ in _tables():
        Instance.__table__.drop(bind)
