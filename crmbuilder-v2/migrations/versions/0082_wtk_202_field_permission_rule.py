"""WTK-202 (WSK-167 / REQ-254) — field_permission_rule entity table.

Creates the ``field_permission_rules`` table (``FPR-NNN``) — the security
design record declaring one unconditional (role × target_field) -> permission
level, deployed to the target CRM's field-permission matrix. The table is
created from the ORM ``__table__`` with ``checkfirst`` (idempotent on the
create_all-then-upgrade-head test path).

Rebuilds ``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the new ``field_permission_rule`` entity
type — the known gotcha: tests build via create_all and miss it, the live DB
500s without it (see 0034 / 0043 / 0045 / 0048 / 0052 / 0054 / 0060 / 0081).

All CHECK predicates derive from the current vocab; rebuilds are supersets so no
existing row is invalidated, and every rebuild inspects the live tables first so
the chain is safe to enter mid-stream. SQLite chain head 0081 -> 0082; companion
PG delta ``migrations/pg/versions/0039_wtk_202_field_permission_rule.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import FieldPermissionRule
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0082_wtk_202_field_permission_rule"
down_revision: str | None = "0081_pi_255_source_mapping_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"field_permission_rule"})

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES


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


def upgrade() -> None:
    bind = op.get_bind()
    FieldPermissionRule.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)


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
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    if FieldPermissionRule.__tablename__ in _tables():
        FieldPermissionRule.__table__.drop(bind)
