"""v0.4 foundation — refs CHECK constraint extensions

Revision ID: 0006_v0_4_foundation_refs_check_extensions
Revises: 0005_catalog_universal_refs
Create Date: 2026-05-14

UI v0.4 slice A. Extends three CHECK constraints on the ``refs`` table
so the universal references table can host the four new methodology
entity types and two new relationship kinds:

* ``refs.source_type`` and ``refs.target_type`` admit ``domain``,
  ``entity``, ``process``, ``crm_candidate``.
* ``refs.relationship_kind`` admits ``entity_scopes_to_domain``
  (DEC-053) and ``process_hands_off_to_process`` (DEC-058).

SQLite cannot ALTER a CHECK constraint in place; ``batch_alter_table``
copies the table with the new constraint. Mirrors the pattern of
``0005_catalog_universal_refs``. Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0006_v0_4_foundation_refs_check_extensions"
down_revision: Union[str, None] = "0005_catalog_universal_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'risk', 'session', 'status', 'topic')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'risk', 'session', 'status', 'topic')"
)
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('affects', 'blocks', 'covers', 'decided_in', "
    "'entity_scopes_to_domain', 'is_about', 'process_hands_off_to_process', "
    "'references', 'supersedes')"
)

_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'risk', 'session', 'status', 'topic')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'decision', 'planning_item', 'risk', 'session', 'status', 'topic')"
)
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('affects', 'blocks', 'covers', 'decided_in', "
    "'is_about', 'references', 'supersedes')"
)


def upgrade() -> None:
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_source_type", _NEW_REF_SOURCE_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_target_type", _NEW_REF_TARGET_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )


def downgrade() -> None:
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_source_type", _OLD_REF_SOURCE_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_target_type", _OLD_REF_TARGET_TYPE_CHECK
        )
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )
