"""v0.8 process v2 schema growth — six TEXT columns + three vocab kinds

Revision ID: 0018_v0_8_process_v2_growth
Revises: 0017_v0_5_create_test_specs_table
Create Date: 2026-05-26

PI-005 satisfier. Grows the existing ``process`` methodology entity per
``methodology-schema-specs/process-v2.md`` v2.0. Additive only: every
v0.4 process field, the four-value ``process_classification`` lifecycle,
the eight endpoints, and the master pane are preserved verbatim. The
v0.4 schema spec (``methodology-schema-specs/process.md`` v1.0) remains
the canonical predecessor; v2 grows it without replacing it.

Operations, in order:

1. Add six new TEXT NULL columns to ``processes`` — ``process_steps``,
   ``process_triggers``, ``process_outcomes``, ``process_edge_cases``,
   ``process_frequency``, ``process_duration_estimate``. Plain TEXT, no
   DEFAULT, no length cap, no CHECK constraints per ``process-v2.md``
   §3.2.2. Existing v0.4 records acquire NULL for all six.
2. Extend ``refs.relationship_kind`` CHECK to admit the three new
   process-source kinds — ``process_performed_by_persona``,
   ``process_touches_field``, ``process_touches_entity`` (per
   ``process-v2.md`` §3.3.2). The ``refs.source_type`` /
   ``refs.target_type`` CHECKs already admit ``process``, ``persona``,
   ``field``, and ``entity`` from prior migrations, so no source/target
   CHECK changes are needed here.

Reversibility posture per ``process-v2.md`` §4.5: the ``downgrade()``
fully reverses both operations. Any references rows holding one of the
three new kinds are hand-deleted before the CHECK rebuild to avoid the
recopy failing; this is a recovery operation, not a routine reversal,
and row loss is documented behavior.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_v0_8_process_v2_growth"
down_revision: Union[str, None] = "0017_v0_5_create_test_specs_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs.relationship_kind CHECK -----------------------------------------
#
# v0.8 process v2 additions per ``process-v2.md`` §3.3.2. Adds three
# new outgoing kinds — ``process_performed_by_persona``,
# ``process_touches_field``, ``process_touches_entity``. Carries
# forward every kind admitted by the prior head (the v0.5+ test_spec
# build, migration 0017). Re-stating the full set here matches the
# 0011 / 0012 / 0017 pattern — the migration is a complete CHECK
# replacement, not an additive ALTER.
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
    "'process_hands_off_to_process', "
    "'process_performed_by_persona', "
    "'process_touches_entity', "
    "'process_touches_field', "
    "'references', "
    "'requirement_realized_by_process', 'requirement_scopes_to_domain', "
    "'requirement_touches_entity', 'requirement_touches_field', "
    "'requirement_verified_by_test_spec', 'resolves', "
    "'supersedes', "
    "'test_spec_exercises_process', "
    "'test_spec_touches_entity', "
    "'test_spec_touches_field', "
    "'workstream_planned_in_reference_book')"
)

# Prior CHECK (copied verbatim from migration 0017's
# ``_NEW_REF_RELATIONSHIP_CHECK``). Used by ``downgrade()``.
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
    "'supersedes', "
    "'test_spec_exercises_process', "
    "'test_spec_touches_entity', "
    "'test_spec_touches_field', "
    "'workstream_planned_in_reference_book')"
)


def upgrade() -> None:
    # 1. Add the six new TEXT NULL columns to the processes table per
    #    process-v2.md §3.2.2. Plain TEXT, no DEFAULT, no CHECK
    #    constraints — Phase 3 content is deliberately unconstrained
    #    at the storage layer.
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("process_steps", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("process_triggers", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("process_outcomes", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("process_edge_cases", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("process_frequency", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "process_duration_estimate", sa.Text(), nullable=True
            )
        )

    # 2. Extend refs.relationship_kind CHECK to admit the three new
    #    process-source kinds per process-v2.md §3.3.2. The source/
    #    target type CHECKs already admit process/persona/field/entity
    #    from prior migrations so no source/target change is needed.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )


def downgrade() -> None:
    """Reverse the upgrade.

    Any rows in ``refs`` that hold one of the three new kinds are
    hand-deleted before the CHECK rebuild — the recopy would otherwise
    fail. Per ``process-v2.md`` §4.5 this is a recovery operation, not
    a routine reversal; row loss is documented behavior, not a
    regression.

    The six new columns on ``processes`` are dropped in reverse-of-add
    order. Records authored under v2 with values in the new columns
    lose those values; records authored under v0.4 are unaffected.
    """
    # 1. Hand-delete refs rows holding any of the three new kinds, then
    #    revert the CHECK extension.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM refs WHERE relationship_kind IN "
            "('process_performed_by_persona', "
            "'process_touches_field', "
            "'process_touches_entity')"
        )
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )

    # 2. Drop the six new columns. Reverse of the add order.
    with op.batch_alter_table("processes", schema=None) as batch_op:
        batch_op.drop_column("process_duration_estimate")
        batch_op.drop_column("process_frequency")
        batch_op.drop_column("process_edge_cases")
        batch_op.drop_column("process_outcomes")
        batch_op.drop_column("process_triggers")
        batch_op.drop_column("process_steps")
