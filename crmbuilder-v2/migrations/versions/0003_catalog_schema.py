"""catalog schema

Revision ID: 0003_catalog_schema
Revises: 0002_soft_delete_decisions
Create Date: 2026-05-13

Ten tables holding the base entity catalog (catalog-ingestion-PRD-v0.1.md
section 4). Idempotent ``upsert-by-catalog_id`` keys live on the
``catalog_id`` text identifier on ``catalog_entity`` and on the
``(catalog_entity_id, name)`` pair for ``catalog_attribute``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_catalog_schema"
down_revision: Union[str, None] = "0002_soft_delete_decisions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "catalog_entity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("tier", sa.Integer(), nullable=False),
        sa.Column("entry_kind", sa.String(length=16), nullable=False),
        sa.Column("parent_entity_id", sa.Integer(), nullable=True),
        sa.Column("discriminator_attribute", sa.String(length=128), nullable=True),
        sa.Column("discriminator_value", sa.String(length=255), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("business_context", sa.Text(), nullable=False),
        sa.Column("data_model_role", sa.String(length=32), nullable=False),
        sa.Column("typically_required", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tier BETWEEN 1 AND 5", name="ck_catalog_entity_tier"
        ),
        sa.CheckConstraint(
            "entry_kind IN ('subclass', 'universal')",
            name="ck_catalog_entity_entry_kind",
        ),
        sa.CheckConstraint(
            "data_model_role IN ('anchor', 'classifier', 'document', 'event', 'junction', 'log')",
            name="ck_catalog_entity_data_model_role",
        ),
        sa.ForeignKeyConstraint(
            ["parent_entity_id"], ["catalog_entity.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("catalog_id"),
    )
    with op.batch_alter_table("catalog_entity", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_entity_catalog_id", ["catalog_id"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_entity_tier_kind", ["tier", "entry_kind"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_entity_parent", ["parent_entity_id"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_entity_is_deleted", ["is_deleted"], unique=False
        )

    op.create_table(
        "catalog_entity_synonym",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_entity_id", sa.Integer(), nullable=False),
        sa.Column("synonym", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("catalog_entity_synonym", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_entity_synonym_entity", ["catalog_entity_id"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_entity_synonym_text", ["synonym"], unique=False
        )

    op.create_table(
        "catalog_entity_system",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_entity_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(length=32), nullable=False),
        sa.Column("system_name", sa.String(length=255), nullable=False),
        sa.Column("api_name", sa.String(length=255), nullable=True),
        sa.Column("is_standard", sa.String(length=16), nullable=False),
        sa.Column("mechanism", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("docs_url", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "system IN ('attio', 'bloomerang', 'civicrm', 'espocrm', 'hubspot', 'salesforce', 'salesforce_npsp')",
            name="ck_catalog_entity_system_system",
        ),
        sa.CheckConstraint(
            "is_standard IN ('false', 'partial', 'true')",
            name="ck_catalog_entity_system_is_standard",
        ),
        sa.CheckConstraint(
            "mechanism IS NULL OR mechanism IN ('contact_subtype', 'custom_property', 'entity_inheritance', 'record_type', 'separate_object', 'type_discriminator')",
            name="ck_catalog_entity_system_mechanism",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_entity_id", "system", name="uq_catalog_entity_system"
        ),
    )
    with op.batch_alter_table("catalog_entity_system", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_entity_system_entity", ["catalog_entity_id"], unique=False
        )

    op.create_table(
        "catalog_source",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_entity_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("catalog_source", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_source_entity", ["catalog_entity_id"], unique=False
        )

    op.create_table(
        "catalog_attribute",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_entity_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("max_length", sa.Integer(), nullable=True),
        sa.Column("reference_target", sa.String(length=128), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("usage", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "type IN ('address', 'attachment', 'autonumber', 'boolean', 'currency', 'date', 'datetime', 'decimal', 'email', 'enum', 'formula', 'integer', 'multienum', 'multireference', 'phone', 'reference', 'richtext', 'string', 'text', 'time', 'url')",
            name="ck_catalog_attribute_type",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_entity_id", "name", name="uq_catalog_attribute_entity_name"
        ),
    )
    with op.batch_alter_table("catalog_attribute", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_attribute_entity", ["catalog_entity_id"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_attribute_name", ["name"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_attribute_is_deleted", ["is_deleted"], unique=False
        )

    op.create_table(
        "catalog_attribute_enum_value",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_attribute_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_attribute_id"],
            ["catalog_attribute.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "catalog_attribute_enum_value", schema=None
    ) as batch_op:
        batch_op.create_index(
            "ix_catalog_attribute_enum_value_attr",
            ["catalog_attribute_id"],
            unique=False,
        )

    op.create_table(
        "catalog_attribute_synonym",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_attribute_id", sa.Integer(), nullable=False),
        sa.Column("synonym", sa.String(length=255), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["catalog_attribute_id"],
            ["catalog_attribute.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table(
        "catalog_attribute_synonym", schema=None
    ) as batch_op:
        batch_op.create_index(
            "ix_catalog_attribute_synonym_attr",
            ["catalog_attribute_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_catalog_attribute_synonym_text", ["synonym"], unique=False
        )

    op.create_table(
        "catalog_attribute_presence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_attribute_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("api_name", sa.String(length=255), nullable=True),
        sa.CheckConstraint(
            "system IN ('attio', 'bloomerang', 'civicrm', 'espocrm', 'hubspot', 'salesforce', 'salesforce_npsp')",
            name="ck_catalog_attribute_presence_system",
        ),
        sa.CheckConstraint(
            "status IN ('absent', 'custom', 'standard')",
            name="ck_catalog_attribute_presence_status",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_attribute_id"],
            ["catalog_attribute.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_attribute_id",
            "system",
            name="uq_catalog_attribute_presence",
        ),
    )
    with op.batch_alter_table(
        "catalog_attribute_presence", schema=None
    ) as batch_op:
        batch_op.create_index(
            "ix_catalog_attribute_presence_attr",
            ["catalog_attribute_id"],
            unique=False,
        )

    op.create_table(
        "catalog_relationship",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_entity_id", sa.Integer(), nullable=False),
        sa.Column("target_entity_id", sa.Integer(), nullable=False),
        sa.Column("cardinality", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "cardinality IN ('many-to-many', 'many-to-one', 'one-to-many', 'one-to-one')",
            name="ck_catalog_relationship_cardinality",
        ),
        sa.CheckConstraint(
            "role IN ('child', 'parent', 'peer')",
            name="ck_catalog_relationship_role",
        ),
        sa.ForeignKeyConstraint(
            ["source_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["target_entity_id"], ["catalog_entity.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("catalog_relationship", schema=None) as batch_op:
        batch_op.create_index(
            "ix_catalog_relationship_source", ["source_entity_id"], unique=False
        )
        batch_op.create_index(
            "ix_catalog_relationship_target", ["target_entity_id"], unique=False
        )

    op.create_table(
        "catalog_relationship_presence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("catalog_relationship_id", sa.Integer(), nullable=False),
        sa.Column("system", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "system IN ('attio', 'bloomerang', 'civicrm', 'espocrm', 'hubspot', 'salesforce', 'salesforce_npsp')",
            name="ck_catalog_relationship_presence_system",
        ),
        sa.CheckConstraint(
            "status IN ('absent', 'custom', 'standard')",
            name="ck_catalog_relationship_presence_status",
        ),
        sa.ForeignKeyConstraint(
            ["catalog_relationship_id"],
            ["catalog_relationship.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "catalog_relationship_id",
            "system",
            name="uq_catalog_relationship_presence",
        ),
    )
    with op.batch_alter_table(
        "catalog_relationship_presence", schema=None
    ) as batch_op:
        batch_op.create_index(
            "ix_catalog_relationship_presence_rel",
            ["catalog_relationship_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "catalog_relationship_presence", schema=None
    ) as batch_op:
        batch_op.drop_index("ix_catalog_relationship_presence_rel")
    op.drop_table("catalog_relationship_presence")
    with op.batch_alter_table("catalog_relationship", schema=None) as batch_op:
        batch_op.drop_index("ix_catalog_relationship_target")
        batch_op.drop_index("ix_catalog_relationship_source")
    op.drop_table("catalog_relationship")
    with op.batch_alter_table(
        "catalog_attribute_presence", schema=None
    ) as batch_op:
        batch_op.drop_index("ix_catalog_attribute_presence_attr")
    op.drop_table("catalog_attribute_presence")
    with op.batch_alter_table(
        "catalog_attribute_synonym", schema=None
    ) as batch_op:
        batch_op.drop_index("ix_catalog_attribute_synonym_text")
        batch_op.drop_index("ix_catalog_attribute_synonym_attr")
    op.drop_table("catalog_attribute_synonym")
    with op.batch_alter_table(
        "catalog_attribute_enum_value", schema=None
    ) as batch_op:
        batch_op.drop_index("ix_catalog_attribute_enum_value_attr")
    op.drop_table("catalog_attribute_enum_value")
    with op.batch_alter_table("catalog_attribute", schema=None) as batch_op:
        batch_op.drop_index("ix_catalog_attribute_is_deleted")
        batch_op.drop_index("ix_catalog_attribute_name")
        batch_op.drop_index("ix_catalog_attribute_entity")
    op.drop_table("catalog_attribute")
    with op.batch_alter_table("catalog_source", schema=None) as batch_op:
        batch_op.drop_index("ix_catalog_source_entity")
    op.drop_table("catalog_source")
    with op.batch_alter_table("catalog_entity_system", schema=None) as batch_op:
        batch_op.drop_index("ix_catalog_entity_system_entity")
    op.drop_table("catalog_entity_system")
    with op.batch_alter_table(
        "catalog_entity_synonym", schema=None
    ) as batch_op:
        batch_op.drop_index("ix_catalog_entity_synonym_text")
        batch_op.drop_index("ix_catalog_entity_synonym_entity")
    op.drop_table("catalog_entity_synonym")
    with op.batch_alter_table("catalog_entity", schema=None) as batch_op:
        batch_op.drop_index("ix_catalog_entity_is_deleted")
        batch_op.drop_index("ix_catalog_entity_parent")
        batch_op.drop_index("ix_catalog_entity_tier_kind")
        batch_op.drop_index("ix_catalog_entity_catalog_id")
    op.drop_table("catalog_entity")
