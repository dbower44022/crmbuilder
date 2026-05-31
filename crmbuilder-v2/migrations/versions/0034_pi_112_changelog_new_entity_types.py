"""PI-112 follow-on — change_log CHECK admits workstream + work_task

Revision ID: 0034_pi_112_changelog_new_entity_types
Revises: 0033_pi_112_planning_item_belongs_to_project
Create Date: 2026-05-31

Phase 4a/4b added the `workstream` and `work_task` entity types to ENTITY_TYPES
and rebuilt the `refs` source/target CHECKs accordingly — but missed the
`change_log` entity-type CHECK (`ck_changelog_entity_type`). On the live DB that
CHECK therefore still excludes the two new entities, so the access layer's
change_log emit (every create/update of a Workstream or Work Task) fails with a
CHECK violation. Tests did not catch it because they build the schema via
`create_all` from the current models. This rebuilds the CHECK from the current
ENTITY_TYPES (∪ 'reference'); a superset, so no existing row is rewritten.

Reversible: ``downgrade`` deletes any change_log rows for the two new entity
types, then narrows the CHECK back.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0034_pi_112_changelog_new_entity_types"
down_revision: Union[str, None] = "0033_pi_112_planning_item_belongs_to_project"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', 'project', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'test_spec', 'topic', 'work_task', 'work_ticket', 'workstream')"
)
_OLD = _NEW.replace("'work_task', ", "").replace(", 'workstream')", ")")


def upgrade() -> None:
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint("ck_changelog_entity_type", _NEW)


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "DELETE FROM change_log WHERE entity_type IN ('workstream', 'work_task')"
        )
    )
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint("ck_changelog_entity_type", _OLD)
