"""REL-039 / PI-357 (REQ-416, DEC-891) — knowledge-structure tables.

Adds three system|engagement-scoped tables migrated out of the instruction
files, and admits the new entity types + relationship kinds in the shared
CHECKs:

- ``preferences`` (PRF-) — advisory interaction/UI/workflow style.
- ``lessons`` (LSN-) — operational gotchas/how-tos split from hybrid memories.
- ``reference_pointers`` (RFP-) — external servers/dashboards/docs/credential
  locations (``access_note`` records *where* a secret lives, never the value).

- ``preference`` / ``lesson`` / ``reference_pointer`` join ``ENTITY_TYPES``, so
  the ``refs`` source/target CHECKs and the ``change_log`` entity-type CHECK
  (which unions ``ENTITY_TYPES``) both widen to admit them.
- ``lesson_derived_from`` / ``lesson_supersedes`` / ``lesson_promoted_to_learning``
  join ``REFERENCE_RELATIONSHIPS``, so the ``refs`` relationship-kind CHECK
  widens to admit them.

All rebuilt CHECKs are supersets, so no existing row is invalidated. Predicates
derive from the current vocab so they cannot drift from the model.

SQLite chain head 0106 -> 0107. Companion PG-chain delta:
``migrations/pg/versions/0064_pi_357_knowledge_structures.py``.

NOTE (live application): the live store is Postgres — the PG chain is walked
(``alembic -c migrations/pg/alembic.ini upgrade head``); this SQLite migration
is the canonical record of the delta for local SQLite dev/tests.
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

revision: str = "0107_pi_357_knowledge_structures"
down_revision: str | None = "0106_pi_063_reference_entries"
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


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _create_preferences() -> None:
    if "preferences" in _tables():
        return
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
            "identifier GLOB 'PRF-[0-9][0-9][0-9]'",
            name="ck_preference_identifier_format",
        ),
        sa.CheckConstraint(
            "category IN ('interaction', 'ui', 'workflow')",
            name="ck_preference_category",
        ),
        sa.CheckConstraint(
            "applies_to IN ('all', 'claude_code', 'sandbox', 'ui')",
            name="ck_preference_applies_to",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired')", name="ck_preference_status"
        ),
    )
    op.create_index("ix_preferences_engagement", "preferences", ["engagement_id"])


def _create_lessons() -> None:
    if "lessons" in _tables():
        return
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
            "identifier GLOB 'LSN-[0-9][0-9][0-9]'",
            name="ck_lesson_identifier_format",
        ),
        sa.CheckConstraint(
            "category IN ('deployment', 'engineering', 'operations', 'process')",
            name="ck_lesson_category",
        ),
        sa.CheckConstraint(
            "signal IN ('guidance', 'hazard', 'howto')", name="ck_lesson_signal"
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired', 'superseded')", name="ck_lesson_status"
        ),
    )
    op.create_index("ix_lessons_engagement", "lessons", ["engagement_id"])
    op.create_index("ix_lessons_category", "lessons", ["category"])


def _create_reference_pointers() -> None:
    if "reference_pointers" in _tables():
        return
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
            "identifier GLOB 'RFP-[0-9][0-9][0-9]'",
            name="ck_reference_pointer_identifier_format",
        ),
        sa.CheckConstraint(
            "kind IN ('credential_location', 'dashboard', 'doc', 'repo', "
            "'server', 'service', 'ticket')",
            name="ck_reference_pointer_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'retired')", name="ck_reference_pointer_status"
        ),
    )
    op.create_index(
        "ix_reference_pointers_engagement", "reference_pointers", ["engagement_id"]
    )
    op.create_index(
        "ix_reference_pointers_kind", "reference_pointers", ["kind"]
    )


def _drop_tables() -> None:
    tables = _tables()
    if "reference_pointers" in tables:
        op.drop_index("ix_reference_pointers_kind", table_name="reference_pointers")
        op.drop_index(
            "ix_reference_pointers_engagement", table_name="reference_pointers"
        )
        op.drop_table("reference_pointers")
    if "lessons" in tables:
        op.drop_index("ix_lessons_category", table_name="lessons")
        op.drop_index("ix_lessons_engagement", table_name="lessons")
        op.drop_table("lessons")
    if "preferences" in tables:
        op.drop_index("ix_preferences_engagement", table_name="preferences")
        op.drop_table("preferences")


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
    _create_preferences()
    _create_lessons()
    _create_reference_pointers()
    _rebuild_ref_checks(_ENTITY_TYPES_NEW, _KINDS_NEW)
    _rebuild_changelog_check(_CHANGELOG_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE source_type IN "
            "('preference', 'lesson', 'reference_pointer') "
            "OR target_type IN ('preference', 'lesson', 'reference_pointer') "
            "OR relationship_kind IN ('lesson_derived_from', 'lesson_supersedes', "
            "'lesson_promoted_to_learning')"
        )
    if "change_log" in _tables():
        op.execute(
            "DELETE FROM change_log WHERE entity_type IN "
            "('preference', 'lesson', 'reference_pointer')"
        )
    _rebuild_ref_checks(_ENTITY_TYPES_OLD, _KINDS_OLD)
    _rebuild_changelog_check(_CHANGELOG_OLD)
    _drop_tables()
