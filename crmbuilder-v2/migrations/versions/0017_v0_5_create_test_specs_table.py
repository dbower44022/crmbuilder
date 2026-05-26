"""v0.5+ test_spec — create test_specs table + refs/change_log CHECK extensions

Revision ID: 0017_v0_5_create_test_specs_table
Revises: 0016_v0_8_create_manual_configs_table
Create Date: 2026-05-26

PI-004 cohort closer. Lands the storage foundation for the
``test_spec`` methodology entity type per
``methodology-schema-specs/test_spec.md`` v1.0. **This is the last of
the four PI-004 cohort siblings; PI-004 resolves on this conversation's
close-out payload.**

Operations, in order:

1. Extend ``refs.source_type`` / ``refs.target_type`` CHECKs to admit
   ``'test_spec'``; extend ``refs.relationship_kind`` to admit the
   three new outbound ``test_spec_*`` kinds
   (``test_spec_exercises_process``, ``test_spec_touches_entity``,
   ``test_spec_touches_field``). All three CHECK swaps in a single
   ``batch_alter_table`` recopy. **The inbound
   ``requirement_verified_by_test_spec`` kind is already admitted by
   migration 0015 (requirement build) so no work needed here for it;
   this build only activates the dormant ``(requirement, test_spec)``
   clause in ``_kinds_for_pair``.**
2. Extend ``change_log.entity_type`` CHECK to admit ``'test_spec'``.
3. Create the ``test_specs`` table per test_spec.md §3.2 — fifteen
   columns (identifier + eleven substantive + three timestamps). Two
   enum CHECK constraints (status, last_run_outcome) plus the
   identifier-format CHECK. Status uses restricted transitions per
   §3.4.1 enforced at the access layer; **last_run_outcome uses
   UNRESTRICTED transitions per §3.4.2 — no transition map**. The
   §3.4.4 cross-field invariant (``last_run_at`` populated whenever
   outcome is a run state; cleared when outcome moves back to
   ``not_run``) is enforced at the access layer, not in SQL. Three
   indexes (status, last_run_outcome, deleted_at).

Forward and backward reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_v0_5_create_test_specs_table"
down_revision: Union[str, None] = "0016_v0_8_create_manual_configs_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constants ---------------------------------------------------

# Source/target type sets extended with 'test_spec'. Sorted alphabetically.
_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_ticket', 'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_ticket', 'workstream')"
)

# relationship_kind CHECK extended with the three new test_spec-source
# kinds. Sorted alphabetically. The ``requirement_verified_by_test_spec``
# kind is already in the previous head (admitted by 0015 proactively).
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
    "'supersedes', "
    "'test_spec_exercises_process', "
    "'test_spec_touches_entity', "
    "'test_spec_touches_field', "
    "'workstream_planned_in_reference_book')"
)

# Originals from 0016 — used by downgrade to restore.
_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
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

# --- change_log CHECK constants --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'test_spec', 'topic', 'work_ticket', 'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'topic', 'work_ticket', 'workstream')"
)

# --- test_spec status / outcome enums (per test_spec.md §3.4) --------------

_TEST_SPEC_STATUS_VALUES = sorted(
    ["candidate", "confirmed", "deferred"]
)
_TEST_SPEC_STATUS_CHECK = (
    "test_spec_status IN ("
    + ", ".join(f"'{v}'" for v in _TEST_SPEC_STATUS_VALUES)
    + ")"
)

_TEST_SPEC_RUN_OUTCOME_VALUES = sorted(
    ["failing", "not_run", "passing", "skipped"]
)
_TEST_SPEC_RUN_OUTCOME_CHECK = (
    "test_spec_last_run_outcome IN ("
    + ", ".join(f"'{v}'" for v in _TEST_SPEC_RUN_OUTCOME_VALUES)
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

    # 2. change_log entity_type CHECK extension — admit 'test_spec'.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # 3. Create test_specs table per test_spec.md §3.2.
    #
    # Fifteen columns: identifier + eleven substantive (name, description,
    # setup, steps, expected, notes, status, last_run_outcome,
    # last_run_at, last_run_notes) plus three timestamps (created_at,
    # updated_at, deleted_at). The dual-axis state (status restricted,
    # outcome unrestricted) and the §3.4.4 cross-field invariant on
    # last_run_at are both enforced at the access layer — see
    # repositories/test_spec.py. The CHECK constraints here are belt-
    # and-braces value-membership only (no transition logic in SQL).
    # No FK columns — the three outbound relationships live in the
    # ``refs`` table per §3.3.1.
    op.create_table(
        "test_specs",
        sa.Column(
            "test_spec_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "test_spec_name", sa.String(length=255), nullable=False
        ),
        sa.Column("test_spec_description", sa.Text(), nullable=False),
        sa.Column("test_spec_setup", sa.Text(), nullable=True),
        sa.Column("test_spec_steps", sa.Text(), nullable=False),
        sa.Column("test_spec_expected", sa.Text(), nullable=False),
        sa.Column("test_spec_notes", sa.Text(), nullable=True),
        sa.Column(
            "test_spec_status",
            sa.String(length=16),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column(
            "test_spec_last_run_outcome",
            sa.String(length=16),
            nullable=False,
            server_default="not_run",
        ),
        sa.Column(
            "test_spec_last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("test_spec_last_run_notes", sa.Text(), nullable=True),
        sa.Column(
            "test_spec_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "test_spec_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "test_spec_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
            name="ck_test_spec_identifier_format",
        ),
        sa.CheckConstraint(
            _TEST_SPEC_STATUS_CHECK,
            name="ck_test_spec_status",
        ),
        sa.CheckConstraint(
            _TEST_SPEC_RUN_OUTCOME_CHECK,
            name="ck_test_spec_last_run_outcome",
        ),
        sa.PrimaryKeyConstraint("test_spec_identifier"),
    )
    with op.batch_alter_table("test_specs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_test_specs_test_spec_status",
            ["test_spec_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_test_specs_test_spec_last_run_outcome",
            ["test_spec_last_run_outcome"],
            unique=False,
        )
        batch_op.create_index(
            "ix_test_specs_test_spec_deleted_at",
            ["test_spec_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    """Reverse the upgrade.

    The test_spec rows are dropped along with the table; any rows in
    ``refs`` with ``source_type='test_spec'`` / ``target_type='test_spec'``
    or with relationship kinds matching ``test_spec_*`` will fail the
    restored v0.5+ CHECK constraints. Operators must hand-clear such
    rows before downgrading.
    """
    # Drop the test_specs table (with its indexes).
    with op.batch_alter_table("test_specs", schema=None) as batch_op:
        batch_op.drop_index("ix_test_specs_test_spec_deleted_at")
        batch_op.drop_index("ix_test_specs_test_spec_last_run_outcome")
        batch_op.drop_index("ix_test_specs_test_spec_status")
    op.drop_table("test_specs")

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
