"""Migration 0012 mechanics — commits table + blocks → blocked_by rename.

Two integration tests that run ``alembic upgrade`` via subprocess against
a temp database file, mirroring the existing
``test_catalog_seed_migration.py`` pattern (which is the canonical way the
test suite exercises the live Alembic chain).

Coverage:
- ``test_alembic_upgrade_creates_commits_table_and_check_swap`` — runs the
  full chain to head and verifies the new commits table exists, the
  ``ck_ref_relationship`` CHECK admits ``blocked_by`` and rejects
  ``blocks``, and the ``ck_changelog_entity_type`` CHECK admits ``commit``.
- ``test_data_migration_renames_blocks_to_blocked_by`` — runs the chain
  through 0011 only (the v0.7 head), seeds two ``blocks`` rows that look
  like the methodology-named REF-0357 / REF-0358 pair (planning_item →
  planning_item), then runs the final step to head. Verifies the two
  rows migrate to ``blocked_by`` with their identity preserved.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text


_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_CATALOG_DIR = (
    _REPO_ROOT
    / "PRDs"
    / "product"
    / "crmbuilder-v2"
    / "research"
    / "base-entity-catalog"
)

# The alembic chain runs migration 0004 (catalog seed) which requires the
# catalog YAML directory on disk. Mirrors the skipif on
# ``tests/crmbuilder_v2/bootstrap/test_catalog_seed_migration.py`` — these
# integration tests run only where the catalog data is still present.
pytestmark = pytest.mark.skipif(
    not _CATALOG_DIR.exists(),
    reason="catalog YAMLs decommissioned (per PRD section 5); "
    "alembic-chain tests run only on installations that still have them",
)


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    # The export-write gate (DEC-114) requires the configured root to
    # exist on disk for any session bound after the migration; the
    # migrations themselves don't write the export tree, but the API
    # imports the access layer transitively.
    env["CRMBUILDER_V2_EXPORT_DIR"] = str(db_path.parent / "db-export")
    (db_path.parent / "db-export").mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def test_alembic_upgrade_creates_commits_table_and_check_swap(tmp_path: Path):
    db = tmp_path / "v2.db"
    result = _alembic(["upgrade", "head"], db)
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as c:
        # commits table exists.
        rows = list(
            c.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name='commits'"
                )
            )
        )
        assert len(rows) == 1, "commits table missing after upgrade head"

        # Indexes on commits table — the three named in commit.md §3.5 plus
        # the soft-delete index.
        index_names = {
            r[0]
            for r in c.execute(
                text(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='index' AND tbl_name='commits'"
                )
            )
        }
        assert "ix_commits_commit_conversation_id" in index_names
        assert "ix_commits_commit_repository" in index_names
        assert "ix_commits_commit_committed_at" in index_names

        # refs CHECK admits 'blocked_by' but rejects 'blocks'.
        # Insert a blocked_by row directly (need first to have the columns).
        # The refs table layout is (id PK, reference_identifier, source_type,
        # source_id, target_type, target_id, relationship_kind, created_at).
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at) "
                "VALUES "
                "('REF-9001', 'planning_item', 'PI-001', 'planning_item', "
                "'PI-002', 'blocked_by', datetime('now'))"
            )
        )
        c.commit()
        count = c.execute(
            text(
                "SELECT COUNT(*) FROM refs WHERE relationship_kind='blocked_by'"
            )
        ).scalar()
        assert count >= 1

        # Trying to insert a 'blocks' row must violate the final CHECK.
        try:
            c.execute(
                text(
                    "INSERT INTO refs "
                    "(reference_identifier, source_type, source_id, "
                    "target_type, target_id, relationship_kind, created_at) "
                    "VALUES "
                    "('REF-9002', 'planning_item', 'PI-003', "
                    "'planning_item', 'PI-004', 'blocks', datetime('now'))"
                )
            )
            c.commit()
            raised = False
        except Exception:
            raised = True
        assert raised, "Expected 'blocks' insert to violate ck_ref_relationship"

        # change_log CHECK admits 'commit'.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor) "
                "VALUES "
                "(datetime('now'), 'commit', 'CM-0001', 'insert', 'migration')"
            )
        )
        c.commit()
        n = c.execute(
            text(
                "SELECT COUNT(*) FROM change_log "
                "WHERE entity_type='commit'"
            )
        ).scalar()
        assert n == 1


def test_data_migration_renames_blocks_to_blocked_by(tmp_path: Path):
    db = tmp_path / "v2.db"
    # Step 1: upgrade to v0.7 head only.
    result = _alembic(
        ["upgrade", "0011_v0_7_governance_entities"], db
    )
    assert result.returncode == 0, (
        f"alembic upgrade to 0011 failed:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    engine = create_engine(f"sqlite:///{db}")
    # Step 2: seed two blocks rows that look like REF-0357 / REF-0358.
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at) "
                "VALUES "
                "('REF-0357', 'planning_item', 'PI-025', 'planning_item', "
                "'PI-024', 'blocks', datetime('now')), "
                "('REF-0358', 'planning_item', 'PI-026', 'planning_item', "
                "'PI-025', 'blocks', datetime('now'))"
            )
        )

    # Step 3: upgrade to head, running migration 0012.
    result = _alembic(["upgrade", "head"], db)
    assert result.returncode == 0, (
        f"alembic upgrade head failed:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )

    # Step 4: verify the migration moved both rows to 'blocked_by'.
    with engine.connect() as c:
        blocks_remaining = c.execute(
            text("SELECT COUNT(*) FROM refs WHERE relationship_kind='blocks'")
        ).scalar()
        assert blocks_remaining == 0

        moved = {
            (r[0], r[1], r[2])
            for r in c.execute(
                text(
                    "SELECT reference_identifier, source_id, target_id "
                    "FROM refs WHERE relationship_kind='blocked_by' "
                    "ORDER BY reference_identifier"
                )
            )
        }
        assert moved == {
            ("REF-0357", "PI-025", "PI-024"),
            ("REF-0358", "PI-026", "PI-025"),
        }
