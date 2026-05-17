"""create engagements table

Revision ID: 0001_create_engagements_table
Revises:
Create Date: 2026-05-16

v0.5 slice A. Creates the meta DB's ``engagements`` table —
the registry that hosts engagement records at the v2-install level
per ``methodology-schema-specs/engagement.md`` §3.2.

Ten columns matching the parent-prefix field-naming convention from
DEC-046. CHECK constraints enforce the identifier-format and
status-enum at the database boundary; case-insensitive uniqueness on
``engagement_code`` and ``engagement_name`` is enforced via
``LOWER(...)`` expression indexes per the schema's spec.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_engagements_table"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column(
            "engagement_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("engagement_code", sa.String(length=16), nullable=False),
        sa.Column("engagement_name", sa.String(length=255), nullable=False),
        sa.Column("engagement_purpose", sa.Text(), nullable=False),
        sa.Column("engagement_status", sa.String(length=16), nullable=False),
        sa.Column(
            "engagement_last_opened_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("engagement_export_dir", sa.Text(), nullable=True),
        sa.Column(
            "engagement_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "engagement_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "engagement_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "engagement_identifier GLOB 'ENG-[0-9][0-9][0-9]'",
            name="ck_engagement_identifier_format",
        ),
        sa.CheckConstraint(
            "engagement_status IN ('active', 'paused', 'archived')",
            name="ck_engagement_status",
        ),
        sa.PrimaryKeyConstraint("engagement_identifier"),
    )
    with op.batch_alter_table("engagements", schema=None) as batch_op:
        # Case-insensitive uniqueness via LOWER(...) expression indexes.
        batch_op.create_index(
            "ux_engagements_code_lower",
            [sa.text("LOWER(engagement_code)")],
            unique=True,
        )
        batch_op.create_index(
            "ux_engagements_name_lower",
            [sa.text("LOWER(engagement_name)")],
            unique=True,
        )
        batch_op.create_index(
            "ix_engagements_status",
            ["engagement_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_engagements_last_opened_at",
            ["engagement_last_opened_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_engagements_deleted_at",
            ["engagement_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("engagements", schema=None) as batch_op:
        batch_op.drop_index("ix_engagements_deleted_at")
        batch_op.drop_index("ix_engagements_last_opened_at")
        batch_op.drop_index("ix_engagements_status")
        batch_op.drop_index("ux_engagements_name_lower")
        batch_op.drop_index("ux_engagements_code_lower")
    op.drop_table("engagements")
