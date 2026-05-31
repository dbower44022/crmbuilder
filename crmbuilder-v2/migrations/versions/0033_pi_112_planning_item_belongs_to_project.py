"""PI-112 follow-on — planning_item_belongs_to_project containment kind

Revision ID: 0033_pi_112_planning_item_belongs_to_project
Revises: 0032_pi_112_work_task_entity
Create Date: 2026-05-31

Completes the target-model §7 containment chain (Project -> Planning Item ->
Workstream -> Work Task). PI-112 implemented the lower two links but missed the
top one: there was no relationship kind to attach a Planning Item to its
Project, so PIs floated unattached and never rolled up under a Project in the
UI. This adds the ``planning_item_belongs_to_project`` kind to the ``refs``
relationship CHECK (superset — no existing row rewritten). The backfill of the
actual edges is done separately via the API, not in this migration.

Reversible: ``downgrade`` deletes any rows using the new kind, then narrows the
CHECK back.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0033_pi_112_planning_item_belongs_to_project"
down_revision: Union[str, None] = "0032_pi_112_work_task_entity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

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
    "'planning_item_belongs_to_project', 'process_hands_off_to_process', "
    "'process_performed_by_persona', 'process_touches_entity', "
    "'process_touches_field', 'project_planned_in_reference_book', "
    "'references', 'requirement_realized_by_process', "
    "'requirement_scopes_to_domain', 'requirement_touches_entity', "
    "'requirement_touches_field', 'requirement_verified_by_test_spec', "
    "'resolves', 'session_belongs_to_project', 'session_follows_from', "
    "'session_opens_against_work_ticket', 'supersedes', "
    "'test_spec_exercises_process', 'test_spec_touches_entity', "
    "'test_spec_touches_field', 'work_task_belongs_to_workstream', "
    "'workstream_belongs_to_planning_item')"
)
_OLD_REL = _NEW_REL.replace("'planning_item_belongs_to_project', ", "")


def upgrade() -> None:
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint("ck_ref_relationship", _NEW_REL)


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM refs WHERE relationship_kind="
            "'planning_item_belongs_to_project'"
        )
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint("ck_ref_relationship", _OLD_REL)
