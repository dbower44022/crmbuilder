"""REL-039 / PI-357 (REQ-416, DEC-891, PG chain) — knowledge-structure tables.

Companion to the SQLite-chain ``0107``. Adds ``preferences`` (PRF-),
``lessons`` (LSN-), and ``reference_pointers`` (RFP-), and admits the three new
entity types + three new relationship kinds in the shared CHECKs (``refs``
source/target/relationship_kind + ``change_log`` entity-type). Supersets, so no
existing row is invalidated. Identifier/enum CHECKs use the dialect-aware
``_IdentifierFormatCheck`` / ``_check_in`` helpers (``~``-regex + ``IN`` on
Postgres).

PG chain head 0063 -> 0064. This is the migration walked against the live
Postgres store (``alembic -c migrations/pg/alembic.ini upgrade head``).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _IdentifierFormatCheck
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    LESSON_CATEGORIES,
    LESSON_SIGNALS,
    LESSON_STATUSES,
    PREFERENCE_APPLIES_TO,
    PREFERENCE_CATEGORIES,
    PREFERENCE_STATUSES,
    REFERENCE_POINTER_KINDS,
    REFERENCE_POINTER_STATUSES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0064_pi_357_knowledge_structures"
down_revision: str | None = "0063_pi_063_reference_entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"preference", "lesson", "reference_pointer"})
_NEW_KINDS = frozenset(
    {"lesson_derived_from", "lesson_supersedes", "lesson_promoted_to_learning"}
)

_ENTITY_TYPES_NEW = ENTITY_TYPES
_ENTITY_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_CHANGELOG_NEW = CHANGE_LOG_ENTITY_TYPES
_CHANGELOG_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _create_preferences() -> None:
    op.create_table(
        "preferences",
        sa.Column("identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "applies_to", sa.String(length=32), nullable=False, server_default="all"
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identifier"),
        sa.CheckConstraint(
            _IdentifierFormatCheck("identifier", ["PRF"]),
            name="ck_preference_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("category", PREFERENCE_CATEGORIES),
            name="ck_preference_category",
        ),
        sa.CheckConstraint(
            _check_in("applies_to", PREFERENCE_APPLIES_TO),
            name="ck_preference_applies_to",
        ),
        sa.CheckConstraint(
            _check_in("status", PREFERENCE_STATUSES), name="ck_preference_status"
        ),
    )
    op.create_index("ix_preferences_engagement", "preferences", ["engagement_id"])


def _create_lessons() -> None:
    op.create_table(
        "lessons",
        sa.Column("identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "signal", sa.String(length=16), nullable=False, server_default="guidance"
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identifier"),
        sa.CheckConstraint(
            _IdentifierFormatCheck("identifier", ["LSN"]),
            name="ck_lesson_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("category", LESSON_CATEGORIES), name="ck_lesson_category"
        ),
        sa.CheckConstraint(
            _check_in("signal", LESSON_SIGNALS), name="ck_lesson_signal"
        ),
        sa.CheckConstraint(
            _check_in("status", LESSON_STATUSES), name="ck_lesson_status"
        ),
    )
    op.create_index("ix_lessons_engagement", "lessons", ["engagement_id"])
    op.create_index("ix_lessons_category", "lessons", ["category"])


def _create_reference_pointers() -> None:
    op.create_table(
        "reference_pointers",
        sa.Column("identifier", sa.String(length=32), nullable=False),
        sa.Column("engagement_id", sa.String(length=32), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target", sa.Text(), nullable=False),
        sa.Column("access_note", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=16), nullable=False, server_default="active"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["engagement_id"],
            ["engagements.engagement_identifier"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identifier"),
        sa.CheckConstraint(
            _IdentifierFormatCheck("identifier", ["RFP"]),
            name="ck_reference_pointer_identifier_format",
        ),
        sa.CheckConstraint(
            _check_in("kind", REFERENCE_POINTER_KINDS),
            name="ck_reference_pointer_kind",
        ),
        sa.CheckConstraint(
            _check_in("status", REFERENCE_POINTER_STATUSES),
            name="ck_reference_pointer_status",
        ),
    )
    op.create_index(
        "ix_reference_pointers_engagement", "reference_pointers", ["engagement_id"]
    )
    op.create_index(
        "ix_reference_pointers_kind", "reference_pointers", ["kind"]
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
    _create_preferences()
    _create_lessons()
    _create_reference_pointers()
    _rebuild_ref_checks(_ENTITY_TYPES_NEW, _KINDS_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE source_type IN "
        "('preference', 'lesson', 'reference_pointer') "
        "OR target_type IN ('preference', 'lesson', 'reference_pointer') "
        "OR relationship_kind IN ('lesson_derived_from', 'lesson_supersedes', "
        "'lesson_promoted_to_learning')"
    )
    op.execute(
        "DELETE FROM change_log WHERE entity_type IN "
        "('preference', 'lesson', 'reference_pointer')"
    )
    _rebuild_ref_checks(_ENTITY_TYPES_OLD, _KINDS_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    op.drop_index("ix_reference_pointers_kind", table_name="reference_pointers")
    op.drop_index(
        "ix_reference_pointers_engagement", table_name="reference_pointers"
    )
    op.drop_table("reference_pointers")
    op.drop_index("ix_lessons_category", table_name="lessons")
    op.drop_index("ix_lessons_engagement", table_name="lessons")
    op.drop_table("lessons")
    op.drop_index("ix_preferences_engagement", table_name="preferences")
    op.drop_table("preferences")
