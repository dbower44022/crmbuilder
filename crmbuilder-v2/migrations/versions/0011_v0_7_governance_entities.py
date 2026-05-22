"""v0.7 governance entities — CHECK extensions, REF-NNNN ids, seven tables

Revision ID: 0011_v0_7_governance_entities
Revises: 0010_v0_4_create_crm_candidates_table
Create Date: 2026-05-22

UI v0.7 (governance entity release). Lands the storage foundation for the
six new governance entity types (workstream, conversation, reference_book,
work_ticket, close_out_payload, deposit_event) per
``governance-entity-PRD-v0.1.md`` section 4.2 and the implementation plan
section 3.2.

Operations, in order:

1. Extend ``refs.source_type`` / ``refs.target_type`` CHECK constraints to
   admit the six new entity types; extend ``refs.relationship_kind`` to
   admit the eight new relationship kinds; add the ``reference_identifier``
   column (``REF-NNNN`` format) with a GLOB CHECK and a UNIQUE constraint.
   All in one ``batch_alter_table`` so the ``refs`` table is recopied once.
2. Back-fill ``reference_identifier`` for existing rows by ``id`` ascending
   order (REF-0001, REF-0002, ...). Done in Python against the bound
   connection so the ordering is explicit and dialect-independent.
3. Extend the ``change_log.entity_type`` CHECK constraint to admit the six
   new entity types.
4. Create the seven new tables in dependency order (reference_book_versions
   after its parent reference_books).

The CHECK extensions precede the new tables so reference-table interactions
can be exercised against the extended constraints. Forward and backward
reversible.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_v0_7_governance_entities"
down_revision: Union[str, None] = "0010_v0_4_create_crm_candidates_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constraints -------------------------------------------------

_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference_book', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference_book', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('affects', 'blocks', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'references', 'supersedes', "
    "'workstream_planned_in_reference_book')"
)
_REF_IDENTIFIER_CHECK = (
    "reference_identifier IS NULL OR "
    "reference_identifier GLOB 'REF-[0-9][0-9][0-9][0-9]'"
)

_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'risk', 'session', 'status', 'topic')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'risk', 'session', 'status', 'topic')"
)
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('affects', 'blocks', 'covers', 'decided_in', "
    "'entity_scopes_to_domain', 'is_about', 'process_hands_off_to_process', "
    "'references', 'supersedes')"
)

# --- change_log CHECK constraint --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'crm_candidate', 'decision', 'domain', 'entity', 'planning_item', "
    "'process', 'reference', 'risk', 'session', 'status', 'topic')"
)


def _backfill_reference_identifiers() -> None:
    """Assign REF-NNNN identifiers to existing refs rows by id order."""
    bind = op.get_bind()
    ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM refs ORDER BY id"))]
    for ordinal, ref_id in enumerate(ids, start=1):
        bind.execute(
            sa.text(
                "UPDATE refs SET reference_identifier = :ident WHERE id = :id"
            ),
            {"ident": f"REF-{ordinal:04d}", "id": ref_id},
        )


def upgrade() -> None:
    # 1. refs CHECK extensions + reference_identifier column (one recopy).
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
        batch_op.add_column(
            sa.Column("reference_identifier", sa.String(length=16), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_ref_reference_identifier_format", _REF_IDENTIFIER_CHECK
        )
        batch_op.create_unique_constraint(
            "uq_ref_reference_identifier", ["reference_identifier"]
        )

    # 2. Back-fill existing rows.
    _backfill_reference_identifiers()

    # 3. change_log entity_type CHECK extension.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # 4. New tables, in dependency order.
    op.create_table(
        "workstreams",
        sa.Column("workstream_identifier", sa.String(length=32), nullable=False),
        sa.Column("workstream_name", sa.String(length=255), nullable=False),
        sa.Column("workstream_status", sa.String(length=16), nullable=False),
        sa.Column("workstream_purpose", sa.Text(), nullable=False),
        sa.Column("workstream_description", sa.Text(), nullable=False),
        sa.Column("workstream_notes", sa.Text(), nullable=True),
        sa.Column("workstream_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workstream_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("workstream_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workstream_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "workstream_completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "workstream_cancelled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "workstream_superseded_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "workstream_identifier GLOB 'WS-[0-9][0-9][0-9]'",
            name="ck_workstream_identifier_format",
        ),
        sa.CheckConstraint(
            "workstream_status IN ('cancelled', 'complete', 'in_flight', "
            "'planned', 'superseded')",
            name="ck_workstream_status",
        ),
        sa.PrimaryKeyConstraint("workstream_identifier"),
    )
    with op.batch_alter_table("workstreams", schema=None) as batch_op:
        batch_op.create_index(
            "ix_workstreams_workstream_status", ["workstream_status"], unique=False
        )
        batch_op.create_index(
            "ix_workstreams_workstream_deleted_at",
            ["workstream_deleted_at"],
            unique=False,
        )

    op.create_table(
        "conversations",
        sa.Column("conversation_identifier", sa.String(length=32), nullable=False),
        sa.Column("conversation_title", sa.String(length=255), nullable=False),
        sa.Column("conversation_status", sa.String(length=20), nullable=False),
        sa.Column("conversation_purpose", sa.Text(), nullable=False),
        sa.Column("conversation_description", sa.Text(), nullable=False),
        sa.Column("conversation_notes", sa.Text(), nullable=True),
        sa.Column(
            "conversation_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "conversation_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "conversation_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "conversation_kickoff_drafted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("conversation_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "conversation_started_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "conversation_completed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "conversation_cancelled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "conversation_superseded_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "conversation_identifier GLOB 'CONV-[0-9][0-9][0-9]'",
            name="ck_conversation_identifier_format",
        ),
        sa.CheckConstraint(
            "conversation_status IN ('cancelled', 'complete', 'in_flight', "
            "'kickoff_drafted', 'planned', 'ready', 'superseded')",
            name="ck_conversation_status",
        ),
        sa.PrimaryKeyConstraint("conversation_identifier"),
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_conversation_status",
            ["conversation_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_conversations_conversation_deleted_at",
            ["conversation_deleted_at"],
            unique=False,
        )

    op.create_table(
        "reference_books",
        sa.Column(
            "reference_book_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("reference_book_title", sa.String(length=255), nullable=False),
        sa.Column("reference_book_description", sa.Text(), nullable=False),
        sa.Column("reference_book_notes", sa.Text(), nullable=True),
        sa.Column("reference_book_kind", sa.String(length=32), nullable=False),
        sa.Column("reference_book_status", sa.String(length=16), nullable=False),
        sa.Column("reference_book_file_path", sa.Text(), nullable=False),
        sa.Column(
            "reference_book_current_version_label",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "reference_book_current_version_date",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reference_book_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "reference_book_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "reference_book_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "reference_book_identifier GLOB 'RB-[0-9][0-9][0-9]'",
            name="ck_reference_book_identifier_format",
        ),
        sa.CheckConstraint(
            "reference_book_kind IN ('apply_script', 'architecture_document', "
            "'conduct_framework', 'implementation_plan', 'investigation_report', "
            "'methodology_guide', 'other', 'product_requirements_document', "
            "'schema_specification', 'session_startup_document', "
            "'workstream_master_plan')",
            name="ck_reference_book_kind",
        ),
        sa.CheckConstraint(
            "reference_book_status IN ('active', 'archived', 'superseded')",
            name="ck_reference_book_status",
        ),
        sa.PrimaryKeyConstraint("reference_book_identifier"),
    )
    with op.batch_alter_table("reference_books", schema=None) as batch_op:
        batch_op.create_index(
            "ix_reference_books_reference_book_kind",
            ["reference_book_kind"],
            unique=False,
        )
        batch_op.create_index(
            "ix_reference_books_reference_book_status",
            ["reference_book_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_reference_books_reference_book_deleted_at",
            ["reference_book_deleted_at"],
            unique=False,
        )

    op.create_table(
        "reference_book_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "reference_book_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "reference_book_version_label", sa.String(length=64), nullable=False
        ),
        sa.Column(
            "reference_book_version_date",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("reference_book_version_summary", sa.Text(), nullable=True),
        sa.Column(
            "reference_book_version_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["reference_book_identifier"],
            ["reference_books.reference_book_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "reference_book_identifier",
            "reference_book_version_label",
            name="uq_reference_book_version",
        ),
    )
    with op.batch_alter_table("reference_book_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_reference_book_versions_parent",
            ["reference_book_identifier"],
            unique=False,
        )

    op.create_table(
        "work_tickets",
        sa.Column("work_ticket_identifier", sa.String(length=32), nullable=False),
        sa.Column("work_ticket_title", sa.String(length=255), nullable=False),
        sa.Column("work_ticket_description", sa.Text(), nullable=False),
        sa.Column("work_ticket_notes", sa.Text(), nullable=True),
        sa.Column("work_ticket_kind", sa.String(length=32), nullable=False),
        sa.Column("work_ticket_status", sa.String(length=16), nullable=False),
        sa.Column("work_ticket_file_path", sa.Text(), nullable=False),
        sa.Column(
            "work_ticket_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "work_ticket_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "work_ticket_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("work_ticket_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "work_ticket_consumed_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "work_ticket_cancelled_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "work_ticket_superseded_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "work_ticket_identifier GLOB 'WT-[0-9][0-9][0-9]'",
            name="ck_work_ticket_identifier_format",
        ),
        sa.CheckConstraint(
            "work_ticket_kind IN ('ad_hoc_prompt', 'claude_code_prompt', "
            "'kickoff_prompt', 'other')",
            name="ck_work_ticket_kind",
        ),
        sa.CheckConstraint(
            "work_ticket_status IN ('cancelled', 'consumed', 'drafted', "
            "'ready', 'superseded')",
            name="ck_work_ticket_status",
        ),
        sa.PrimaryKeyConstraint("work_ticket_identifier"),
    )
    with op.batch_alter_table("work_tickets", schema=None) as batch_op:
        batch_op.create_index(
            "ix_work_tickets_work_ticket_kind", ["work_ticket_kind"], unique=False
        )
        batch_op.create_index(
            "ix_work_tickets_work_ticket_status",
            ["work_ticket_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_work_tickets_work_ticket_deleted_at",
            ["work_ticket_deleted_at"],
            unique=False,
        )

    op.create_table(
        "close_out_payloads",
        sa.Column(
            "close_out_payload_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column(
            "close_out_payload_title", sa.String(length=255), nullable=False
        ),
        sa.Column("close_out_payload_description", sa.Text(), nullable=False),
        sa.Column("close_out_payload_notes", sa.Text(), nullable=True),
        sa.Column("close_out_payload_status", sa.String(length=16), nullable=False),
        sa.Column("close_out_payload_file_path", sa.Text(), nullable=False),
        sa.Column(
            "close_out_payload_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "close_out_payload_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "close_out_payload_deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "close_out_payload_ready_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "close_out_payload_applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "close_out_payload_cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "close_out_payload_superseded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "close_out_payload_identifier GLOB 'COP-[0-9][0-9][0-9]'",
            name="ck_close_out_payload_identifier_format",
        ),
        sa.CheckConstraint(
            "close_out_payload_status IN ('applied', 'cancelled', 'drafted', "
            "'ready', 'superseded')",
            name="ck_close_out_payload_status",
        ),
        sa.PrimaryKeyConstraint("close_out_payload_identifier"),
    )
    with op.batch_alter_table("close_out_payloads", schema=None) as batch_op:
        batch_op.create_index(
            "ix_close_out_payloads_close_out_payload_status",
            ["close_out_payload_status"],
            unique=False,
        )
        batch_op.create_index(
            "ix_close_out_payloads_close_out_payload_deleted_at",
            ["close_out_payload_deleted_at"],
            unique=False,
        )

    op.create_table(
        "deposit_events",
        sa.Column(
            "deposit_event_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("deposit_event_title", sa.String(length=255), nullable=False),
        sa.Column("deposit_event_description", sa.Text(), nullable=False),
        sa.Column("deposit_event_outcome", sa.String(length=16), nullable=False),
        sa.Column("deposit_event_records_summary", sa.JSON(), nullable=False),
        sa.Column("deposit_event_error_info", sa.JSON(), nullable=True),
        sa.Column("deposit_event_apply_context", sa.JSON(), nullable=False),
        sa.Column("deposit_event_log_file_path", sa.Text(), nullable=False),
        sa.Column(
            "deposit_event_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.CheckConstraint(
            "deposit_event_identifier GLOB 'DEP-[0-9][0-9][0-9]'",
            name="ck_deposit_event_identifier_format",
        ),
        sa.CheckConstraint(
            "deposit_event_outcome IN ('failure', 'success')",
            name="ck_deposit_event_outcome",
        ),
        sa.PrimaryKeyConstraint("deposit_event_identifier"),
    )
    with op.batch_alter_table("deposit_events", schema=None) as batch_op:
        batch_op.create_index(
            "ix_deposit_events_deposit_event_outcome",
            ["deposit_event_outcome"],
            unique=False,
        )
        batch_op.create_index(
            "ix_deposit_events_deposit_event_created_at",
            ["deposit_event_created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("deposit_events")
    op.drop_table("close_out_payloads")
    op.drop_table("work_tickets")
    op.drop_table("reference_book_versions")
    op.drop_table("reference_books")
    op.drop_table("conversations")
    op.drop_table("workstreams")

    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _OLD_CHANGELOG_ENTITY_TYPE_CHECK
        )

    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("uq_ref_reference_identifier", type_="unique")
        batch_op.drop_constraint(
            "ck_ref_reference_identifier_format", type_="check"
        )
        batch_op.drop_column("reference_identifier")
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
