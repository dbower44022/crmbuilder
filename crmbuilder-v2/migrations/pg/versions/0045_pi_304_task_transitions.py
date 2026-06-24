"""PI-304 (PG chain) — task_transitions table + entity-type / relationship CHECKs.

Companion to the SQLite-chain ``0088``. Creates the ``task_transitions`` table
(the append-only task-transition log, ``task_transition`` entity, DEC-692) and
rebuilds the ``change_log`` / ``refs`` entity-type CHECKs to admit
``task_transition`` and the ``refs`` relationship-kind CHECK to admit
``task_transition_records_task`` on Postgres deployments materialised from an
earlier baseline. Inspector-guarded table create: a no-op on a fresh baseline
(create_all already has it), a real change on a pre-existing PG store. Supersets,
so no existing row is invalidated.

PG chain head 0044 -> 0045.
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

revision: str = "0045_pi_304_task_transitions"
down_revision: str | None = "0044_pi_302_work_task_resolved_agent_profile"
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
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log",
        _check_in("entity_type", changelog_types),
    )
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", ref_types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", ref_types)
    )


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if TaskTransitionRow.__tablename__ not in _tables():
        TaskTransitionRow.__table__.create(bind)
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_NEW, _REF_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type = 'task_transition' "
        "OR target_type = 'task_transition' "
        "OR relationship_kind = 'task_transition_records_task'"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'task_transition'")
    _rebuild_entity_type_checks(_CHANGELOG_TYPES_OLD, _REF_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if TaskTransitionRow.__tablename__ in _tables():
        TaskTransitionRow.__table__.drop(bind)
