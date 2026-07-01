"""REL-040 / PI-094 (REQ-412) — the ``participant`` methodology entity.

Adds the ``participants`` table (the real engagement person/role a
Persona is backed by) and admits the new entity type + reference kind in
the shared CHECKs:

- ``participant`` joins ``ENTITY_TYPES``, so the ``refs`` source/target
  CHECKs and the ``change_log`` entity-type CHECK (which unions
  ``ENTITY_TYPES``) both widen to admit it.
- ``persona_backed_by_participant`` joins ``REFERENCE_RELATIONSHIPS``, so
  the ``refs`` relationship-kind CHECK widens to admit it.

All rebuilt CHECKs are supersets, so no existing row is invalidated.
Predicates derive from the current vocab so they cannot drift from the
model.

SQLite chain head 0104 -> 0105. Companion PG-chain delta:
``migrations/pg/versions/0062_pi_094_participant_entity.py``.

NOTE (live application): the live store is create_all-managed and is NOT
walked through this SQLite chain. This migration is the canonical record
of the delta; the live application is performed via
``crmbuilder-v2-bootstrap-db`` (verified on a copy first) per the
standard runbook.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0105_pi_094_participant_entity"
down_revision: str | None = "0104_pi_374_foreign_link_target"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "participant"
_NEW_KIND = "persona_backed_by_participant"

_ENTITY_TYPES_NEW = ENTITY_TYPES
_ENTITY_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_CHANGELOG_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - {_NEW_KIND}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_participants_table() -> None:
    if "participants" in _tables():
        return
    op.create_table(
        "participants",
        sa.Column("engagement_id", sa.String(length=32), nullable=False),
        sa.Column(
            "participant_identifier", sa.String(length=32), nullable=False
        ),
        sa.Column("participant_name", sa.String(length=255), nullable=False),
        sa.Column(
            "participant_role_kind", sa.String(length=255), nullable=False
        ),
        sa.Column(
            "participant_affiliation", sa.String(length=255), nullable=True
        ),
        sa.Column("participant_contact", sa.String(length=255), nullable=True),
        sa.Column("participant_notes", sa.Text(), nullable=True),
        sa.Column(
            "participant_status",
            sa.String(length=16),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "participant_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "participant_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "participant_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["engagement_id"], ["engagements.engagement_identifier"]
        ),
        sa.PrimaryKeyConstraint("engagement_id", "participant_identifier"),
        sa.CheckConstraint(
            "participant_identifier GLOB 'PTC-[0-9][0-9][0-9]'",
            name="ck_participant_identifier_format",
        ),
        sa.CheckConstraint(
            "participant_status IN ('active', 'inactive')",
            name="ck_participant_status",
        ),
    )
    op.create_index(
        "ix_participants_participant_status",
        "participants",
        ["participant_status"],
    )
    op.create_index(
        "ix_participants_participant_deleted_at",
        "participants",
        ["participant_deleted_at"],
    )


def _drop_participants_table() -> None:
    if "participants" not in _tables():
        return
    op.drop_index(
        "ix_participants_participant_deleted_at", table_name="participants"
    )
    op.drop_index(
        "ix_participants_participant_status", table_name="participants"
    )
    op.drop_table("participants")


def _rebuild_ref_checks(
    entity_types: frozenset[str], kinds: frozenset[str]
) -> None:
    if "refs" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_source_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_source_type", _check_in("source_type", entity_types)
        )
        batch.drop_constraint("ck_ref_target_type", type_="check")
        batch.create_check_constraint(
            "ck_ref_target_type", _check_in("target_type", entity_types)
        )
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def _rebuild_changelog_check(entity_types: frozenset[str]) -> None:
    if "change_log" not in _tables():
        return
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type", _check_in("entity_type", entity_types)
        )


def upgrade() -> None:
    _create_participants_table()
    _rebuild_ref_checks(_ENTITY_TYPES_NEW, _KINDS_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE source_type = 'participant' "
            "OR target_type = 'participant' "
            "OR relationship_kind = 'persona_backed_by_participant'"
        )
    if "change_log" in _tables():
        op.execute(
            "DELETE FROM change_log WHERE entity_type = 'participant'"
        )
    _rebuild_ref_checks(_ENTITY_TYPES_OLD, _KINDS_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    _drop_participants_table()
