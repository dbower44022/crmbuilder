"""PI-134 (PG chain) — findings table + entity-type / relationship-kind CHECKs.

Companion to the SQLite-chain ``0045``. Creates the ``findings`` table and
rebuilds the ``change_log`` / ``refs`` entity-type CHECKs to admit ``finding``
and the ``refs`` relationship-kind CHECK to admit ``finding_relates_to`` /
``finding_resolved_by`` on Postgres deployments materialised from an earlier
baseline. Inspector-guarded: a no-op table create on a fresh baseline (create_all
already has it), a real change on a pre-existing PG store. Supersets, so no
existing row is invalidated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Finding
from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0007_pi_134_findings_entity"
down_revision: str | None = "0006_pi_122_registry_binding_edges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "finding"
_NEW_KINDS = frozenset({"finding_relates_to", "finding_resolved_by"})
_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log",
        _check_in("entity_type", types | {"reference"}),
    )
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint("ck_ref_source_type", "refs", _check_in("source_type", types))
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint("ck_ref_target_type", "refs", _check_in("target_type", types))


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if Finding.__tablename__ not in _tables():
        Finding.__table__.create(bind)
    _rebuild_entity_type_checks(_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type = 'finding' OR target_type = 'finding' "
        "OR relationship_kind IN ('finding_relates_to', 'finding_resolved_by')"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'finding'")
    _rebuild_entity_type_checks(_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if Finding.__tablename__ in _tables():
        Finding.__table__.drop(bind)
