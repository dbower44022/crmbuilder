"""PI-080 — register conversation_orchestrates_conversation reference kind

Revision ID: 0022_pi_080_conversation_orchestrates_conversation
Revises: 0021_pi_073_session_conversation_redesign
Create Date: 2026-05-27

Extends the ``refs.relationship_kind`` CHECK constraint to admit the new
``conversation_orchestrates_conversation`` kind that connects an
orchestrator conversation to each of its child agents' conversations.
Without this kind the governance timeline can't express the parent–child
structure of a parallel run.

Per CLAUDE.md, adding a relationship kind requires updating three places
in lockstep: ``REFERENCE_RELATIONSHIPS`` (vocab.py), the
``_kinds_for_pair`` source/target constraint mapping (vocab.py), and the
``refs.relationship_kind`` CHECK constraint (this migration). The vocab
updates accompany this migration in the same commit.

The CHECK is replaced via the standard ``batch_alter_table`` recopy
pattern — drop the old named constraint, create the new one with the
extended kind list. The post-PI-074 ``_build_migration_engine()`` in
``migrations/env.py`` runs migrations with ``foreign_keys=OFF`` so the
table copy doesn't fault on FK references; no env.py changes required.

Forward and backward reversible. The downgrade restores the prior
38-plus-6-kind list (omitting the new kind). If any refs rows have been
authored against the new kind between upgrade and downgrade, the recopy
will fail; operator must hand-clean before downgrading.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0022_pi_080_conversation_orchestrates_conversation"
down_revision: str | None = "0021_pi_073_session_conversation_redesign"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Pre-PI-080 admitted set (44 kinds: 38 from the 0019 schema + 6 PI-073).
# Identical to ``_NEW_REF_RELATIONSHIP_CHECK`` in migration 0021.
_OLD_REF_RELATIONSHIP_CHECK = (
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

# Post-PI-080 admitted set — same 44 kinds plus
# ``conversation_orchestrates_conversation``. Sorted alphabetically.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_session', "
    "'conversation_belongs_to_workstream', "
    "'conversation_follows_from', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_orchestrates_conversation', "
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
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )


def downgrade() -> None:
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )
