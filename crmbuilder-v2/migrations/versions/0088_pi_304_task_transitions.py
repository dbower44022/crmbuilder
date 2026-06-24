"""PI-304 — task_transitions table + entity-type / relationship-kind CHECK rebuilds.

Creates the ``task_transitions`` table (the append-only task-transition log,
``task_transition`` entity, DEC-692 / WTK-213) and rebuilds the ``change_log`` +
``refs`` entity-type CHECKs to admit the new ``task_transition`` entity type, and
the ``refs`` relationship-kind CHECK to admit the new edge kind
``task_transition_records_task``. All three CHECKs are supersets, so no existing
row is invalidated (the documented gotcha that adding an ENTITY_TYPE must rebuild
change_log + refs CHECKs, not just refs; tests build via create_all and miss it —
see 0034 / 0043 / 0045).

The table is created from the ORM ``__table__`` (carries the dialect-aware
identifier-format CHECK) with ``checkfirst`` so this is idempotent on the
create_all-then-upgrade-head test path. The CHECK predicates are derived from the
current vocab so they cannot drift from the models.

SQLite chain head 0087 -> 0088. Companion PG-chain delta:
``migrations/pg/versions/0045_pi_304_task_transitions.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is
create_all-managed and is NOT walked through this SQLite chain. This migration is
the canonical record of the delta; the live application is performed (and verified
on a copy first) per the standard runbook and authorized by a PM session.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import TaskTransitionRow
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0088_pi_304_task_transitions"
down_revision: str | None = "0087_pi_302_work_task_resolved_agent_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "task_transition"
_NEW_KINDS = frozenset({"task_transition_records_task"})

_CHANGELOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_REF_TYPES_NEW = ENTITY_TYPES
_REF_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    changelog_types: frozenset[str], ref_types: frozenset[str]
) -> None:
    existing = _tables()  # change_log/refs absent when the chain is entered mid-stream
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", changelog_types)
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_source_type", _check_in("source_type", ref_types)
            )
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_target_type", _check_in("target_type", ref_types)
            )


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    bind = op.get_bind()
    TaskTransitionRow.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_NEW, _REF_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'task_transition' "
            "OR target_type = 'task_transition' "
            "OR relationship_kind = 'task_transition_records_task'"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'task_transition'")
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_OLD, _REF_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if TaskTransitionRow.__tablename__ in _tables():
        TaskTransitionRow.__table__.drop(bind)
