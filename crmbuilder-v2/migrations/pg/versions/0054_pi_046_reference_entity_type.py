"""PI-046 (PG chain) — add ``reference`` to ENTITY_TYPES; rebuild the refs CHECKs.

Companion to the SQLite-chain ``0097``. ``reference`` is declared as an entity type
so ``RELATIONSHIP_RULES`` generates the ``("deposit_event", "reference")`` key for
``deposit_event_wrote_record`` (closing the schema-vs-spec contradiction PI-046 /
REQ-387). Only the ``refs`` source/target-type CHECKs move — they derive from
``ENTITY_TYPES``. The ``change_log`` entity-type CHECK is unchanged
(``CHANGE_LOG_ENTITY_TYPES`` already carried ``reference``), and no relationship-kind
CHECK change (``deposit_event_wrote_record`` is existing). Supersets, so no existing
row is invalidated.

PG chain head 0053 -> 0054.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import ENTITY_TYPES, _check_in

revision: str = "0054_pi_046_reference_entity_type"
down_revision: str | None = "0053_pi_255_association_mappings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "reference"
_REF_TYPES_NEW = ENTITY_TYPES
_REF_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}


def _rebuild_ref_type_checks(ref_types: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", ref_types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", ref_types)
    )


def upgrade() -> None:
    _rebuild_ref_type_checks(_REF_TYPES_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE source_type = 'reference' "
        "OR target_type = 'reference'"
    )
    _rebuild_ref_type_checks(_REF_TYPES_OLD)
