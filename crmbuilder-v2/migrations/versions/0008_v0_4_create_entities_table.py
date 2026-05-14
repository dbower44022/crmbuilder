"""v0.4 slice C — create the entities table

Revision ID: 0008_v0_4_create_entities_table
Revises: 0007_v0_4_create_domains_table
Create Date: 2026-05-14

UI v0.4 slice C. Adds the ``entities`` table — the second methodology
entity type — per ``methodology-schema-specs/entity.md`` section 3.2.

The table follows the parent-prefix field-naming convention: every
column is prefixed ``entity_``. The primary key is the prefixed-string
identifier ``entity_identifier`` (format ``ENT-NNN``, enforced by a
SQLite GLOB CHECK) — there is no integer surrogate ``id`` column.
``entity_status`` is constrained to the three-value lifecycle vocab;
``entity_deleted_at`` carries v2's standard nullable soft-delete column.
Case-insensitive ``entity_name`` uniqueness is enforced at the access
layer (no UNIQUE index here), per the spec.

No FK column to ``domain`` — entity-to-domain affiliations live in the
``refs`` table as ``entity_scopes_to_domain`` references. Slice A added
that vocab kind and extended the ``refs`` CHECK constraints; slice B's
migration already extended the ``change_log.entity_type`` CHECK to
admit all four methodology entity types, so this migration touches the
``entities`` table only.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_v0_4_create_entities_table"
down_revision: Union[str, None] = "0007_v0_4_create_domains_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("entity_identifier", sa.String(length=32), nullable=False),
        sa.Column("entity_name", sa.String(length=255), nullable=False),
        sa.Column("entity_status", sa.String(length=16), nullable=False),
        sa.Column("entity_description", sa.Text(), nullable=False),
        sa.Column("entity_notes", sa.Text(), nullable=True),
        sa.Column(
            "entity_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "entity_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "entity_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "entity_identifier GLOB 'ENT-[0-9][0-9][0-9]'",
            name="ck_entity_identifier_format",
        ),
        sa.CheckConstraint(
            "entity_status IN ('candidate', 'confirmed', 'deferred')",
            name="ck_entity_status",
        ),
        sa.PrimaryKeyConstraint("entity_identifier"),
    )
    with op.batch_alter_table("entities", schema=None) as batch_op:
        batch_op.create_index(
            "ix_entities_entity_status", ["entity_status"], unique=False
        )
        batch_op.create_index(
            "ix_entities_entity_deleted_at",
            ["entity_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("entities", schema=None) as batch_op:
        batch_op.drop_index("ix_entities_entity_deleted_at")
        batch_op.drop_index("ix_entities_entity_status")
    op.drop_table("entities")
