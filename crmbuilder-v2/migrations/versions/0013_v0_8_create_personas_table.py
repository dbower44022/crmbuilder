"""v0.5+ persona — create personas table + refs/change_log CHECK extensions

Revision ID: 0013_v0_8_create_personas_table
Revises: 0012_v0_8_commits_and_blocked_by_rename
Create Date: 2026-05-25

PI-003. Lands the storage foundation for the ``persona`` methodology
entity type per ``methodology-schema-specs/persona.md`` v1.0.

Operations, in order:

1. Create the ``personas`` table per persona.md §3.2 — nine columns,
   two CHECK constraints (identifier format, status enum), two indexes.
2. Extend ``refs.source_type`` / ``refs.target_type`` CHECKs to admit
   ``'persona'``; extend ``refs.relationship_kind`` to admit
   ``'persona_scopes_to_domain'`` and ``'persona_realized_as_entity'``.
   All three CHECK swaps in a single ``batch_alter_table`` recopy.
3. Extend ``change_log.entity_type`` CHECK to admit ``'persona'``.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_v0_8_create_personas_table"
down_revision: Union[str, None] = "0012_v0_8_commits_and_blocked_by_rename"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constants ---------------------------------------------------

# Source/target type sets extended with 'persona'. Sorted alphabetically.
_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'persona', "
    "'planning_item', 'process', 'reference_book', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'persona', "
    "'planning_item', 'process', 'reference_book', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)

# relationship_kind CHECK extended with the two persona-source kinds.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'persona_realized_as_entity', 'persona_scopes_to_domain', "
    "'process_hands_off_to_process', 'references', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# Originals from 0012 — used by downgrade to restore.
_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'references', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# --- change_log CHECK constants --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'persona', "
    "'planning_item', 'process', 'reference', 'reference_book', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference', 'reference_book', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
)


def upgrade() -> None:
    # 1. Create personas table per persona.md §3.2.
    op.create_table(
        "personas",
        sa.Column("persona_identifier", sa.String(length=32), nullable=False),
        sa.Column("persona_name", sa.String(length=255), nullable=False),
        sa.Column("persona_role_summary", sa.Text(), nullable=False),
        sa.Column("persona_responsibilities", sa.Text(), nullable=True),
        sa.Column("persona_notes", sa.Text(), nullable=True),
        sa.Column("persona_status", sa.String(length=16), nullable=False),
        sa.Column(
            "persona_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "persona_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "persona_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "persona_identifier GLOB 'PER-[0-9][0-9][0-9]'",
            name="ck_persona_identifier_format",
        ),
        sa.CheckConstraint(
            "persona_status IN ('candidate', 'confirmed', 'deferred')",
            name="ck_persona_status",
        ),
        sa.PrimaryKeyConstraint("persona_identifier"),
    )
    with op.batch_alter_table("personas", schema=None) as batch_op:
        batch_op.create_index(
            "ix_personas_persona_status", ["persona_status"], unique=False
        )
        batch_op.create_index(
            "ix_personas_persona_deleted_at",
            ["persona_deleted_at"],
            unique=False,
        )

    # 2. refs CHECK extensions — single recopy for all three swaps.
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

    # 3. change_log entity_type CHECK extension — admit 'persona'.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )


def downgrade() -> None:
    """Reverse the upgrade.

    The persona rows are dropped along with the table; any rows in
    ``refs`` with ``source_type='persona'`` / ``target_type='persona'``
    or with relationship kinds ``persona_scopes_to_domain`` /
    ``persona_realized_as_entity`` will fail the restored v0.8 CHECK
    constraints. Operators must hand-clear such rows before downgrading.
    """
    # Reverse change_log CHECK.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _OLD_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # Reverse refs CHECKs — single recopy.
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

    # Drop the personas table (with its indexes).
    with op.batch_alter_table("personas", schema=None) as batch_op:
        batch_op.drop_index("ix_personas_persona_deleted_at")
        batch_op.drop_index("ix_personas_persona_status")
    op.drop_table("personas")
