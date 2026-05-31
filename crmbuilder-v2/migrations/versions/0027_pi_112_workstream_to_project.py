"""PI-112 Phase 1b — rename workstream -> Project, WS- -> PRJ-

Revision ID: 0027_pi_112_workstream_to_project
Revises: 0026_pi_078_identifier_reservations
Create Date: 2026-05-30

Live-data half of PI-112 Phase 1 (DEC-341 / DEC-345). The code rename landed
in Phase 1a (commit a0977a9); this migrates the engagement databases to match.

Operations:
  1. Recreate the ``workstreams`` table as ``projects`` (column prefix
     workstream_* -> project_*, identifier CHECK GLOB 'PRJ-...'), copying every
     row with its ``WS-NNN`` identifier rewritten to ``PRJ-NNN`` in the
     INSERT...SELECT. Recreate-and-copy rather than batch column-rename because
     the identifier CHECK references the renamed column and SQLite carries
     CHECK SQL verbatim across a batch recreate.
  2. ``refs``: drop the three enumerated CHECKs, rewrite the workstream-typed
     edges (source_id/target_id WS->PRJ tied to their type, source_type/
     target_type 'workstream'->'project', and the three relationship kinds
     *_belongs_to_workstream / workstream_planned_in_reference_book ->
     *_project / project_planned_in_reference_book), then recreate the CHECKs
     against the renamed vocabulary.
  3. ``reference_books``: drop the kind CHECK, rewrite the
     ``workstream_master_plan`` reference-book-kind to ``project_master_plan``,
     recreate the CHECK.
  4. ``identifier_reservations``: rewrite any ``entity_type='workstream'`` rows
     to 'project' (none live at authoring, but kept for correctness).

Reversible: ``downgrade`` performs the exact inverse. CHECK literals are
hardcoded (self-contained, no vocab import) and were generated from the
renamed vocab at authoring time.
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_pi_112_workstream_to_project"
down_revision: Union[str, None] = "0026_pi_078_identifier_reservations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- enumerated CHECK literals (generated from vocab at authoring) ----------

_NEW_SOURCE = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', 'project', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_ticket')"
)
_OLD_SOURCE = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'field', "
    "'manual_config', 'persona', 'planning_item', 'process', "
    "'reference_book', 'requirement', 'risk', 'session', 'status', "
    "'test_spec', 'topic', 'work_ticket', 'workstream')"
)
_NEW_TARGET = _NEW_SOURCE.replace("source_type", "target_type")
_OLD_TARGET = _OLD_SOURCE.replace("source_type", "target_type")

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
    "'test_spec_touches_field')"
)
_OLD_REL = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_session', 'conversation_belongs_to_workstream', "
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
    "'process_touches_entity', 'process_touches_field', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'session_belongs_to_workstream', 'session_follows_from', "
    "'session_opens_against_work_ticket', 'supersedes', "
    "'test_spec_exercises_process', 'test_spec_touches_entity', "
    "'test_spec_touches_field', 'workstream_planned_in_reference_book')"
)

_NEW_RBK = (
    "reference_book_kind IN ('apply_script', 'architecture_document', "
    "'conduct_framework', 'implementation_plan', 'investigation_report', "
    "'methodology_guide', 'other', 'product_requirements_document', "
    "'project_master_plan', 'schema_specification', "
    "'session_startup_document')"
)
_OLD_RBK = (
    "reference_book_kind IN ('apply_script', 'architecture_document', "
    "'conduct_framework', 'implementation_plan', 'investigation_report', "
    "'methodology_guide', 'other', 'product_requirements_document', "
    "'schema_specification', 'session_startup_document', "
    "'workstream_master_plan')"
)

_STATUS_CHECK_NEW = (
    "project_status IN ('cancelled', 'complete', 'in_flight', 'planned', "
    "'superseded')"
)
_STATUS_CHECK_OLD = (
    "workstream_status IN ('cancelled', 'complete', 'in_flight', 'planned', "
    "'superseded')"
)

# Column order shared by the create_table / INSERT...SELECT in both directions.
_PROJ_COLS = (
    "project_identifier, project_name, project_status, project_purpose, "
    "project_description, project_notes, project_created_at, "
    "project_updated_at, project_deleted_at, project_started_at, "
    "project_completed_at, project_cancelled_at, project_superseded_at"
)
_WS_COLS = (
    "workstream_identifier, workstream_name, workstream_status, "
    "workstream_purpose, workstream_description, workstream_notes, "
    "workstream_created_at, workstream_updated_at, workstream_deleted_at, "
    "workstream_started_at, workstream_completed_at, workstream_cancelled_at, "
    "workstream_superseded_at"
)


def _create_projects_table(identifier_glob: str, id_col: str, status_check: str,
                           table: str, id_format_name: str,
                           status_name: str) -> None:
    op.create_table(
        table,
        sa.Column(f"{id_col}_identifier", sa.String(32), primary_key=True),
        sa.Column(f"{id_col}_name", sa.String(255), nullable=False),
        sa.Column(f"{id_col}_status", sa.String(16), nullable=False),
        sa.Column(f"{id_col}_purpose", sa.Text(), nullable=False),
        sa.Column(f"{id_col}_description", sa.Text(), nullable=False),
        sa.Column(f"{id_col}_notes", sa.Text(), nullable=True),
        sa.Column(f"{id_col}_created_at", sa.DateTime(), nullable=False),
        sa.Column(f"{id_col}_updated_at", sa.DateTime(), nullable=False),
        sa.Column(f"{id_col}_deleted_at", sa.DateTime(), nullable=True),
        sa.Column(f"{id_col}_started_at", sa.DateTime(), nullable=True),
        sa.Column(f"{id_col}_completed_at", sa.DateTime(), nullable=True),
        sa.Column(f"{id_col}_cancelled_at", sa.DateTime(), nullable=True),
        sa.Column(f"{id_col}_superseded_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            f"{id_col}_identifier GLOB '{identifier_glob}'", name=id_format_name
        ),
        sa.CheckConstraint(status_check, name=status_name),
    )
    op.create_index(
        f"ix_{table}_{id_col}_status", table, [f"{id_col}_status"]
    )
    op.create_index(
        f"ix_{table}_{id_col}_deleted_at", table, [f"{id_col}_deleted_at"]
    )


def upgrade() -> None:
    bind = op.get_bind()

    # 1. workstreams -> projects (recreate + copy with WS->PRJ rewrite).
    _create_projects_table(
        "PRJ-[0-9][0-9][0-9]", "project", _STATUS_CHECK_NEW, "projects",
        "ck_project_identifier_format", "ck_project_status",
    )
    bind.execute(sa.text(
        f"INSERT INTO projects ({_PROJ_COLS}) "
        f"SELECT 'PRJ-' || substr(workstream_identifier, 4), {_WS_COLS[len('workstream_identifier, '):]} "
        f"FROM workstreams"
    ))
    op.drop_table("workstreams")

    # 2. refs: drop CHECKs, rewrite workstream-typed edges, recreate CHECKs.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
    bind.execute(sa.text(
        "UPDATE refs SET source_id='PRJ-'||substr(source_id,4) "
        "WHERE source_type='workstream' AND source_id GLOB 'WS-[0-9][0-9][0-9]'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET target_id='PRJ-'||substr(target_id,4) "
        "WHERE target_type='workstream' AND target_id GLOB 'WS-[0-9][0-9][0-9]'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET source_type='project' WHERE source_type='workstream'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET target_type='project' WHERE target_type='workstream'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='conversation_belongs_to_project' "
        "WHERE relationship_kind='conversation_belongs_to_workstream'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='session_belongs_to_project' "
        "WHERE relationship_kind='session_belongs_to_workstream'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='project_planned_in_reference_book' "
        "WHERE relationship_kind='workstream_planned_in_reference_book'"
    ))
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_ref_source_type", _NEW_SOURCE)
        batch_op.create_check_constraint("ck_ref_target_type", _NEW_TARGET)
        batch_op.create_check_constraint("ck_ref_relationship", _NEW_REL)

    # 3. reference_books: rewrite the kind, rebuild the kind CHECK.
    with op.batch_alter_table("reference_books", schema=None) as batch_op:
        batch_op.drop_constraint("ck_reference_book_kind", type_="check")
    bind.execute(sa.text(
        "UPDATE reference_books SET reference_book_kind='project_master_plan' "
        "WHERE reference_book_kind='workstream_master_plan'"
    ))
    with op.batch_alter_table("reference_books", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_reference_book_kind", _NEW_RBK)

    # 4. identifier_reservations: rewrite entity_type (defensive; 0 live rows).
    bind.execute(sa.text(
        "UPDATE identifier_reservations SET entity_type='project' "
        "WHERE entity_type='workstream'"
    ))


def downgrade() -> None:
    bind = op.get_bind()

    # 4'. identifier_reservations.
    bind.execute(sa.text(
        "UPDATE identifier_reservations SET entity_type='workstream' "
        "WHERE entity_type='project'"
    ))

    # 3'. reference_books.
    with op.batch_alter_table("reference_books", schema=None) as batch_op:
        batch_op.drop_constraint("ck_reference_book_kind", type_="check")
    bind.execute(sa.text(
        "UPDATE reference_books SET reference_book_kind='workstream_master_plan' "
        "WHERE reference_book_kind='project_master_plan'"
    ))
    with op.batch_alter_table("reference_books", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_reference_book_kind", _OLD_RBK)

    # 2'. refs.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_source_type", type_="check")
        batch_op.drop_constraint("ck_ref_target_type", type_="check")
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='conversation_belongs_to_workstream' "
        "WHERE relationship_kind='conversation_belongs_to_project'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='session_belongs_to_workstream' "
        "WHERE relationship_kind='session_belongs_to_project'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET relationship_kind='workstream_planned_in_reference_book' "
        "WHERE relationship_kind='project_planned_in_reference_book'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET source_id='WS-'||substr(source_id,5) "
        "WHERE source_type='project' AND source_id GLOB 'PRJ-[0-9][0-9][0-9]'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET target_id='WS-'||substr(target_id,5) "
        "WHERE target_type='project' AND target_id GLOB 'PRJ-[0-9][0-9][0-9]'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET source_type='workstream' WHERE source_type='project'"
    ))
    bind.execute(sa.text(
        "UPDATE refs SET target_type='workstream' WHERE target_type='project'"
    ))
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.create_check_constraint("ck_ref_source_type", _OLD_SOURCE)
        batch_op.create_check_constraint("ck_ref_target_type", _OLD_TARGET)
        batch_op.create_check_constraint("ck_ref_relationship", _OLD_REL)

    # 1'. projects -> workstreams.
    _create_projects_table(
        "WS-[0-9][0-9][0-9]", "workstream", _STATUS_CHECK_OLD, "workstreams",
        "ck_workstream_identifier_format", "ck_workstream_status",
    )
    bind.execute(sa.text(
        f"INSERT INTO workstreams ({_WS_COLS}) "
        f"SELECT 'WS-' || substr(project_identifier, 5), {_PROJ_COLS[len('project_identifier, '):]} "
        f"FROM projects"
    ))
    op.drop_table("projects")
