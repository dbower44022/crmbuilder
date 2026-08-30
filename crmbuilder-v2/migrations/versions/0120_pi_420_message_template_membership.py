"""PI-420 (REQ-124 audit half) — email templates gain per-instance membership.

The audit now reconciles each entity's EmailTemplate records into the existing
``message_templates`` table and records which instances carry each template, so
``instance_memberships.member_type`` admits ``message_template``. Rebuilds
``ck_instance_membership_member_type`` from the current vocab (superset — no
row invalidated); inspector-guarded so the chain is safe to enter mid-stream.
No new entity type and no new relationship kind. Mirrors 0061.

SQLite chain head 0119 -> 0120. Companion PG-chain delta:
``migrations/pg/versions/0077_pi_420_message_template_membership.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_MEMBER_TYPES, _check_in

revision: str = "0120_pi_420_message_template_membership"
down_revision: str | None = "0119_pi_422_entity_formula_scripts"
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
    with op.batch_alter_table("instance_memberships") as batch:
        batch.drop_constraint("ck_instance_membership_member_type", type_="check")
        batch.create_check_constraint(
            "ck_instance_membership_member_type",
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
