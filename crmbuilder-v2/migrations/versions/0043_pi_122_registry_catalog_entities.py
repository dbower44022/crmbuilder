"""PI-122 — Agent Profile Registry catalog entities + entity-type CHECK rebuild.

Creates the four registry tables — ``agent_profiles`` / ``skills`` /
``governance_rules`` / ``learnings`` — and rebuilds the ``change_log`` and
``refs`` entity-type CHECKs to admit the four new entity types
(``agent_profile`` / ``skill`` / ``governance_rule`` / ``learning``). The new
CHECKs are a superset, so no existing row is invalidated (the gotcha that adding
an ENTITY_TYPE must rebuild change_log + refs CHECKs; tests build via create_all
and miss it — see 0034).

Tables are created from the ORM ``__table__`` (carries the dialect-aware
identifier-format CHECKs) with ``checkfirst`` so this is idempotent on the
create_all-then-upgrade-head test path. The CHECK predicates are derived from
the current vocab so they cannot drift from the models.

SQLite chain head 0042 -> 0043. Companion PG-chain delta:
``migrations/pg/versions/0005_pi_122_registry_catalog_entities.py``.
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

revision: str = "0043_pi_122_registry_catalog_entities"
down_revision: str | None = "0042_pi_gamma_changelog_principal_attribution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"agent_profile", "skill", "governance_rule", "learning"})
_TABLES = (AgentProfileRow, SkillRow, GovernanceRuleRow, LearningRow)

# Current (with the four new types) and prior (without) entity-type sets.
_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(types: frozenset[str]) -> None:
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type",
            _check_in("entity_type", types | {"reference"}),
        )
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
    bind = op.get_bind()
    for model in _TABLES:
        model.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    # Drop any refs / change_log rows referencing the new types before narrowing.
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
