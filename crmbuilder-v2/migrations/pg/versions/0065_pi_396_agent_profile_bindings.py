"""REQ-472 / PI-396 (PG chain) — registry-native agent-profile bindings.

Companion to the SQLite-chain ``0108``. Adds ``agent_profile_bindings``:
profile → skill/governance_rule bindings with the registry's nullable
``engagement_id`` scope (NULL = a system-baseline binding every engagement
inherits at contract resolution; set = that engagement's overlay).
``mode='disable'`` (engagement-scoped) masks the baseline binding of the same
target. Existing per-engagement reference edges keep working unchanged and are
NOT migrated. No shared-CHECK rebuilds: bindings are not an ``ENTITY_TYPES``
member and are not referenceable from ``refs``.

PG chain head 0064 -> 0065. This is the migration walked against the live
Postgres store (``alembic -c migrations/pg/alembic.ini upgrade head``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import BINDING_MODES, BINDING_TARGET_TYPES, _check_in

revision: str = "0065_pi_396_agent_profile_bindings"
down_revision: str | None = "0064_pi_357_knowledge_structures"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_profile_bindings",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("profile_id", sa.String(length=32), nullable=False),
        sa.Column("target_type", sa.String(length=16), nullable=False),
        sa.Column("target_id", sa.String(length=32), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False, server_default="bind"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["agent_profiles.identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            _check_in("target_type", BINDING_TARGET_TYPES),
            name="ck_apb_target_type",
        ),
        sa.CheckConstraint(_check_in("mode", BINDING_MODES), name="ck_apb_mode"),
    )
    op.create_index(
        "ix_apb_profile", "agent_profile_bindings", ["profile_id"]
    )
    op.create_index(
        "ix_apb_engagement", "agent_profile_bindings", ["engagement_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_apb_engagement", table_name="agent_profile_bindings")
    op.drop_index("ix_apb_profile", table_name="agent_profile_bindings")
    op.drop_table("agent_profile_bindings")
