"""PI-195 (PRJ-027) — filtered_tabs table + CHECK rebuilds.

Creates the ``filtered_tabs`` table (the engine-neutral filtered-tab design
record, ``FTB-``) from the ORM ``__table__`` with ``checkfirst`` (idempotent on
the create_all-then-upgrade-head test path). Rebuilds ``ck_changelog_entity_
type`` and the ``refs`` ``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs to
admit the new ``filtered_tab`` entity type, and the ``instance_memberships``
``ck_instance_membership_member_type`` CHECK to admit the ``filtered_tab`` member
type. No new relationship_kind. All CHECK predicates derive from current vocab
(supersets, no row invalidated); rebuilds inspect live tables first so the chain
is safe to enter mid-stream. SQLite head 0060 -> 0061; companion PG delta
``migrations/pg/versions/0019_pi_195_filtered_tab.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import FilteredTab
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    INSTANCE_MEMBERSHIP_MEMBER_TYPES,
    _check_in,
)

revision: str = "0061_pi_195_filtered_tab"
down_revision: str | None = "0060_pi_193_194_layout_role_team"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "filtered_tab"
_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW}
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW}
_MEMBER_NEW = INSTANCE_MEMBERSHIP_MEMBER_TYPES
_MEMBER_OLD = INSTANCE_MEMBERSHIP_MEMBER_TYPES - {_NEW}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(types: frozenset[str], log_types: frozenset[str]) -> None:
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


def _rebuild_member_type_check(member_types: frozenset[str]) -> None:
    if "instance_memberships" not in _tables():
        return
    with op.batch_alter_table("instance_memberships") as batch:
        batch.drop_constraint("ck_instance_membership_member_type", type_="check")
        batch.create_check_constraint(
            "ck_instance_membership_member_type",
            _check_in("member_type", member_types),
        )


def upgrade() -> None:
    FilteredTab.__table__.create(op.get_bind(), checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)
    _rebuild_member_type_check(_MEMBER_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'filtered_tab' "
            "OR target_type = 'filtered_tab'"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'filtered_tab'")
    if "instance_memberships" in existing:
        op.execute(
            "DELETE FROM instance_memberships WHERE member_type = 'filtered_tab'"
        )
    _rebuild_member_type_check(_MEMBER_OLD)
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    if FilteredTab.__tablename__ in _tables():
        FilteredTab.__table__.drop(bind)
