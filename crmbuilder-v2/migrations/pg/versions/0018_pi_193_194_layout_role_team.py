"""PI-193 + PI-194 (PG chain) — layouts / roles / teams tables + CHECK rebuilds.

Companion to the SQLite-chain ``0060``. Creates the ``layouts`` / ``roles`` /
``teams`` tables and rebuilds the change_log / refs entity-type CHECKs and the
``instance_memberships`` member-type CHECK to admit the three new families on
Postgres deployments materialised from an earlier baseline. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries them — the
creates are inspector-guarded and the rebuilds are same-text no-ops there; on a
pre-existing PG store they are real changes. Supersets, so no row is
invalidated. Never replay the SQLite chain on Postgres; siblings, not a sequence.
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

revision: str = "0018_pi_193_194_layout_role_team"
down_revision: str | None = "0017_pi_185_instance_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"layout", "role", "team"})

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES
_MEMBER_NEW = INSTANCE_MEMBERSHIP_MEMBER_TYPES
_MEMBER_OLD = INSTANCE_MEMBERSHIP_MEMBER_TYPES - _NEW_TYPES


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(types: frozenset[str], log_types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log", _check_in("entity_type", log_types)
    )
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", types)
    )


def _rebuild_member_type_check(member_types: frozenset[str]) -> None:
    op.drop_constraint(
        "ck_instance_membership_member_type", "instance_memberships", type_="check"
    )
    op.create_check_constraint(
        "ck_instance_membership_member_type",
        "instance_memberships",
        _check_in("member_type", member_types),
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    for model in (Layout, Role, Team):
        if model.__tablename__ not in existing:
            model.__table__.create(bind)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_NEW)
    _rebuild_member_type_check(_MEMBER_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    op.execute(
        "DELETE FROM refs WHERE source_type IN ('layout','role','team') "
        "OR target_type IN ('layout','role','team')"
    )
    op.execute(
        "DELETE FROM change_log WHERE entity_type IN ('layout','role','team')"
    )
    op.execute(
        "DELETE FROM instance_memberships "
        "WHERE member_type IN ('layout','role','team')"
    )
    _rebuild_member_type_check(_MEMBER_OLD)
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_OLD)
    for model in (Team, Role, Layout):
        if model.__tablename__ in _tables():
            model.__table__.drop(bind)
