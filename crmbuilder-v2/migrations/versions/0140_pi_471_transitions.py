"""PI-471 (REQ-577 to REQ-586, approved by DEC-1071): the ``transitions`` table
and the four reference kinds that name an individual move.

A transition (``TRN-``) is one allowed move of a status field on an entity
within a process: from one value of the field, from a set of its values, or
from the creation of the record, to one value, together with who may make the
move, what must be recorded before it, and what happens automatically after it.
The table is created from the ORM ``__table__`` with ``checkfirst`` so the
create_all-then-upgrade-head test path is idempotent.

Three CHECK rebuilds accompany it, each a superset that invalidates no existing
row, and each inspector-guarded so the chain is safe to enter mid-stream: the
change-log entity type and the ``refs`` source and target types admit
``transition``, and the ``refs`` relationship kind admits the four inbound
kinds of REQ-583 — ``view_offers_transition``,
``automation_triggered_by_transition``, ``test_spec_exercises_transition`` and
``requirement_touches_transition``. This is the known gotcha the earlier
table-adding migrations record: tests build through create_all and miss the
CHECK, while the live store returns a 500 without it.

Downgrade removes the rows that reference a transition, the change-log rows for
the type, then narrows the CHECKs and drops the table.

SQLite chain head 0139 -> 0140. Companion PG-chain delta:
``migrations/pg/versions/0097_pi_471_transitions.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Transition
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0140_pi_471_transitions"
down_revision: str | None = "0139_pi_488_session_opening_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "transition"
_NEW_KINDS = frozenset(
    {
        "view_offers_transition",
        "automation_triggered_by_transition",
        "test_spec_exercises_transition",
        "requirement_touches_transition",
    }
)

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_checks(
    types: frozenset[str], log_types: frozenset[str], kinds: frozenset[str]
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
            batch.drop_constraint("ck_ref_relationship", type_="check")
            batch.create_check_constraint(
                "ck_ref_relationship", _check_in("relationship_kind", kinds)
            )


def upgrade() -> None:
    Transition.__table__.create(op.get_bind(), checkfirst=True)
    _rebuild_checks(_TYPES_NEW, _LOG_NEW, _KINDS_NEW)


def downgrade() -> None:
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'transition' "
            "OR target_type = 'transition'"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'transition'")
    _rebuild_checks(_TYPES_OLD, _LOG_OLD, _KINDS_OLD)
    if Transition.__tablename__ in _tables():
        Transition.__table__.drop(op.get_bind())
