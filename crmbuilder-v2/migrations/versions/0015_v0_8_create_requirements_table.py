"""v0.5+ requirement — create requirements table + refs/change_log CHECK extensions

Revision ID: 0015_v0_8_create_requirements_table
Revises: 0014_v0_8_create_fields_table
Create Date: 2026-05-26

PI-004 cohort sibling. Lands the storage foundation for the
``requirement`` methodology entity type per
``methodology-schema-specs/requirement.md`` v1.0.

Operations, in order:

1. Create the ``requirements`` table per requirement.md §3.2 — ten
   columns (seven substantive plus identifier plus three timestamps),
   three CHECK constraints (identifier format, status enum, priority
   enum), three indexes.
2. Extend ``refs.source_type`` / ``refs.target_type`` CHECKs to admit
   ``'requirement'``; extend ``refs.relationship_kind`` to admit all
   five new ``requirement_*`` kinds (``requirement_scopes_to_domain``,
   ``requirement_touches_entity``, ``requirement_touches_field``,
   ``requirement_realized_by_process``,
   ``requirement_verified_by_test_spec``). All three CHECK swaps in a
   single ``batch_alter_table`` recopy.
3. Extend ``change_log.entity_type`` CHECK to admit ``'requirement'``.

Per requirement.md §3.3.1 admitting the five new kinds proactively is
forward-compatible — a row attempting ``(requirement, test_spec)`` will
still fail the ``target_type`` CHECK because ``test_spec`` is not yet
admitted as a target type. Field IS now live so
``(requirement, field)`` is fully usable; ``test_spec`` lands with its
own PI-004 sibling build.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_v0_8_create_requirements_table"
down_revision: Union[str, None] = "0014_v0_8_create_fields_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constants ---------------------------------------------------

# Source/target type sets extended with 'requirement'. Sorted alphabetically.
_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'requirement', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'requirement', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
)

# relationship_kind CHECK extended with the five new requirement-source kinds.
# Sorted alphabetically.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'field_belongs_to_entity', 'is_about', "
    "'persona_realized_as_entity', 'persona_scopes_to_domain', "
    "'process_hands_off_to_process', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# Originals from 0014 — used by downgrade to restore.
_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'field_belongs_to_entity', 'is_about', "
    "'persona_realized_as_entity', 'persona_scopes_to_domain', "
    "'process_hands_off_to_process', 'references', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# --- change_log CHECK constants --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference', 'reference_book', "
    "'requirement', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference', 'reference_book', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
)


def upgrade() -> None:
    # 1. Create requirements table per requirement.md §3.2.
    #
    # Ten columns: seven substantive (identifier, name, description,
    # acceptance_summary, priority, status, notes) plus three timestamps
    # (created_at, updated_at, deleted_at). No FK columns — the five
    # outbound relationships live in the ``refs`` table per §3.3.1.
    # No SQL-level UNIQUE on requirement_name — case-insensitive global
    # uniqueness is enforced at the access layer per §3.2.1.
    op.create_table(
        "requirements",
        sa.Column(
            "requirement_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("requirement_name", sa.String(length=255), nullable=False),
        sa.Column("requirement_description", sa.Text(), nullable=False),
        sa.Column(
            "requirement_acceptance_summary", sa.Text(), nullable=False
        ),
        sa.Column("requirement_priority", sa.String(length=16), nullable=False),
        sa.Column("requirement_status", sa.String(length=16), nullable=False),
        sa.Column("requirement_notes", sa.Text(), nullable=True),
        sa.Column(
            "requirement_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "requirement_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "requirement_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "requirement_identifier GLOB 'REQ-[0-9][0-9][0-9]'",
            name="ck_requirement_identifier_format",
        ),
        sa.CheckConstraint(
            "requirement_status IN ('candidate', 'confirmed', 'deferred')",
            name="ck_requirement_status",
        ),
        sa.CheckConstraint(
            "requirement_priority IN ('could', 'must', 'should', 'wont')",
            name="ck_requirement_priority",
        ),
        sa.PrimaryKeyConstraint("requirement_identifier"),
    )
    with op.batch_alter_table("requirements", schema=None) as batch_op:
        batch_op.create_index(
            "ix_requirements_requirement_status",
            ["requirement_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_requirements_requirement_priority",
            ["requirement_priority"],
            unique=False,
        )
        batch_op.create_index(
            "ix_requirements_requirement_deleted_at",
            ["requirement_deleted_at"],
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

    # 3. change_log entity_type CHECK extension — admit 'requirement'.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )


def downgrade() -> None:
    """Reverse the upgrade.

    The requirement rows are dropped along with the table; any rows in
    ``refs`` with ``source_type='requirement'`` / ``target_type='requirement'``
    or with relationship kinds matching ``requirement_*`` will fail the
    restored v0.5+ CHECK constraints. Operators must hand-clear such
    rows before downgrading.
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

    # Drop the requirements table (with its indexes).
    with op.batch_alter_table("requirements", schema=None) as batch_op:
        batch_op.drop_index("ix_requirements_requirement_deleted_at")
        batch_op.drop_index("ix_requirements_requirement_priority")
        batch_op.drop_index("ix_requirements_requirement_status")
    op.drop_table("requirements")
