"""PI-193 + PI-194 (PRJ-027) — layouts / roles / teams tables + CHECK rebuilds.

Adds the three net-new design families in one migration (built + merged
together): the ``layouts`` (``LAY-``), ``roles`` (``ROL-``), and ``teams``
(``TM-``) tables, created from the ORM ``__table__`` with ``checkfirst``
(idempotent on the create_all-then-upgrade-head test path). Rebuilds
``ck_changelog_entity_type`` and the ``refs`` ``ck_ref_source_type`` /
``ck_ref_target_type`` CHECKs to admit the three new entity types (the known
gotcha: tests build via create_all and miss it, the live DB 500s without it —
see 0034 / 0043 / 0045 / 0048 / 0052 / 0054). Also rebuilds the
``instance_memberships`` ``ck_instance_membership_member_type`` CHECK to admit
the new member types ``layout`` / ``role`` / ``team`` (PI-193/194 reconcile
records membership for these families).

No new relationship_kind — these families are inventory objects tracked via the
instance_membership join, not refs edges. All CHECK predicates derive from the
current vocab; rebuilds are supersets so no existing row is invalidated. Every
rebuild inspects the live tables first and skips absent ones so the chain is
safe to enter mid-stream. SQLite chain head 0059 -> 0060; companion PG delta
``migrations/pg/versions/0018_pi_193_194_layout_role_team.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Layout, Role, Team
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    INSTANCE_MEMBERSHIP_MEMBER_TYPES,
    _check_in,
)

revision: str = "0060_pi_193_194_layout_role_team"
down_revision: str | None = "0059_pi_185_instance_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"layout", "role", "team"})
_NEW_MEMBER_TYPES = frozenset({"layout", "role", "team"})

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES
_MEMBER_NEW = INSTANCE_MEMBERSHIP_MEMBER_TYPES
_MEMBER_OLD = INSTANCE_MEMBERSHIP_MEMBER_TYPES - _NEW_MEMBER_TYPES


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
    bind = op.get_bind()
    for model in (Layout, Role, Team):
        model.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)
    _rebuild_member_type_check(_MEMBER_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type IN ('layout','role','team') "
            "OR target_type IN ('layout','role','team')"
        )
    if "change_log" in existing:
        op.execute(
            "DELETE FROM change_log WHERE entity_type IN ('layout','role','team')"
        )
    if "instance_memberships" in existing:
        op.execute(
            "DELETE FROM instance_memberships "
            "WHERE member_type IN ('layout','role','team')"
        )
    _rebuild_member_type_check(_MEMBER_OLD)
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    for model in (Team, Role, Layout):
        if model.__tablename__ in _tables():
            model.__table__.drop(bind)
