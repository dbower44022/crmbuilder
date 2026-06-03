"""PI-122 (PG chain) — admit the registry binding + learning edge kinds.

Companion to the SQLite-chain ``0044``. Rebuilds ``ck_ref_relationship`` to admit
the five new ``REFERENCE_RELATIONSHIPS`` kinds on Postgres deployments
materialised from an earlier baseline.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0006_pi_122_registry_binding_edges"
down_revision: str | None = "0005_pi_122_registry_catalog_entities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset(
    {
        "agent_profile_has_skill",
        "agent_profile_governed_by_rule",
        "learning_derived_from",
        "learning_contradicted_by",
        "learning_promoted_to",
    }
)
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _rebuild(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    _rebuild(_KINDS_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE relationship_kind IN "
        "('agent_profile_has_skill', 'agent_profile_governed_by_rule', "
        "'learning_derived_from', 'learning_contradicted_by', 'learning_promoted_to')"
    )
    _rebuild(_KINDS_OLD)
