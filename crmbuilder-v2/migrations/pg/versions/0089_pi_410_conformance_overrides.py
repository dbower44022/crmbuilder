"""PI-410 (REQ-494, PG chain) — one-deploy conformance overrides.

Companion to the SQLite-chain ``0132``. PG chain head 0088 -> 0089.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0089_pi_410_conformance_overrides"
down_revision: str | None = "0088_pi_406_system_setting_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "conformance_overrides"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _TABLE in _tables():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(length=32),
            sa.ForeignKey("engagements.engagement_identifier"),
            nullable=False,
        ),
        sa.Column("instance_identifier", sa.String(length=32), nullable=False),
        sa.Column("authorized_by", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["engagement_id", "instance_identifier"],
            ["instances.engagement_id", "instances.instance_identifier"],
            ondelete="CASCADE",
            name="fk_conformance_overrides_instance",
        ),
    )
    op.create_index(
        "ix_conformance_overrides_instance", _TABLE, ["instance_identifier"]
    )


def downgrade() -> None:
    if _TABLE not in _tables():
        return
    op.drop_index("ix_conformance_overrides_instance", table_name=_TABLE)
    op.drop_table(_TABLE)
