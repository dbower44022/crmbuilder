"""catalog universal references integration

Revision ID: 0005_catalog_universal_refs
Revises: 0004_catalog_seed
Create Date: 2026-05-14

Extends the existing CHECK constraints on ``refs.source_type``,
``refs.target_type``, and ``change_log.entity_type`` to admit the two
new catalog entity types (``catalog_entity``, ``catalog_attribute``),
per the universal references integration in catalog-ingestion-PRD-v0.1.md
section 3.

Other v2 entities (decisions, planning items, future methodology
entities) can now reference catalog rows by target_type=catalog_entity
or catalog_attribute, target_id=catalog_id (or ``{catalog_id}.{name}``
for attributes).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_catalog_universal_refs"
down_revision: Union[str, None] = "0004_catalog_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_REF_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'risk', 'session', 'status', 'topic')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'risk', 'session', 'status', 'topic')"
)
_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'reference', 'risk', 'session', 'status', 'topic')"
)


def upgrade() -> None:
    # SQLite cannot ALTER CHECK constraints in place; batch_alter_table
    # copies the table with the new constraint.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_source_type", _NEW_REF_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_target_type", _NEW_REF_TARGET_TYPE_CHECK
        )

    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )


def downgrade() -> None:
    _OLD_REF_TYPE_CHECK = (
        "source_type IN ('charter', 'decision', 'planning_item', "
        "'risk', 'session', 'status', 'topic')"
    )
    _OLD_REF_TARGET_TYPE_CHECK = (
        "target_type IN ('charter', 'decision', 'planning_item', "
        "'risk', 'session', 'status', 'topic')"
    )
    _OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
        "entity_type IN ('charter', 'decision', 'planning_item', "
        "'reference', 'risk', 'session', 'status', 'topic')"
    )

    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_source_type", _OLD_REF_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_target_type", _OLD_REF_TARGET_TYPE_CHECK
        )

    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _OLD_CHANGELOG_ENTITY_TYPE_CHECK
        )
