"""PI-112 Phase 4a — Workstream (delivery-phase) entity

Revision ID: 0030_pi_112_workstream_phase_entity
Revises: 0029_pi_112_planning_item_lifecycle
Create Date: 2026-05-30

DEC-343 / DEC-349. Introduces the NEW Workstream entity — a single delivery
phase of one Planning Item (WSK- identifier). Creates the ``workstreams`` table
and extends the ``refs`` CHECKs to admit the ``workstream`` entity type (as a
reference source/target) and the ``workstream_belongs_to_planning_item``
relationship kind. The new CHECKs are supersets of the old, so no existing
``refs`` row needs rewriting on upgrade.

Reversible: ``downgrade`` deletes any ``refs`` rows that use the new type/kind
(documented data loss, like prior CHECK-narrowing reversals), restores the old
CHECKs, and drops the ``workstreams`` table.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0031_pi_112_workstream_phase_entity"
down_revision: Union[str, None] = "0030_pi_112_changelog_workstream_to_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_SRC = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', 'project', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_ticket', 'workstream')"
)
_OLD_SRC = _NEW_SRC.replace(", 'workstream')", ")")
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
    "'test_spec_touches_field', 'workstream_belongs_to_planning_item')"
)
_OLD_REL = _NEW_REL.replace(", 'workstream_belongs_to_planning_item')", ")")

_PHASE_CHECK = (
    "workstream_phase_type IN ('Data Migration', 'Deployment', 'Design', "
    "'Development', 'Documentation', 'Testing')"
)
_STATUS_CHECK = (
    "workstream_status IN ('Blocked', 'Complete', 'In Progress', 'Planned')"
)


def upgrade() -> None:
    op.create_table(
        "workstreams",
        sa.Column("workstream_identifier", sa.String(32), primary_key=True),
        sa.Column("workstream_phase_type", sa.String(32), nullable=False),
        sa.Column("workstream_title", sa.String(255), nullable=False),
        sa.Column("workstream_description", sa.Text(), nullable=True),
        sa.Column("workstream_status", sa.String(16), nullable=False),
        sa.Column("workstream_notes", sa.Text(), nullable=True),
        sa.Column("workstream_created_at", sa.DateTime(), nullable=False),
        sa.Column("workstream_updated_at", sa.DateTime(), nullable=False),
        sa.Column("workstream_deleted_at", sa.DateTime(), nullable=True),
        sa.Column("workstream_started_at", sa.DateTime(), nullable=True),
        sa.Column("workstream_completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "workstream_identifier GLOB 'WSK-[0-9][0-9][0-9]'",
            name="ck_workstream_identifier_format",
        ),
        sa.CheckConstraint(_PHASE_CHECK, name="ck_workstream_phase_type"),
        sa.CheckConstraint(_STATUS_CHECK, name="ck_workstream_status"),
    )
    op.create_index(
        "ix_workstreams_workstream_status", "workstreams", ["workstream_status"]
    )
    op.create_index(
        "ix_workstreams_workstream_deleted_at", "workstreams",
        ["workstream_deleted_at"],
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
            "DELETE FROM refs WHERE source_type='workstream' "
            "OR target_type='workstream' "
            "OR relationship_kind='workstream_belongs_to_planning_item'"
        )
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint("ck_ref_source_type", _OLD_SRC)
        batch_op.create_check_constraint("ck_ref_target_type", _OLD_TGT)
        batch_op.create_check_constraint("ck_ref_relationship", _OLD_REL)
    op.drop_index("ix_workstreams_workstream_deleted_at", table_name="workstreams")
    op.drop_index("ix_workstreams_workstream_status", table_name="workstreams")
    op.drop_table("workstreams")
