"""PI-122 (PG chain) — registry catalog entities + entity-type CHECK rebuild.

Companion to the SQLite-chain ``0043``. Creates the four registry tables and
rebuilds the ``change_log`` / ``refs`` entity-type CHECKs to admit the four new
types on Postgres deployments materialised from an earlier baseline. Inspector-
guarded: a no-op on a fresh baseline (create_all already has the tables), a real
change on a pre-existing PG store.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import (
    AgentProfileRow,
    GovernanceRuleRow,
    LearningRow,
    SkillRow,
)
from crmbuilder_v2.access.vocab import ENTITY_TYPES, _check_in

revision: str = "0005_pi_122_registry_catalog_entities"
down_revision: str | None = "0004_pi_gamma_changelog_principal_attribution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"agent_profile", "skill", "governance_rule", "learning"})
_TABLES = (AgentProfileRow, SkillRow, GovernanceRuleRow, LearningRow)
_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES


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


def upgrade() -> None:
    bind = op.get_bind()
    have = _tables()
    for model in _TABLES:
        if model.__tablename__ not in have:
            model.__table__.create(bind)
    _rebuild_entity_type_checks(_TYPES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type IN "
        "('agent_profile', 'skill', 'governance_rule', 'learning') "
        "OR target_type IN "
        "('agent_profile', 'skill', 'governance_rule', 'learning')"
    )
    op.execute(
        "DELETE FROM change_log WHERE entity_type IN "
        "('agent_profile', 'skill', 'governance_rule', 'learning')"
    )
    _rebuild_entity_type_checks(_TYPES_OLD)
    have = _tables()
    for model in reversed(_TABLES):
        if model.__tablename__ in have:
            model.__table__.drop(bind)
