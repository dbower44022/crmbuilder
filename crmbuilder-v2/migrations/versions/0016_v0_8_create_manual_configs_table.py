"""v0.5+ manual_config — create manual_configs table + refs/change_log CHECK extensions

Revision ID: 0016_v0_8_create_manual_configs_table
Revises: 0015_v0_8_create_requirements_table
Create Date: 2026-05-26

PI-004 cohort sibling. Lands the storage foundation for the
``manual_config`` methodology entity type per
``methodology-schema-specs/manual_config.md`` v1.0.

Operations, in order:

1. Extend ``refs.source_type`` / ``refs.target_type`` CHECKs to admit
   ``'manual_config'``; extend ``refs.relationship_kind`` to admit the
   four new ``manual_config_*`` kinds (``manual_config_scopes_to_domain``,
   ``manual_config_touches_entity``, ``manual_config_touches_field``,
   ``manual_config_realizes_requirement``). All three CHECK swaps in a
   single ``batch_alter_table`` recopy.
2. Extend ``change_log.entity_type`` CHECK to admit ``'manual_config'``.
3. Create the ``manual_configs`` table per manual_config.md §3.2 — twelve
   columns (identifier + nine substantive + three timestamps), three
   CHECK constraints (identifier format, status enum, category enum),
   three indexes (status, category, deleted_at).

All four ``manual_config_*`` relationship-kind values are admitted to
the ``refs.relationship_kind`` CHECK proactively per manual_config.md
§3.3.1. The ``_kinds_for_pair`` clauses for ``(manual_config, field)``
and ``(manual_config, requirement)`` are both fully active because
those sibling entity types are live as of the PI-004 first slice and
PI-004 cohort builds respectively.

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_v0_8_create_manual_configs_table"
down_revision: Union[str, None] = "0015_v0_8_create_requirements_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constants ---------------------------------------------------

# Source/target type sets extended with 'manual_config'. Sorted alphabetically.
_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
)

# relationship_kind CHECK extended with the four new manual_config-source
# kinds. Sorted alphabetically.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'field_belongs_to_entity', 'is_about', "
    "'manual_config_realizes_requirement', "
    "'manual_config_scopes_to_domain', "
    "'manual_config_touches_entity', "
    "'manual_config_touches_field', "
    "'persona_realized_as_entity', 'persona_scopes_to_domain', "
    "'process_hands_off_to_process', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# Originals from 0015 — used by downgrade to restore.
_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'requirement', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference_book', 'requirement', 'risk', "
    "'session', 'status', 'topic', 'work_ticket', 'workstream')"
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
    "'process_hands_off_to_process', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# --- change_log CHECK constants --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', 'persona', "
    "'planning_item', 'process', 'reference', 'reference_book', "
    "'requirement', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)

# --- manual_config category enum (per manual_config.md §3.2.3) -------------

_MANUAL_CONFIG_CATEGORY_VALUES = sorted(
    [
        "saved_view",
        "duplicate_check",
        "workflow",
        "deferred_options_enum",
        "role_permission",
        "dynamic_logic",
        "other",
    ]
)
_MANUAL_CONFIG_CATEGORY_CHECK = (
    "manual_config_category IN ("
    + ", ".join(f"'{v}'" for v in _MANUAL_CONFIG_CATEGORY_VALUES)
    + ")"
)

# --- manual_config status enum (per manual_config.md §3.4.1) ---------------

_MANUAL_CONFIG_STATUS_VALUES = sorted(
    ["candidate", "confirmed", "deferred", "completed"]
)
_MANUAL_CONFIG_STATUS_CHECK = (
    "manual_config_status IN ("
    + ", ".join(f"'{v}'" for v in _MANUAL_CONFIG_STATUS_VALUES)
    + ")"
)


def upgrade() -> None:
    # 1. refs CHECK extensions — single recopy for all three swaps.
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

    # 2. change_log entity_type CHECK extension — admit 'manual_config'.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # 3. Create manual_configs table per manual_config.md §3.2.
    #
    # Twelve columns: identifier + nine substantive (name, category,
    # description, instructions, notes, status, completed_at,
    # completed_by) plus three timestamps (created_at, updated_at,
    # deleted_at). Completion fields are nullable at the storage layer;
    # the §3.5.3 cross-field invariant (both required on transition into
    # ``completed``) is enforced at the access layer — expressing the
    # conditional in SQLite is brittle and the access-layer error body
    # carries richer detail. No FK columns — the four outbound
    # relationships live in the ``refs`` table per §3.3.1.
    op.create_table(
        "manual_configs",
        sa.Column(
            "manual_config_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "manual_config_name", sa.String(length=255), nullable=False
        ),
        sa.Column(
            "manual_config_category", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "manual_config_description", sa.Text(), nullable=False
        ),
        sa.Column(
            "manual_config_instructions", sa.Text(), nullable=False
        ),
        sa.Column("manual_config_notes", sa.Text(), nullable=True),
        sa.Column(
            "manual_config_status", sa.String(length=16), nullable=False
        ),
        sa.Column(
            "manual_config_completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("manual_config_completed_by", sa.Text(), nullable=True),
        sa.Column(
            "manual_config_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "manual_config_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "manual_config_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "manual_config_identifier GLOB 'MCF-[0-9][0-9][0-9]'",
            name="ck_manual_config_identifier_format",
        ),
        sa.CheckConstraint(
            _MANUAL_CONFIG_STATUS_CHECK,
            name="ck_manual_config_status",
        ),
        sa.CheckConstraint(
            _MANUAL_CONFIG_CATEGORY_CHECK,
            name="ck_manual_config_category",
        ),
        sa.PrimaryKeyConstraint("manual_config_identifier"),
    )
    with op.batch_alter_table("manual_configs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_manual_configs_manual_config_status",
            ["manual_config_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_manual_configs_manual_config_category",
            ["manual_config_category"],
            unique=False,
        )
        batch_op.create_index(
            "ix_manual_configs_manual_config_deleted_at",
            ["manual_config_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    """Reverse the upgrade.

    The manual_config rows are dropped along with the table; any rows
    in ``refs`` with ``source_type='manual_config'`` /
    ``target_type='manual_config'`` or with relationship kinds matching
    ``manual_config_*`` will fail the restored v0.5+ CHECK constraints.
    Operators must hand-clear such rows before downgrading.
    """
    # Drop the manual_configs table (with its indexes).
    with op.batch_alter_table("manual_configs", schema=None) as batch_op:
        batch_op.drop_index("ix_manual_configs_manual_config_deleted_at")
        batch_op.drop_index("ix_manual_configs_manual_config_category")
        batch_op.drop_index("ix_manual_configs_manual_config_status")
    op.drop_table("manual_configs")

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
