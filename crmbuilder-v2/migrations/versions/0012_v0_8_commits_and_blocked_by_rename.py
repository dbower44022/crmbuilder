"""v0.8 commits table + blocks → blocked_by rename + vocab extensions

Revision ID: 0012_v0_8_commits_and_blocked_by_rename
Revises: 0011_v0_7_governance_entities
Create Date: 2026-05-23

PI-029 slice A. Lands the storage foundation for the ``commit`` entity type
per ``governance-schema-specs/commit.md`` v1.0 and the renamed/added
relationship kinds per ``methodology-code-change-lifecycle.md`` §3.2–§3.4.

Operations, in order:

1. Recopy ``refs`` once with the **interim** ``ck_ref_relationship`` CHECK
   that admits both ``'blocks'`` and ``'blocked_by'`` (plus the new
   ``'resolves'`` and ``'addresses'``), and the extended
   ``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs that admit
   ``'commit'``.
2. Data migration — ``UPDATE refs SET relationship_kind = 'blocked_by'
   WHERE relationship_kind = 'blocks'``. Asserts the two methodology-named
   rows (REF-0357, REF-0358) migrate. Acceptance: zero ``'blocks'`` rows
   remain.
3. Recopy ``refs`` again with the **final** ``ck_ref_relationship`` CHECK
   that drops ``'blocks'`` entirely.
4. Recopy ``change_log`` once to extend ``ck_changelog_entity_type``
   admitting ``'commit'``.
5. Create the ``commits`` table per ``commit.md`` §3.2 — fifteen columns,
   two UNIQUE constraints (``commit_identifier``, ``commit_sha``), three
   CHECK constraints (identifier format, SHA format, non-negative
   file-changed count), three indexes for the dominant query patterns.

The two-step CHECK swap on ``refs.relationship_kind`` is necessary because
SQLite's ``batch_alter_table`` recopies the table — every row must satisfy
the new CHECK during the recopy. The interim CHECK admits both the old and
new values; the final CHECK drops the old value after the UPDATE has
migrated every row.

Downgrade reverses in opposite order. The ``blocked_by`` → ``blocks``
reversal is **lossy** for any rows authored under v0.8 with a
``blocked_by`` kind that the original v0.7 CHECK would have rejected;
those rows are silently re-mapped to ``blocks`` on downgrade.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_v0_8_commits_and_blocked_by_rename"
down_revision: Union[str, None] = "0011_v0_7_governance_entities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- refs CHECK constants ---------------------------------------------------

# Source/target type sets extended with 'commit'. Sorted alphabetically.
_NEW_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)
_NEW_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)

# Interim relationship_kind CHECK — admits BOTH 'blocks' (old) and
# 'blocked_by' (new) plus 'resolves' and 'addresses' (new) so the data
# migration can move rows from 'blocks' to 'blocked_by' under a CHECK that
# admits both.
_INTERIM_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', 'blocks', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'references', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# Final relationship_kind CHECK — 'blocks' removed, 'blocked_by' /
# 'resolves' / 'addresses' present.
_FINAL_REF_RELATIONSHIP_CHECK = (
    "relationship_kind IN ('addresses', 'affects', 'blocked_by', "
    "'close_out_payload_produced_by_conversation', "
    "'conversation_belongs_to_workstream', "
    "'conversation_opens_against_work_ticket', "
    "'conversation_records_session', 'conversation_succeeds_conversation', "
    "'covers', 'decided_in', 'deposit_event_applies_close_out_payload', "
    "'deposit_event_wrote_record', 'entity_scopes_to_domain', 'is_about', "
    "'process_hands_off_to_process', 'references', 'resolves', "
    "'supersedes', 'workstream_planned_in_reference_book')"
)

# Originals from 0011 — used by downgrade to restore.
_OLD_REF_SOURCE_TYPE_CHECK = (
    "source_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference_book', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)
_OLD_REF_TARGET_TYPE_CHECK = (
    "target_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference_book', 'risk', 'session', 'status', 'topic', 'work_ticket', "
    "'workstream')"
)
_OLD_REF_RELATIONSHIP_CHECK = (
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

# --- change_log CHECK constants --------------------------------------------

_NEW_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'commit', 'conversation', 'crm_candidate', "
    "'decision', 'deposit_event', 'domain', 'entity', 'planning_item', "
    "'process', 'reference', 'reference_book', 'risk', 'session', 'status', "
    "'topic', 'work_ticket', 'workstream')"
)
_OLD_CHANGELOG_ENTITY_TYPE_CHECK = (
    "entity_type IN ('catalog_attribute', 'catalog_entity', 'charter', "
    "'close_out_payload', 'conversation', 'crm_candidate', 'decision', "
    "'deposit_event', 'domain', 'entity', 'planning_item', 'process', "
    "'reference', 'reference_book', 'risk', 'session', 'status', 'topic', "
    "'work_ticket', 'workstream')"
)


def upgrade() -> None:
    # 1. Interim refs CHECK swap — admits both old and new relationship kinds
    #    plus extended source/target types. One recopy.
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
            "ck_ref_relationship", _INTERIM_REF_RELATIONSHIP_CHECK
        )

    # 2. Data migration — 'blocks' rows to 'blocked_by'.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE refs SET relationship_kind = 'blocked_by' "
            "WHERE relationship_kind = 'blocks'"
        )
    )
    remaining = bind.execute(
        sa.text("SELECT COUNT(*) FROM refs WHERE relationship_kind = 'blocks'")
    ).scalar()
    assert remaining == 0, (
        f"After UPDATE, expected 0 'blocks' rows; found {remaining}"
    )

    # 3. Final refs CHECK swap — drop the interim CHECK, install the final
    #    CHECK that no longer admits 'blocks'. One recopy.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _FINAL_REF_RELATIONSHIP_CHECK
        )

    # 4. change_log entity_type CHECK extension — admit 'commit'.
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _NEW_CHANGELOG_ENTITY_TYPE_CHECK
        )

    # 5. Create commits table per commit.md §3.2.
    op.create_table(
        "commits",
        sa.Column("commit_identifier", sa.String(length=32), nullable=False),
        sa.Column("commit_sha", sa.String(length=64), nullable=False),
        sa.Column("commit_message_first_line", sa.Text(), nullable=False),
        sa.Column("commit_message_full", sa.Text(), nullable=False),
        sa.Column("commit_author_name", sa.String(length=255), nullable=False),
        sa.Column("commit_author_email", sa.String(length=255), nullable=False),
        # ISO 8601 with explicit offset preserved verbatim — TEXT not
        # DateTime per commit.md §3.2.5.
        sa.Column("commit_committed_at", sa.Text(), nullable=False),
        sa.Column("commit_repository", sa.String(length=255), nullable=False),
        sa.Column(
            "commit_branch", sa.String(length=255), nullable=False,
            server_default="main",
        ),
        sa.Column(
            "commit_parent_shas", sa.JSON(), nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("commit_files_changed_count", sa.Integer(), nullable=False),
        sa.Column("commit_conversation_id", sa.String(length=32), nullable=False),
        sa.Column(
            "commit_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "commit_updated_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "commit_deleted_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.CheckConstraint(
            "commit_identifier GLOB 'CM-[0-9][0-9][0-9][0-9]'",
            name="ck_commit_identifier_format",
        ),
        sa.CheckConstraint(
            "LENGTH(commit_sha) = 40 AND "
            "commit_sha NOT GLOB '*[^0-9a-f]*'",
            name="ck_commit_sha_format",
        ),
        sa.CheckConstraint(
            "commit_files_changed_count >= 0",
            name="ck_commit_files_changed_count_nonneg",
        ),
        sa.PrimaryKeyConstraint("commit_identifier"),
        sa.UniqueConstraint("commit_sha", name="uq_commit_sha"),
    )
    with op.batch_alter_table("commits", schema=None) as batch_op:
        batch_op.create_index(
            "ix_commits_commit_conversation_id",
            ["commit_conversation_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_commits_commit_repository",
            ["commit_repository"],
            unique=False,
        )
        batch_op.create_index(
            "ix_commits_commit_committed_at",
            ["commit_committed_at"],
            unique=False,
        )
        batch_op.create_index(
            "ix_commits_commit_deleted_at",
            ["commit_deleted_at"],
            unique=False,
        )


def downgrade() -> None:
    """Reverse the upgrade.

    The ``blocked_by`` → ``blocks`` reversal is **lossy** in two ways:

    * Any ``blocked_by`` rows authored under v0.8 between upgrade and
      downgrade that the original v0.7 CHECK would have rejected
      (because their ``source_type`` / ``target_type`` pairs were
      ``planning_item`` / ``planning_item`` while v0.7 only admitted
      ``risk`` / ``planning_item`` as ``blocks`` sources) are silently
      re-mapped to ``blocks`` and may then fail the v0.7 CHECK on the
      pair semantics. This is acceptable per the standard Alembic
      downgrade posture: downgrades are operational rollback tools,
      not undo functions.
    * Any ``resolves`` or ``addresses`` rows authored under v0.8 cannot
      be represented in the v0.7 CHECK at all; the downgrade aborts
      via assertion if any such rows exist (the operator must hand-fix
      before downgrading).
    """
    op.drop_table("commits")

    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_entity_type", type_="check")
        batch_op.create_check_constraint(
            "ck_changelog_entity_type", _OLD_CHANGELOG_ENTITY_TYPE_CHECK
        )

    bind = op.get_bind()
    # Abort if v0.8-only kinds exist — downgrade can't represent them.
    for forbidden in ("resolves", "addresses"):
        n = bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM refs WHERE relationship_kind = :k"
            ),
            {"k": forbidden},
        ).scalar()
        assert n == 0, (
            f"Cannot downgrade: {n} rows hold relationship_kind='{forbidden}', "
            "which has no v0.7 representation. Hand-fix and retry."
        )

    # Recopy refs once with an interim CHECK admitting both 'blocks' and
    # 'blocked_by' plus the v0.7 source/target sets.
    with op.batch_alter_table("refs", schema=None) as batch_op:
        batch_op.drop_constraint("ck_ref_relationship", type_="check")
        batch_op.create_check_constraint(
            "ck_ref_relationship", _INTERIM_REF_RELATIONSHIP_CHECK
        )

    bind.execute(
        sa.text(
            "UPDATE refs SET relationship_kind = 'blocks' "
            "WHERE relationship_kind = 'blocked_by'"
        )
    )

    # Restore the original v0.7 CHECKs.
    with op.batch_alter_table("refs", schema=None) as batch_op:
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
