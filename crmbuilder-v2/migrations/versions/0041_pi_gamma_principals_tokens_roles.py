"""PI-gamma — identity/RBAC tables: principals, api_tokens, role_assignments.

System/shared tables (no engagement_id discriminator): a principal spans
engagements; its per-engagement rights live in role_assignments. Mirrors the ORM
models in ``access/models.py`` (PrincipalRow / ApiTokenRow / RoleAssignmentRow).

SQLite chain head 0040 -> 0041. The companion PG-chain delta is
``migrations/pg/versions/0003_pi_gamma_principals_tokens_roles.py`` (the
PI-alpha dual-head posture: PG is not replayed through this batch chain).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_pi_gamma_principals_tokens_roles"
down_revision: str | None = "0040_pi_beta_drop_engagement_export_dir"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    # Guarded create: a no-op for tables already present when the schema was
    # materialised from the current ORM models (the migration-from-create_all
    # test path runs ``upgrade head`` over a DB that already has these tables).
    have = _tables()
    if "principals" not in have:
        _create_principals()
    if "api_tokens" not in have:
        _create_api_tokens()
    if "role_assignments" not in have:
        _create_role_assignments()


def _create_principals() -> None:
    op.create_table(
        "principals",
        sa.Column("principal_id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("identity", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("agent_tier", sa.String(length=32), nullable=True),
        sa.Column("agent_area", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "principal_id GLOB 'PRN-[0-9][0-9][0-9]'",
            name="ck_principal_identifier_format",
        ),
        sa.CheckConstraint(
            "kind IN ('human', 'service_agent')",
            name="ck_principal_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_principal_status",
        ),
        sa.PrimaryKeyConstraint("principal_id"),
    )
    op.create_index("ix_principals_status", "principals", ["status"])
    op.create_index("ix_principals_kind", "principals", ["kind"])


def _create_api_tokens() -> None:
    op.create_table(
        "api_tokens",
        sa.Column("token_id", sa.String(length=32), nullable=False),
        sa.Column("principal_id", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "token_id GLOB 'TOK-[0-9][0-9][0-9][0-9]'",
            name="ck_api_token_identifier_format",
        ),
        sa.CheckConstraint(
            "LENGTH(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'",
            name="ck_api_token_hash_hex",
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["principals.principal_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("token_id"),
        sa.UniqueConstraint("token_hash", name="ux_api_tokens_hash"),
    )
    op.create_index("ix_api_tokens_principal", "api_tokens", ["principal_id"])


def _create_role_assignments() -> None:
    op.create_table(
        "role_assignments",
        sa.Column(
            "role_assignment_id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'editor', 'viewer', 'orchestrator', "
            "'pi_lead', 'phase_specialist', 'area_specialist')",
            name="ck_role_assignment_role",
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["principals.principal_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_assignment_id"),
        sa.UniqueConstraint(
            "principal_id",
            "engagement_id",
            "role",
            name="ux_role_assignments_principal_engagement_role",
        ),
    )
    op.create_index(
        "ix_role_assignments_principal", "role_assignments", ["principal_id"]
    )
    op.create_index(
        "ix_role_assignments_engagement", "role_assignments", ["engagement_id"]
    )


def downgrade() -> None:
    have = _tables()
    if "role_assignments" in have:
        op.drop_table("role_assignments")
    if "api_tokens" in have:
        op.drop_table("api_tokens")
    if "principals" in have:
        op.drop_table("principals")
