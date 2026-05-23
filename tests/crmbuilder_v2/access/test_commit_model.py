"""Schema-level tests for the v0.8 Commit model.

Exercises the model directly via the ``v2_env`` fixture (which uses
``Base.metadata.create_all`` rather than the Alembic chain) so the tests
run regardless of whether the catalog YAMLs are present.

The full Alembic chain (including the data migration moving ``blocks`` to
``blocked_by``) is exercised in
``tests/crmbuilder_v2/migration/test_0012_commits_and_blocked_by.py``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from crmbuilder_v2.access.db import session_scope


def test_commits_table_exists_after_create_all(v2_env):
    """The Commit model materializes a ``commits`` table via create_all."""
    with session_scope() as s:
        names = inspect(s.get_bind()).get_table_names()
    assert "commits" in names


def test_commits_table_has_expected_columns(v2_env):
    """The commits table has the v0.8 fifteen-column inventory."""
    with session_scope() as s:
        cols = {
            c["name"]
            for c in inspect(s.get_bind()).get_columns("commits")
        }
    expected = {
        "commit_identifier",
        "commit_sha",
        "commit_message_first_line",
        "commit_message_full",
        "commit_author_name",
        "commit_author_email",
        "commit_committed_at",
        "commit_repository",
        "commit_branch",
        "commit_parent_shas",
        "commit_files_changed_count",
        "commit_conversation_id",
        "commit_created_at",
        "commit_updated_at",
        "commit_deleted_at",
    }
    assert expected <= cols, f"missing columns: {sorted(expected - cols)}"


def test_commits_unique_constraint_on_sha(v2_env):
    """``commit_sha`` is UNIQUE across rows."""
    with session_scope() as s:
        uqs = inspect(s.get_bind()).get_unique_constraints("commits")
    sha_uqs = [u for u in uqs if u["column_names"] == ["commit_sha"]]
    assert len(sha_uqs) == 1, f"expected unique on commit_sha; got {uqs}"


def test_commits_identifier_format_check_rejects_wrong_width(v2_env):
    """CM identifier must be four digits, not three."""
    with session_scope() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO commits "
                    "(commit_identifier, commit_sha, "
                    "commit_message_first_line, commit_message_full, "
                    "commit_author_name, commit_author_email, "
                    "commit_committed_at, commit_repository, commit_branch, "
                    "commit_parent_shas, commit_files_changed_count, "
                    "commit_conversation_id, commit_created_at, "
                    "commit_updated_at) "
                    "VALUES "
                    "('CM-001', "
                    "'0123456789abcdef0123456789abcdef01234567', "
                    "'test', 'test', 'doug', 'doug@x.com', "
                    "'2026-05-23T20:00:00-04:00', 'crmbuilder', 'main', "
                    "'[]', 1, 'CONV-001', "
                    "datetime('now'), datetime('now'))"
                )
            )


def test_commits_sha_format_check_rejects_wrong_length(v2_env):
    """SHA must be exactly 40 lowercase hex chars."""
    with session_scope() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO commits "
                    "(commit_identifier, commit_sha, "
                    "commit_message_first_line, commit_message_full, "
                    "commit_author_name, commit_author_email, "
                    "commit_committed_at, commit_repository, commit_branch, "
                    "commit_parent_shas, commit_files_changed_count, "
                    "commit_conversation_id, commit_created_at, "
                    "commit_updated_at) "
                    "VALUES "
                    "('CM-0001', 'TOO_SHORT', "
                    "'test', 'test', 'doug', 'doug@x.com', "
                    "'2026-05-23T20:00:00-04:00', 'crmbuilder', 'main', "
                    "'[]', 1, 'CONV-001', "
                    "datetime('now'), datetime('now'))"
                )
            )


def test_commits_sha_format_check_rejects_uppercase(v2_env):
    """SHA must be lowercase hex; uppercase characters are rejected."""
    with session_scope() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO commits "
                    "(commit_identifier, commit_sha, "
                    "commit_message_first_line, commit_message_full, "
                    "commit_author_name, commit_author_email, "
                    "commit_committed_at, commit_repository, commit_branch, "
                    "commit_parent_shas, commit_files_changed_count, "
                    "commit_conversation_id, commit_created_at, "
                    "commit_updated_at) "
                    "VALUES "
                    "('CM-0001', "
                    "'ABCDEF0123456789ABCDEF0123456789ABCDEF01', "
                    "'test', 'test', 'doug', 'doug@x.com', "
                    "'2026-05-23T20:00:00-04:00', 'crmbuilder', 'main', "
                    "'[]', 1, 'CONV-001', "
                    "datetime('now'), datetime('now'))"
                )
            )


def test_commits_files_changed_count_check_rejects_negative(v2_env):
    """File-change count must be non-negative."""
    with session_scope() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO commits "
                    "(commit_identifier, commit_sha, "
                    "commit_message_first_line, commit_message_full, "
                    "commit_author_name, commit_author_email, "
                    "commit_committed_at, commit_repository, commit_branch, "
                    "commit_parent_shas, commit_files_changed_count, "
                    "commit_conversation_id, commit_created_at, "
                    "commit_updated_at) "
                    "VALUES "
                    "('CM-0001', "
                    "'0123456789abcdef0123456789abcdef01234567', "
                    "'test', 'test', 'doug', 'doug@x.com', "
                    "'2026-05-23T20:00:00-04:00', 'crmbuilder', 'main', "
                    "'[]', -1, 'CONV-001', "
                    "datetime('now'), datetime('now'))"
                )
            )


def test_commits_well_formed_insert_round_trips(v2_env):
    """A correctly-shaped commit row inserts and reads back."""
    with session_scope() as s:
        s.execute(
            text(
                "INSERT INTO commits "
                "(commit_identifier, commit_sha, "
                "commit_message_first_line, commit_message_full, "
                "commit_author_name, commit_author_email, "
                "commit_committed_at, commit_repository, commit_branch, "
                "commit_parent_shas, commit_files_changed_count, "
                "commit_conversation_id, commit_created_at, "
                "commit_updated_at) "
                "VALUES "
                "('CM-0001', "
                "'0123456789abcdef0123456789abcdef01234567', "
                "'subject', 'subject\\n\\nbody', 'Doug Bower', "
                "'doug@dougbower.com', '2026-05-23T20:00:00-04:00', "
                "'crmbuilder', 'main', '[]', 3, 'CONV-001', "
                "datetime('now'), datetime('now'))"
            )
        )
    with session_scope() as s:
        row = s.execute(
            text("SELECT commit_sha FROM commits WHERE commit_identifier='CM-0001'")
        ).first()
    assert row is not None
    assert row[0] == "0123456789abcdef0123456789abcdef01234567"


def test_refs_check_admits_blocked_by_via_create_all(v2_env):
    """After model update, the refs CHECK admits ``blocked_by``."""
    with session_scope() as s:
        s.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at) "
                "VALUES "
                "('REF-9001', 'planning_item', 'PI-001', "
                "'planning_item', 'PI-002', 'blocked_by', datetime('now'))"
            )
        )
    with session_scope() as s:
        n = s.execute(
            text("SELECT COUNT(*) FROM refs WHERE relationship_kind='blocked_by'")
        ).scalar()
    assert n == 1


def test_refs_check_rejects_legacy_blocks(v2_env):
    """The legacy ``blocks`` kind must be rejected by the final CHECK."""
    with session_scope() as s:
        with pytest.raises(IntegrityError):
            s.execute(
                text(
                    "INSERT INTO refs "
                    "(reference_identifier, source_type, source_id, "
                    "target_type, target_id, relationship_kind, created_at) "
                    "VALUES "
                    "('REF-9002', 'planning_item', 'PI-003', "
                    "'planning_item', 'PI-004', 'blocks', datetime('now'))"
                )
            )


def test_refs_check_admits_commit_as_source_and_target(v2_env):
    """Adding ``commit`` to ENTITY_TYPES must let it pass the refs CHECK."""
    with session_scope() as s:
        s.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at) "
                "VALUES "
                "('REF-9003', 'commit', 'CM-0001', "
                "'session', 'SES-001', 'is_about', datetime('now'))"
            )
        )
        s.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at) "
                "VALUES "
                "('REF-9004', 'decision', 'DEC-001', "
                "'commit', 'CM-0001', 'references', datetime('now'))"
            )
        )
    with session_scope() as s:
        n_src = s.execute(
            text("SELECT COUNT(*) FROM refs WHERE source_type='commit'")
        ).scalar()
        n_tgt = s.execute(
            text("SELECT COUNT(*) FROM refs WHERE target_type='commit'")
        ).scalar()
    assert n_src == 1
    assert n_tgt == 1
