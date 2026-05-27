"""PI-073 Phase A — session and conversation entity redesign (schema only)

Revision ID: 0020_pi_073_session_conversation_redesign
Revises: 0019_v0_5_entity_kind_and_variants
Create Date: 2026-05-27

PI-073 Phase A per ``pi-073-execution-plan.md`` v0.3 and the spec pair
``governance-schema-specs/session-v2.md`` v1.0 + ``conversation-v2.md`` v1.0.
DEC-314 (active, supersedes DEC-013) is the authority.

This migration carries the **schema** half of the redesign only. The
**data** migration is Phase F, which lives in a separate alembic revision
(or a standalone script) authored against this revision's schema. Between
this revision and Phase F, the old data is preserved in renamed
``legacy_conversations`` and ``legacy_sessions`` tables; the new
``sessions`` and ``conversations`` tables are empty.

Operations, in order:

1. Recopy ``refs`` once to extend ``relationship_kind`` CHECK with the six
   new PI-073 kinds. The existing kinds — including the v0.7 kinds that
   will be retired in Phase F (e.g., ``conversation_records_session``) —
   remain admitted; Phase F's data migration retires them.
2. Rename existing ``conversations`` → ``legacy_conversations``. Preserves
   the 66 rows that, in Phase F, will become the new ``sessions`` table's
   content (because the v0.7 conversation entity becomes the new session
   per DEC-314 / session-v2.md §6).
3. Rename existing ``sessions`` → ``legacy_sessions``. Preserves the 95
   rows that, in Phase F, will become the new ``conversations`` table's
   content (per conversation-v2.md §6).
4. Create new ``sessions`` table per session-v2.md §3 (medium-agnostic
   communication container; SES-NNN identifier; medium enum;
   JSON medium_metadata; 5+1-status lifecycle).
5. Create new ``conversations`` table per conversation-v2.md §3 (topical
   sub-unit; CNV-NNN identifier; 6-status lifecycle including not_started
   terminal).
6. Rename ``commits.commit_conversation_id`` → ``commits.commit_session_id``.
   The existing FK soft-references CONV-NNN identifiers (the v0.7
   conversation entity); under the new model those identifiers will
   become session identifiers per Phase F. Rename now so post-Phase-F the
   column name matches its semantic. The index on the column is recreated
   under the new name.

Forward and backward reversible. The downgrade restores the prior shape:
re-renames legacy_* back to their canonical names, drops new sessions and
conversations, reverts the refs CHECK, restores the commit FK column name.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_pi_073_session_conversation_redesign"
down_revision: Union[str, None] = "0019_v0_5_entity_kind_and_variants"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs.relationship_kind CHECK -------------------------------------------

# Pre-PI-073 admitted set (38 kinds from the 0019 schema). Retained verbatim
# in the upgrade; Phase F retires the v0.7-era conversation_* kinds after
# data migration completes.
_OLD_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'entity_variant_of_entity', 'field_belongs_to_entity', 'is_about', "
    "'manual_config_realizes_requirement', "
    "'manual_config_scopes_to_domain', 'manual_config_touches_entity', "
    "'manual_config_touches_field', 'persona_realized_as_entity', "
    "'persona_scopes_to_domain', 'process_hands_off_to_process', "
    "'process_performed_by_persona', 'process_touches_entity', "
    "'process_touches_field', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', 'supersedes', "
    "'test_spec_exercises_process', 'test_spec_touches_entity', "
    "'test_spec_touches_field', 'workstream_planned_in_reference_book')"
)

# Post-PI-073 admitted set — same 38 kinds plus 6 new (session_*, new
# conversation_*). Sorted alphabetically. Phase F retires the v0.7 kinds.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_session', "
    "'conversation_belongs_to_workstream', "
    "'conversation_follows_from', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', "
    "'conversation_relates_to', "
    "'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'entity_variant_of_entity', 'field_belongs_to_entity', 'is_about', "
    "'manual_config_realizes_requirement', "
    "'manual_config_scopes_to_domain', 'manual_config_touches_entity', "
    "'manual_config_touches_field', 'persona_realized_as_entity', "
    "'persona_scopes_to_domain', 'process_hands_off_to_process', "
    "'process_performed_by_persona', 'process_touches_entity', "
    "'process_touches_field', 'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'session_belongs_to_workstream', "
    "'session_follows_from', "
    "'session_opens_against_work_ticket', "
    "'supersedes', "
    "'test_spec_exercises_process', 'test_spec_touches_entity', "
    "'test_spec_touches_field', 'workstream_planned_in_reference_book')"
)


def upgrade() -> None:
    # 1. Extend refs.relationship_kind CHECK to admit the six new PI-073 kinds.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )

    # 2. Drop user-defined indexes on conversations + sessions BEFORE
    #    renaming. SQLite indexes share a global namespace with the new
    #    tables' indexes; dropping frees the names for reuse. PK
    #    auto-indexes (sqlite_autoindex_*) travel with the rename.
    #    Legacy tables don't need these indexes — they're read-only for
    #    Phase F's data migration consumer.
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_conversations_conversation_status")
        batch_op.drop_index("ix_conversations_conversation_deleted_at")

    # The old sessions table had ix_sessions_identifier and
    # ix_sessions_session_date — names don't collide with new sessions
    # indexes (which are session_status, session_medium, session_deleted_at)
    # so they could remain, but dropping for cleanliness.
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_sessions_identifier")
        batch_op.drop_index("ix_sessions_session_date")

    # 3. Rename old conversations → legacy_conversations (preserves 66 rows).
    op.rename_table("conversations", "legacy_conversations")

    # 4. Rename old sessions → legacy_sessions (preserves 95 rows).
    op.rename_table("sessions", "legacy_sessions")

    # 5. Create new sessions table per session-v2.md §3 (medium-agnostic).
    op.create_table(
        "sessions",
        # Identity
        sa.Column("session_identifier", sa.String(length=32), nullable=False),
        sa.Column("session_title", sa.String(length=255), nullable=False),
        # Content
        sa.Column("session_description", sa.Text(), nullable=False),
        sa.Column("session_notes", sa.Text(), nullable=True),
        # Classification
        sa.Column("session_status", sa.String(length=20), nullable=False,
                  server_default="planned"),
        sa.Column("session_medium", sa.String(length=20), nullable=False),
        # Universal communication fields
        sa.Column("session_scheduled_for", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_started_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_ended_at", sa.DateTime(timezone=True),
                  nullable=True),
        # session_participants: JSON array of persona identifiers
        sa.Column("session_participants", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        # Medium-specific metadata JSON column
        sa.Column("session_medium_metadata", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'")),
        # Lifecycle timestamps
        sa.Column("session_created_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("session_updated_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("session_deleted_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_in_flight_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_cancelled_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_not_started_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("session_superseded_at", sa.DateTime(timezone=True),
                  nullable=True),
        # Constraints
        sa.CheckConstraint(
            "session_identifier GLOB 'SES-[0-9][0-9][0-9]'",
            name="ck_session_identifier_format",
        ),
        sa.CheckConstraint(
            "session_status IN ('planned', 'in_flight', 'complete', "
            "'cancelled', 'not_started', 'superseded')",
            name="ck_session_status",
        ),
        sa.CheckConstraint(
            "session_medium IN ('chat', 'email', 'phone', 'zoom', "
            "'in_person', 'slack', 'other')",
            name="ck_session_medium",
        ),
        sa.PrimaryKeyConstraint("session_identifier"),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_sessions_session_status", ["session_status"], unique=False
        )
        batch_op.create_index(
            "ix_sessions_session_medium", ["session_medium"], unique=False
        )
        batch_op.create_index(
            "ix_sessions_session_deleted_at", ["session_deleted_at"],
            unique=False,
        )

    # 6. Create new conversations table per conversation-v2.md §3 (topical
    #    sub-unit). New CNV-NNN identifier prefix per §3.1.
    op.create_table(
        "conversations",
        # Identity
        sa.Column("conversation_identifier", sa.String(length=32),
                  nullable=False),
        sa.Column("conversation_title", sa.String(length=255), nullable=False),
        # Content
        sa.Column("conversation_purpose", sa.Text(), nullable=False),
        sa.Column("conversation_description", sa.Text(), nullable=False),
        sa.Column("conversation_summary", sa.Text(), nullable=True),
        sa.Column("conversation_notes", sa.Text(), nullable=True),
        # Classification
        sa.Column("conversation_status", sa.String(length=20), nullable=False,
                  server_default="planned"),
        # Lifecycle timestamps
        sa.Column("conversation_created_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("conversation_updated_at", sa.DateTime(timezone=True),
                  nullable=False),
        sa.Column("conversation_deleted_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("conversation_in_flight_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("conversation_completed_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("conversation_cancelled_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("conversation_not_started_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("conversation_superseded_at", sa.DateTime(timezone=True),
                  nullable=True),
        # Constraints
        sa.CheckConstraint(
            "conversation_identifier GLOB 'CNV-[0-9][0-9][0-9]'",
            name="ck_conversation_identifier_format",
        ),
        sa.CheckConstraint(
            "conversation_status IN ('planned', 'in_flight', 'complete', "
            "'cancelled', 'not_started', 'superseded')",
            name="ck_conversation_status",
        ),
        sa.PrimaryKeyConstraint("conversation_identifier"),
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_conversation_status",
            ["conversation_status"], unique=False,
        )
        batch_op.create_index(
            "ix_conversations_conversation_deleted_at",
            ["conversation_deleted_at"], unique=False,
        )

    # 7. Rename commit_conversation_id → commit_session_id on commits table.
    #    Two separate batch operations: first drop the old index (so the
    #    batch_alter_table's table-copy-and-recreate doesn't try to reflect
    #    a non-existent column), then alter_column in a second batch, then
    #    create the new index in a third batch.
    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.drop_index("ix_commits_commit_conversation_id")

    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.alter_column(
            "commit_conversation_id",
            new_column_name="commit_session_id",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )

    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.create_index(
            "ix_commits_commit_session_id",
            ["commit_session_id"],
            unique=False,
        )


def downgrade() -> None:
    """Reverse the upgrade.

    Lossy if any rows have been authored under the new schema between
    upgrade and downgrade: the new ``sessions`` and ``conversations``
    tables are dropped, so any records authored against them are lost.
    Phase F's data-migration of records from ``legacy_*`` to the new
    tables is not yet applied at this revision; so on a clean downgrade
    immediately after upgrade, no records have been authored against the
    new tables and the downgrade is lossless.

    The new PI-073 relationship kinds are removed from the CHECK; if any
    refs rows exist with those kinds, the recopy will fail. Operator
    must hand-clean before downgrading.
    """
    # 6. Restore commit_session_id → commit_conversation_id. Same split-batch
    #    pattern as upgrade step 7.
    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.drop_index("ix_commits_commit_session_id")

    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.alter_column(
            "commit_session_id",
            new_column_name="commit_conversation_id",
            existing_type=sa.String(length=32),
            existing_nullable=False,
        )

    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.create_index(
            "ix_commits_commit_conversation_id",
            ["commit_conversation_id"],
            unique=False,
        )

    # 5. Drop new conversations table.
    op.drop_table("conversations")

    # 4. Drop new sessions table.
    op.drop_table("sessions")

    # 4. Rename legacy_sessions back to sessions.
    op.rename_table("legacy_sessions", "sessions")

    # 3. Rename legacy_conversations back to conversations.
    op.rename_table("legacy_conversations", "conversations")

    # 2. Recreate the dropped indexes on conversations + sessions.
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_conversation_status",
            ["conversation_status"], unique=False,
        )
        batch_op.create_index(
            "ix_conversations_conversation_deleted_at",
            ["conversation_deleted_at"], unique=False,
        )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_sessions_identifier",
            ["identifier"], unique=False,
        )
        batch_op.create_index(
            "ix_sessions_session_date",
            ["session_date"], unique=False,
        )

    # 1. Revert refs.relationship_kind CHECK.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )
