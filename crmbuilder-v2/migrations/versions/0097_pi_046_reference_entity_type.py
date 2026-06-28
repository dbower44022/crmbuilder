"""PI-046 (REQ-387) — add ``reference`` to ENTITY_TYPES; rebuild the refs CHECKs.

``vocab._kinds_for_pair`` admitted ``target_type="reference"`` for kind
``deposit_event_wrote_record``, but ``reference`` was absent from
``vocab.ENTITY_TYPES``, so ``RELATIONSHIP_RULES`` (the ENTITY_TYPES × ENTITY_TYPES
product) never generated the ``("deposit_event", "reference")`` key and such POSTs
422'd. Declaring ``reference`` closes that schema-vs-spec contradiction.

Only the ``refs`` source/target-type CHECKs move — they derive from
``ENTITY_TYPES``. The ``change_log`` entity-type CHECK is **unchanged**:
``CHANGE_LOG_ENTITY_TYPES`` already carried ``reference`` via its explicit union,
so adding it to ``ENTITY_TYPES`` leaves that set identical. No relationship-kind
CHECK change either — ``deposit_event_wrote_record`` is an existing kind. Both
rebuilt CHECKs are supersets, so no existing row is invalidated.

SQLite chain head 0096 -> 0097. Companion PG-chain delta:
``migrations/pg/versions/0054_pi_046_reference_entity_type.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is
create_all-managed and is NOT walked through this SQLite chain. This migration is
the canonical record of the delta; the live application is performed via
``crmbuilder-v2-bootstrap-db`` (and verified on a copy first) per the standard
runbook.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import ENTITY_TYPES, _check_in

revision: str = "0097_pi_046_reference_entity_type"
down_revision: str | None = "0096_pi_255_association_mappings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "reference"
_REF_TYPES_NEW = ENTITY_TYPES
_REF_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_ref_type_checks(ref_types: frozenset[str]) -> None:
    if "refs" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_source_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_source_type", _check_in("source_type", ref_types)
        )
        batch.drop_constraint("ck_ref_target_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_target_type", _check_in("target_type", ref_types)
        )


def upgrade() -> None:
    _rebuild_ref_type_checks(_REF_TYPES_NEW)


def downgrade() -> None:
    # Drop any rows the widened CHECK newly admitted, then restore the old CHECK.
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE source_type = 'reference' "
            "OR target_type = 'reference'"
        )
    _rebuild_ref_type_checks(_REF_TYPES_OLD)
