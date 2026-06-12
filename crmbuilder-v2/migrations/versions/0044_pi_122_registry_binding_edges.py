"""PI-122 — admit the registry binding + learning edge kinds in the refs CHECK.

Rebuilds ``ck_ref_relationship`` to admit the five new ``REFERENCE_RELATIONSHIPS``
kinds: ``agent_profile_has_skill``, ``agent_profile_governed_by_rule`` (slice 2
bindings) and ``learning_derived_from`` / ``learning_contradicted_by`` /
``learning_promoted_to`` (admitted now so the learning slice needs no further
CHECK migration). Superset, so no existing row is invalidated. Predicate derived
from the current vocab so it cannot drift from the model.

SQLite chain head 0043 -> 0044. Companion PG-chain delta:
``migrations/pg/versions/0006_pi_122_registry_binding_edges.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0044_pi_122_registry_binding_edges"
down_revision: str | None = "0043_pi_122_registry_catalog_entities"
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


def _has_refs() -> bool:
    # refs is absent when the chain is entered mid-stream (isolated-migration tests)
    return "refs" in set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild(kinds: frozenset[str]) -> None:
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    if not _has_refs():
        return
    _rebuild(_KINDS_NEW)


def downgrade() -> None:
    if not _has_refs():
        return
    op.execute(
        "DELETE FROM refs WHERE relationship_kind IN "
        "('agent_profile_has_skill', 'agent_profile_governed_by_rule', "
        "'learning_derived_from', 'learning_contradicted_by', 'learning_promoted_to')"
    )
    _rebuild(_KINDS_OLD)
