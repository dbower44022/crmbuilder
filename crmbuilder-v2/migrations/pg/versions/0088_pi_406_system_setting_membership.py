"""PI-406 (REQ-485 audit half, PG chain) — settings gain per-instance membership.

Companion to the SQLite-chain ``0131``. The settings reader is now invoked by
the audit and its observations persisted, so
``instance_memberships.member_type`` admits ``system_setting``. Rebuilds the
CHECK from the current vocab (superset — no row invalidated). Mirrors
0077/0078.

PG chain head 0087 -> 0088.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_MEMBER_TYPES, _check_in

revision: str = "0088_pi_406_system_setting_membership"
down_revision: str | None = "0087_pi_414_field_vocabulary_subtractive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "system_setting"
_MEMBER_NEW = INSTANCE_MEMBERSHIP_MEMBER_TYPES
_MEMBER_OLD = INSTANCE_MEMBERSHIP_MEMBER_TYPES - {_NEW}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_member_type_check(member_types: frozenset[str]) -> None:
    if "instance_memberships" not in _tables():
        return
    op.drop_constraint(
        "ck_instance_membership_member_type", "instance_memberships", type_="check"
    )
    op.create_check_constraint(
        "ck_instance_membership_member_type",
        "instance_memberships",
        _check_in("member_type", member_types),
    )


def upgrade() -> None:
    _rebuild_member_type_check(_MEMBER_NEW)


def downgrade() -> None:
    if "instance_memberships" in _tables():
        op.execute(
            f"DELETE FROM instance_memberships WHERE member_type = '{_NEW}'"
        )
    _rebuild_member_type_check(_MEMBER_OLD)
