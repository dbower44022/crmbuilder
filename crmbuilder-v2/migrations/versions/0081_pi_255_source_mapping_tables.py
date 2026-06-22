"""PI-255 (PRJ-027 / SES-230) — source instance mapping model tables.

Creates the seven tables of the candidate-gated source mapping layer:
``source_mappings`` (``SMG-``) and ``field_mappings`` (``FMP-``) — the
prefixed-identifier entity/field decisions — plus their support children
``source_mapping_targets``, ``source_mapping_joins``,
``field_mapping_translations``, ``value_mappings`` and the reconciler's
pre-decision ``mapping_candidates`` (integer-PK). Tables are created from the
ORM ``__table__`` with ``checkfirst`` (idempotent on the create_all-then-
upgrade-head test path).

Rebuilds ``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the three new entity types
(``source_mapping`` / ``field_mapping`` / ``mapping_candidate``) — the known
gotcha: tests build via create_all and miss it, the live DB 500s without it
(see 0034 / 0043 / 0045 / 0048 / 0052 / 0054 / 0060). Also rebuilds the
``instance_memberships`` ``ck_instance_membership_state`` CHECK to admit the two
new states ``candidate_pending`` / ``mapping_stale`` (SES-230, DEC-454).

All CHECK predicates derive from the current vocab; rebuilds are supersets so no
existing row is invalidated, and every rebuild inspects the live tables first so
the chain is safe to enter mid-stream. SQLite chain head 0080 -> 0081; companion
PG delta ``migrations/pg/versions/0038_pi_255_source_mapping_tables.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import (
    FieldMapping,
    FieldMappingTranslation,
    MappingCandidate,
    SourceMapping,
    SourceMappingJoin,
    SourceMappingTarget,
    ValueMapping,
)
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    INSTANCE_MEMBERSHIP_STATES,
    _check_in,
)

revision: str = "0081_pi_255_source_mapping_tables"
down_revision: str | None = "0080_pi_263_cost_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"source_mapping", "field_mapping", "mapping_candidate"})
_NEW_STATES = frozenset({"candidate_pending", "mapping_stale"})

# FK-order: parents (source_mappings, field_mappings) before their children, so a
# create/drop honours soft-reference order even though links are not hard FKs.
_MODELS = (
    SourceMapping,
    SourceMappingTarget,
    SourceMappingJoin,
    FieldMapping,
    FieldMappingTranslation,
    ValueMapping,
    MappingCandidate,
)

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES
_STATES_NEW = INSTANCE_MEMBERSHIP_STATES
_STATES_OLD = INSTANCE_MEMBERSHIP_STATES - _NEW_STATES


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    types: frozenset[str], log_types: frozenset[str]
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


def _rebuild_membership_state_check(states: frozenset[str]) -> None:
    if "instance_memberships" not in _tables():
        return
    with op.batch_alter_table("instance_memberships") as batch:
        batch.drop_constraint("ck_instance_membership_state", type_="check")
        batch.create_check_constraint(
            "ck_instance_membership_state", _check_in("state", states)
        )


def upgrade() -> None:
    bind = op.get_bind()
    for model in _MODELS:
        model.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)
    _rebuild_membership_state_check(_STATES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    new_list = "', '".join(sorted(_NEW_TYPES))
    if "refs" in existing:
        op.execute(
            f"DELETE FROM refs WHERE source_type IN ('{new_list}') "
            f"OR target_type IN ('{new_list}')"
        )
    if "change_log" in existing:
        op.execute(
            f"DELETE FROM change_log WHERE entity_type IN ('{new_list}')"
        )
    if "instance_memberships" in existing:
        states_list = "', '".join(sorted(_NEW_STATES))
        op.execute(
            f"DELETE FROM instance_memberships WHERE state IN ('{states_list}')"
        )
    _rebuild_membership_state_check(_STATES_OLD)
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    for model in reversed(_MODELS):
        if model.__tablename__ in _tables():
            model.__table__.drop(bind)
