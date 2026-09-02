"""PI-412 (REQ-498) — the fleet view's queryable copy of each stamp reading.

The design-version stamp lives IN the instance (REQ-495); the fleet view must
be queryable without reaching every instance, so the audit's settings pass
copies what it read — ``standardVersion``, ``planFingerprint``, and when — onto
the instance record. A failed read leaves the columns untouched, so their age
is visible rather than reset.

PG chain head 0090 -> 0091. Companion of the SQLite-chain
``0134_pi_412_instance_stamp_reading``.

NOTE (live application): the live application goes through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and is performed by
Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0091_pi_412_instance_stamp_reading"
down_revision: str | None = "0090_pi_448_audit_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    ("instance_standard_version", sa.Text()),
    ("instance_plan_fingerprint", sa.Text()),
    ("instance_stamp_read_at", sa.DateTime(timezone=True)),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "instances" not in _tables():
        return
    have = _cols("instances")
    missing = [(n, t) for n, t in _COLUMNS if n not in have]
    if not missing:
        return
    with op.batch_alter_table("instances") as batch:
        for name, type_ in missing:
            batch.add_column(sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    if "instances" not in _tables():
        return
    have = _cols("instances")
    with op.batch_alter_table("instances") as batch:
        for name, _type in _COLUMNS:
            if name in have:
                batch.drop_column(name)
