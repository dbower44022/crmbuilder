"""v0.5+ entity schema growth — entity_kind column + entity_variant_of_entity vocab

Revision ID: 0019_v0_5_entity_kind_and_variants
Revises: 0018_v0_8_process_v2_growth
Create Date: 2026-05-26

PI-010 satisfier. Grows the existing ``entity`` methodology entity per
``methodology-schema-specs/entity.md`` v1.1 (this build's spec
amendment). Additive only: every v0.4 entity field, the three-status
propose-verify lifecycle, the eight endpoints, and the master pane are
preserved verbatim.

Operations, in order:

1. Add one new TEXT NULL column to ``entities`` — ``entity_kind`` (per
   DEC-292). CHECK-constrained to the five-value vocabulary
   ``person`` | ``organization`` | ``event`` | ``transaction`` |
   ``other`` (or NULL — operators may defer classification). No
   default. Existing v0.4 records acquire NULL on migration.
2. Extend ``refs.relationship_kind`` CHECK to admit the new
   ``entity_variant_of_entity`` kind (per DEC-291). This is the first
   entity-to-entity edge kind in v2's reference vocabulary. The
   ``refs.source_type`` / ``refs.target_type`` CHECKs already admit
   ``entity`` from migration 0006, so no source/target CHECK changes
   are needed here. Cardinality (an entity may have at most one
   outbound variant edge) is enforced at the access layer, not the
   schema layer — same posture as ``field_belongs_to_entity`` at PI-004.

Reversibility posture per ``entity.md`` v1.1 §4.5: the ``downgrade()``
fully reverses both operations. Any references rows holding the new
kind are hand-deleted before the CHECK rebuild to avoid the recopy
failing; this is a recovery operation, not a routine reversal, and
row loss is documented behavior.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_v0_5_entity_kind_and_variants"
down_revision: Union[str, None] = "0018_v0_8_process_v2_growth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs.relationship_kind CHECK -----------------------------------------
#
# v0.5+ PI-010 addition per ``entity.md`` v1.1 §3.3.1. Adds one new
# outgoing kind — ``entity_variant_of_entity`` (entity → entity).
# Carries forward every kind admitted by the prior head (the v0.8
# process v2 build, migration 0018). Re-stating the full set here
# matches the 0011 / 0012 / 0017 / 0018 pattern — the migration is a
# complete CHECK replacement, not an additive ALTER.
_NEW_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', "
    "'entity_variant_of_entity', "
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

# Prior CHECK (copied verbatim from migration 0018's
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


_ENTITY_KIND_CHECK = (
    "entity_kind IS NULL OR entity_kind IN "
    "('event', 'organization', 'other', 'person', 'transaction')"
)


def upgrade() -> None:
    # 1. Add the new entity_kind TEXT NULL column to the entities table
    #    per entity.md v1.1 §3.2.3. Five-value enum (person, organization,
    #    event, transaction, other) plus NULL — operators may defer
    #    classification per DEC-292.
    with op.batch_alter_table("entities", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("entity_kind", sa.Text(), nullable=True)
        )
        batch_op.create_check_constraint("ck_entity_kind", _ENTITY_KIND_CHECK)

    # 2. Extend refs.relationship_kind CHECK to admit the new
    #    entity_variant_of_entity kind per entity.md v1.1 §3.3.1.
    #    The source/target type CHECKs already admit `entity` from
    #    migration 0006, so no source/target change is needed here.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _NEW_REF_RELATIONSHIP_CHECK
        )


def downgrade() -> None:
    """Reverse the upgrade.

    Any rows in ``refs`` that hold ``entity_variant_of_entity`` are
    hand-deleted before the CHECK rebuild — the recopy would otherwise
    fail. Per ``entity.md`` v1.1 §4.5 this is a recovery operation,
    not a routine reversal; row loss is documented behavior, not a
    regression. Records authored under v2 with a non-NULL
    ``entity_kind`` lose that value; records authored under v0.4 are
    unaffected.
    """
    # 1. Hand-delete refs rows holding the new kind, then revert the CHECK.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM refs WHERE relationship_kind = "
            "'entity_variant_of_entity'"
        )
    )
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _OLD_REF_RELATIONSHIP_CHECK
        )

    # 2. Drop the entity_kind column and its CHECK constraint.
    with op.batch_alter_table("entities", schema=None) as batch_op:
        batch_op.drop_constraint("ck_entity_kind", type_="check")
        batch_op.drop_column("entity_kind")
