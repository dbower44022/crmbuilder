"""PI-112 follow-on — change_log: workstream -> project

Migration 0027 renamed workstream -> Project (WS- -> PRJ-) across the
``projects`` table, the ``refs`` CHECK constraints + edge data, the
``reference_books`` kind CHECK, and ``identifier_reservations`` — but it
never touched ``change_log``. Its ``ck_changelog_entity_type`` CHECK still
enumerates ``'workstream'`` and omits ``'project'``, so every new
``create_project`` emit() (entity_type='project') violates the constraint
and the POST 500s. The ORM model derives the constraint from
``ENTITY_TYPES | {'reference'}`` (already 'project', no 'workstream'), so
fresh ``create_all`` databases are correct; only migration-built databases
carry the stale literal. This migration closes that gap.

Steps:
  1. Rewrite the historical ``change_log`` rows that recorded workstream
     events: ``entity_identifier`` WS-NNN -> PRJ-NNN, then ``entity_type``
     'workstream' -> 'project'. (before/after JSON payloads are left as
     authored — they are a faithful record of the row shape at the time.)
  2. Rebuild ``ck_changelog_entity_type`` to the model-matching set
     (drop 'workstream', add 'project').

Reversible: ``downgrade`` performs the exact inverse (project -> workstream,
PRJ- -> WS-). CHECK literals are hardcoded (self-contained, no vocab import)
and were generated from the renamed vocab at authoring time.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "0030_pi_112_changelog_workstream_to_project"
down_revision: Union[str, None] = "0029_pi_112_planning_item_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- enumerated CHECK literals (generated from vocab at authoring) ----------
# NEW: model's ENTITY_TYPES | {'reference'} — has 'project', no 'workstream'.
_NEW_ENTITY_TYPE = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', 'project', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'test_spec', 'topic', 'work_ticket')"
)
# OLD: pre-0030 live literal — has 'workstream', no 'project'.
_OLD_ENTITY_TYPE = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference', 'reference_book', 'requirement', 'risk', 'session', "
    "'status', 'test_spec', 'topic', 'work_ticket', 'workstream')"
)


def upgrade() -> None:
    # 1. Rewrite historical workstream-typed change_log rows to project.
    op.execute(
        "UPDATE change_log SET entity_identifier = 'PRJ-' || substr(entity_identifier, 4) "
        "WHERE entity_type='workstream' AND entity_identifier GLOB 'WS-[0-9][0-9][0-9]'"
    )
    op.execute(
        "UPDATE change_log SET entity_type='project' WHERE entity_type='workstream'"
    )
    # 2. Rebuild the entity_type CHECK to the model-matching set.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint("ck_changelog_entity_type", _NEW_ENTITY_TYPE)


def downgrade() -> None:
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint("ck_changelog_entity_type", _OLD_ENTITY_TYPE)
    op.execute(
        "UPDATE change_log SET entity_identifier = 'WS-' || substr(entity_identifier, 5) "
        "WHERE entity_type='project' AND entity_identifier GLOB 'PRJ-[0-9][0-9][0-9]'"
    )
    op.execute(
        "UPDATE change_log SET entity_type='workstream' WHERE entity_type='project'"
    )
