"""PI-413 (REQ-499) — workflows gain per-instance membership.

The audit now reads the Workflow records an Advanced-Pack instance holds
(live-verified 2026-09-01 on CBMTEST: the generic record path enumerates
them) and records what it saw, so ``instance_memberships.member_type``
admits ``workflow``. Detection only — emitting and applying workflows stay
deferred until the design carries workflow content (DEC-926).

Rebuilds ``ck_instance_membership_member_type`` from the current vocab
(superset — no row invalidated); inspector-guarded so the chain is safe to
enter mid-stream. Mirrors 0120/0121/0131.

SQLite chain head 0134 -> 0135. Companion PG-chain delta:
``migrations/pg/versions/0092_pi_413_workflow_membership.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_MEMBER_TYPES, _check_in

revision: str = "0135_pi_413_workflow_membership"
down_revision: str | None = "0134_pi_412_instance_stamp_reading"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW = "workflow"
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
