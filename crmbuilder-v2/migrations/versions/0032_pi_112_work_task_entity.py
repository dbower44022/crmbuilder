"""PI-112 Phase 4b — Work Task (single-area) entity

Revision ID: 0032_pi_112_work_task_entity
Revises: 0031_pi_112_workstream_phase_entity
Create Date: 2026-05-30

DEC-342. Introduces the Work Task entity — the single-area unit of execution
within a Workstream (WTK- identifier), carrying the ``area`` field (relocated
off the Planning Item in Phase 4c) and a claim. Creates the ``work_tasks``
table and extends the ``refs`` CHECKs to admit the ``work_task`` entity type
and the ``work_task_belongs_to_workstream`` kind. New CHECKs are supersets, so
no existing ``refs`` row is rewritten on upgrade.

Reversible: ``downgrade`` deletes any ``refs`` row using the new type/kind,
restores the old CHECKs, and drops the ``work_tasks`` table.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0032_pi_112_work_task_entity"
down_revision: Union[str, None] = "0031_pi_112_workstream_phase_entity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_SRC = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', 'project', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_task', 'work_ticket', 'workstream')"
)
_OLD_SRC = _NEW_SRC.replace("'work_task', ", "")
_NEW_TGT = _NEW_SRC.replace("source_type", "target_type")
_OLD_TGT = _OLD_SRC.replace("source_type", "target_type")

_NEW_REL = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_project', 'conversation_belongs_to_session', "
    "'conversation_follows_from', 'conversation_opens_against_work_ticket', "
    "'conversation_orchestrates_conversation', 'conversation_records_session', "
    "'conversation_relates_to', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'entity_variant_of_entity', 'field_belongs_to_entity', 'is_about', "
    "'manual_config_realizes_requirement', 'manual_config_scopes_to_domain', "
    "'manual_config_touches_entity', 'manual_config_touches_field', "
    "'persona_realized_as_entity', 'persona_scopes_to_domain', "
    "'process_hands_off_to_process', 'process_performed_by_persona', "
    "'process_touches_entity', 'process_touches_field', "
    "'project_planned_in_reference_book', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'session_belongs_to_project', 'session_follows_from', "
    "'session_opens_against_work_ticket', 'supersedes', "
    "'test_spec_exercises_process', 'test_spec_touches_entity', "
    "'test_spec_touches_field', 'work_task_belongs_to_workstream', "
    "'workstream_belongs_to_planning_item')"
)
_OLD_REL = _NEW_REL.replace("'work_task_belongs_to_workstream', ", "")

_STATUS_CHECK = (
    "work_task_status IN ('Blocked', 'Claimed', 'Complete', 'Failed', "
    "'In Progress', 'Planned', 'Ready')"
)
_CLAIM_CHECK = (
    "(work_task_claimed_by IS NULL AND work_task_claimed_at IS NULL) OR "
    "(work_task_claimed_by IS NOT NULL AND work_task_claimed_at IS NOT NULL)"
)


def upgrade() -> None:
    op.create_table(
        "work_tasks",
        sa.Column("work_task_identifier", sa.String(32), primary_key=True),
        sa.Column("work_task_title", sa.String(255), nullable=False),
        sa.Column("work_task_description", sa.Text(), nullable=True),
        sa.Column("work_task_status", sa.String(16), nullable=False),
        sa.Column("work_task_area", sa.String(64), nullable=False),
        sa.Column("work_task_claimed_by", sa.String(64), nullable=True),
        sa.Column("work_task_claimed_at", sa.DateTime(), nullable=True),
        sa.Column("work_task_notes", sa.Text(), nullable=True),
        sa.Column("work_task_created_at", sa.DateTime(), nullable=False),
        sa.Column("work_task_updated_at", sa.DateTime(), nullable=False),
        sa.Column("work_task_deleted_at", sa.DateTime(), nullable=True),
        sa.Column("work_task_started_at", sa.DateTime(), nullable=True),
        sa.Column("work_task_completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "work_task_identifier GLOB 'WTK-[0-9][0-9][0-9]'",
            name="ck_work_task_identifier_format",
        ),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_work_task_status"),
        sa.CheckConstraint(_CLAIM_CHECK, name="ck_work_task_claim_pairing"),
    )
    op.create_index(
        "ix_work_tasks_work_task_status", "work_tasks", ["work_task_status"]
    )
    op.create_index(
        "ix_work_tasks_work_task_area", "work_tasks", ["work_task_area"]
    )
    op.create_index(
        "ix_work_tasks_work_task_deleted_at", "work_tasks",
        ["work_task_deleted_at"],
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint("ck_ref_source_type", _NEW_SRC)
        batch_op.create_check_constraint("ck_ref_target_type", _NEW_TGT)
        batch_op.create_check_constraint("ck_ref_relationship", _NEW_REL)


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM refs WHERE source_type='work_task' "
            "OR target_type='work_task' "
            "OR relationship_kind='work_task_belongs_to_workstream'"
        )
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint("ck_ref_source_type", _OLD_SRC)
        batch_op.create_check_constraint("ck_ref_target_type", _OLD_TGT)
        batch_op.create_check_constraint("ck_ref_relationship", _OLD_REL)
    op.drop_index("ix_work_tasks_work_task_deleted_at", table_name="work_tasks")
    op.drop_index("ix_work_tasks_work_task_area", table_name="work_tasks")
    op.drop_index("ix_work_tasks_work_task_status", table_name="work_tasks")
    op.drop_table("work_tasks")
