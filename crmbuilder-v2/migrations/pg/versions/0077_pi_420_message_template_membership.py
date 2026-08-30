"""PI-420 (REQ-124 audit half) — email templates gain per-instance membership.

``instance_memberships.member_type`` admits ``message_template``; rebuilds
``ck_instance_membership_member_type`` from the current vocab (superset — no
row invalidated). No new entity type, no new relationship kind. Mirrors 0019.

PG chain head 0076 -> 0077. Companion SQLite-chain delta:
``migrations/versions/0120_pi_420_message_template_membership.py``.

NOTE (live application): applied to the live Postgres store through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and performed by Doug
(GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_MEMBER_TYPES, _check_in

revision: str = "0077_pi_420_message_template_membership"
down_revision: str | None = "0076_pi_422_entity_formula_scripts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "message_template"
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
