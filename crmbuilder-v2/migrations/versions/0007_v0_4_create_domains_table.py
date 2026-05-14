"""v0.4 slice B — create the domains table

Revision ID: 0007_v0_4_create_domains_table
Revises: 0006_v0_4_foundation_refs_check_extensions
Create Date: 2026-05-14

UI v0.4 slice B. Adds the ``domains`` table — the first methodology
entity type — per ``methodology-schema-specs/domain.md`` section 3.2.

The table follows the parent-prefix field-naming convention: every
column is prefixed ``domain_``. The primary key is the prefixed-string
identifier ``domain_identifier`` (format ``DOM-NNN``, enforced by a
SQLite GLOB CHECK) — there is no integer surrogate ``id`` column.
``domain_status`` is constrained to the three-value lifecycle vocab;
``domain_deleted_at`` carries v2's standard nullable soft-delete column.
Case-insensitive ``domain_name`` uniqueness is enforced at the access
layer (no UNIQUE index here), per the spec.

This migration also extends the ``change_log.entity_type`` CHECK
constraint to admit the four methodology entity types (``domain``,
``entity``, ``process``, ``crm_candidate``). Slice A added these to the
``vocab.ENTITY_TYPES`` frozenset and extended the ``refs`` CHECK
constraints to match, but left ``change_log`` on its catalog-era value
set; the domains repository emits change-log rows, so the constraint
must admit ``domain``. Extending it to all four methodology types now
keeps the migrated schema in lockstep with ``Base.metadata`` (which
already derives its CHECK from ``ENTITY_TYPES``) and means slices C–E
need not re-touch this constraint.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_v0_4_create_domains_table"
down_revision: Union[str, None] = "0006_v0_4_foundation_refs_check_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'reference', 'risk', 'session', 'status', 'topic')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'reference', 'risk', 'session', "
    "'status', 'topic')"
)


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("domain_identifier", sa.String(length=32), nullable=False),
        sa.Column("domain_name", sa.String(length=255), nullable=False),
        sa.Column("domain_status", sa.String(length=16), nullable=False),
        sa.Column("domain_purpose", sa.Text(), nullable=False),
        sa.Column("domain_description", sa.Text(), nullable=False),
        sa.Column("domain_notes", sa.Text(), nullable=True),
        sa.Column(
            "domain_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "domain_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "domain_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "domain_identifier GLOB 'DOM-[0-9][0-9][0-9]'",
            name="ck_domain_identifier_format",
        ),
        sa.CheckConstraint(
            "domain_status IN ('candidate', 'confirmed', 'deferred')",
            name="ck_domain_status",
        ),
        sa.PrimaryKeyConstraint("domain_identifier"),
    )
    with op.batch_alter_table("domains", schema=None) as batch_op:
        batch_op.create_index(
            "ix_domains_domain_status", ["domain_status"], unique=False
        )
        batch_op.create_index(
            "ix_domains_domain_deleted_at",
            ["domain_deleted_at"],
            unique=False,
        )

    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )


def downgrade() -> None:
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _OLD_CHANGELOG_ENTITY_TYPE_CHECK
        )

    with op.batch_alter_table("domains", schema=None) as batch_op:
        batch_op.drop_index("ix_domains_domain_deleted_at")
        batch_op.drop_index("ix_domains_domain_status")
    op.drop_table("domains")
