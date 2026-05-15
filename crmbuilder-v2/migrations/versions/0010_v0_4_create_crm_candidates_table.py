"""v0.4 slice E — create the crm_candidates table

Revision ID: 0010_v0_4_create_crm_candidates_table
Revises: 0009_v0_4_create_processes_table
Create Date: 2026-05-14

UI v0.4 slice E. Adds the ``crm_candidates`` table — the fourth and
final methodology entity type — per ``methodology-schema-specs/
crm_candidate.md`` section 3.2.

The table follows the parent-prefix field-naming convention: every
column is prefixed ``crm_candidate_``. The primary key is the
prefixed-string identifier ``crm_candidate_identifier`` (format
``CRM-NNN``, enforced by a SQLite GLOB CHECK) — there is no integer
surrogate ``id`` column. The four-value ``crm_candidate_status`` enum
(``active`` / ``selected`` / ``declined`` / ``removed``) is enforced
at the database boundary; the singleton-``selected`` constraint per
spec section 3.4.3 is enforced exclusively at the access layer (not as
a SQL CHECK or partial UNIQUE) per spec section 3.5.4.

Slice A's ``ENTITY_TYPES`` already included ``crm_candidate``, and
slice B's migration extended the ``change_log.entity_type`` CHECK to
admit all four methodology entity types, so this migration touches the
``crm_candidates`` table only.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_v0_4_create_crm_candidates_table"
down_revision: Union[str, None] = "0009_v0_4_create_processes_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_candidates",
        sa.Column(
            "crm_candidate_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "crm_candidate_name", sa.String(length=255), nullable=False
        ),
        sa.Column(
            "crm_candidate_status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "crm_candidate_fit_reason", sa.Text(), nullable=False
        ),
        sa.Column("crm_candidate_notes", sa.Text(), nullable=True),
        sa.Column(
            "crm_candidate_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "crm_candidate_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "crm_candidate_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "crm_candidate_identifier GLOB 'CRM-[0-9][0-9][0-9]'",
            name="ck_crm_candidate_identifier_format",
        ),
        sa.CheckConstraint(
            "crm_candidate_status IN "
            "('active', 'declined', 'removed', 'selected')",
            name="ck_crm_candidate_status",
        ),
        sa.PrimaryKeyConstraint("crm_candidate_identifier"),
    )
    with op.batch_alter_table("crm_candidates", schema=None) as batch_op:
        batch_op.create_index(
            "ix_crm_candidates_crm_candidate_status",
            ["crm_candidate_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_crm_candidates_crm_candidate_deleted_at",
            ["crm_candidate_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("crm_candidates", schema=None) as batch_op:
        batch_op.drop_index("ix_crm_candidates_crm_candidate_deleted_at")
        batch_op.drop_index("ix_crm_candidates_crm_candidate_status")
    op.drop_table("crm_candidates")
