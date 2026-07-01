"""REL-040 / PI-094 (REQ-412, PG chain) — the ``participant`` methodology entity.

Companion to the SQLite-chain ``0105``. Adds the ``participants`` table
and admits the new entity type + reference kind in the shared CHECKs:

- ``participant`` joins ``ENTITY_TYPES`` → the ``refs`` source/target
  CHECKs and the ``change_log`` entity-type CHECK both widen.
- ``persona_backed_by_participant`` joins ``REFERENCE_RELATIONSHIPS`` →
  the ``refs`` relationship-kind CHECK widens.

Supersets, so no existing row is invalidated. Identifier/status CHECKs
use the dialect-aware ``_IdentifierFormatCheck`` / ``_check_in`` helpers
(``~``-regex + ``IN`` on Postgres).

PG chain head 0061 -> 0062.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _IdentifierFormatCheck
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    PARTICIPANT_STATUSES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0062_pi_094_participant_entity"
down_revision: str | None = "0061_pi_374_foreign_link_target"
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


def _create_participants_table() -> None:
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
            _IdentifierFormatCheck("participant_identifier", ["PTC"]),
            name="ck_participant_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("participant_status", PARTICIPANT_STATUSES),
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


def _rebuild_ref_checks(
    entity_types: frozenset[str], kinds: frozenset[str]
) -> None:
    op.drop_constraint("ck_ref_source_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_source_type", "refs", _check_in("source_type", entity_types)
    )
    op.drop_constraint("ck_ref_target_type", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_target_type", "refs", _check_in("target_type", entity_types)
    )
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def _rebuild_changelog_check(entity_types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type",
        "change_log",
        _check_in("entity_type", entity_types),
    )


def upgrade() -> None:
    _create_participants_table()
    _rebuild_ref_checks(_ENTITY_TYPES_NEW, _KINDS_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE source_type = 'participant' "
        "OR target_type = 'participant' "
        "OR relationship_kind = 'persona_backed_by_participant'"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'participant'")
    _rebuild_ref_checks(_ENTITY_TYPES_OLD, _KINDS_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    op.drop_index(
        "ix_participants_participant_deleted_at", table_name="participants"
    )
    op.drop_index(
        "ix_participants_participant_status", table_name="participants"
    )
    op.drop_table("participants")
