"""PI-205 (PG chain) — releases table + CHECK rebuilds.

Companion to the SQLite-chain ``0063``. Creates the ``releases`` table (with the
``uq_releases_one_in_lane`` partial unique index) and rebuilds the change_log /
refs entity-type CHECKs and the refs relationship_kind CHECK to admit the
``release`` entity type and the two new relationship kinds on Postgres
deployments materialised from an earlier baseline. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries it — the
create is inspector-guarded and the rebuilds are same-text no-ops there; on a
pre-existing PG store they are real changes. Supersets, no row invalidated.
Never replay the SQLite chain on Postgres; siblings, not a sequence.
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

revision: str = "0020_pi_205_release_entity"
down_revision: str | None = "0019_pi_195_filtered_tab"
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
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log", _check_in("entity_type", log_types)
    )
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", types)
    )
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", rels)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if Release.__tablename__ not in _tables():
        Release.__table__.create(bind)
    _rebuild_checks(_TYPES_NEW, _LOG_NEW, _REL_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE source_type = 'release' "
        "OR target_type = 'release' "
        "OR relationship_kind IN "
        "('project_belongs_to_release', 'release_planned_in_reference_book')"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'release'")
    _rebuild_checks(_TYPES_OLD, _LOG_OLD, _REL_OLD)
    if Release.__tablename__ in _tables():
        Release.__table__.drop(op.get_bind())
