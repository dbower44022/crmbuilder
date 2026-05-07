"""Bootstrap migration tests — idempotency and round-trip through JSON export."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Stage a copy of the bootstrap fixture markdown into a temp dir."""
    out = tmp_path / "src"
    out.mkdir()
    for name in ("decisions.md", "sessions.md", "charter.md"):
        shutil.copy(FIXTURES / name, out / name)
    # Use the no-changelog status fixture as ``status.md`` for this test.
    shutil.copy(FIXTURES / "status_no_changelog.md", out / "status.md")
    return out


def test_migration_imports_all_entities(v2_env, source_dir: Path):
    from crmbuilder_v2.bootstrap.migrate import migrate

    summary = migrate(source_dir)
    assert summary.decisions == 2
    assert summary.sessions == 1
    assert summary.charter_versions == 2
    assert summary.status_versions == 1
    assert summary.references == 2  # SES-001 → DEC-001, DEC-002


def test_migration_is_idempotent(v2_env, source_dir: Path):
    """Re-running the migration produces the same database state."""
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import (
        decisions,
        references,
        sessions,
    )
    from crmbuilder_v2.bootstrap.migrate import migrate

    migrate(source_dir)
    with session_scope() as s:
        d_count_1 = len(decisions.list_all(s))
        s_count_1 = len(sessions.list_all(s))
        r_count_1 = len(references.list_all(s))

    migrate(source_dir)  # second run
    with session_scope() as s:
        d_count_2 = len(decisions.list_all(s))
        s_count_2 = len(sessions.list_all(s))
        r_count_2 = len(references.list_all(s))

    assert d_count_1 == d_count_2 == 2
    assert s_count_1 == s_count_2 == 1
    assert r_count_1 == r_count_2 == 2


def test_orientation_reads_match_source(v2_env, source_dir: Path):
    """After migration, the DEC-011 Tier 2 reads return the migrated content."""
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import sessions
    from crmbuilder_v2.bootstrap.migrate import migrate

    migrate(source_dir)

    with session_scope() as s:
        recent = sessions.list_all(s, limit=3)
    assert len(recent) == 1
    assert recent[0]["identifier"] == "SES-001"


def test_migration_creates_decided_in_references(v2_env, source_dir: Path):
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.repositories import references
    from crmbuilder_v2.bootstrap.migrate import migrate

    migrate(source_dir)
    with session_scope() as s:
        refs = references.list_from(
            s, source_type="session", source_id="SES-001"
        )
    assert {r["target_id"] for r in refs} == {"DEC-001", "DEC-002"}
    assert all(r["relationship"] == "decided_in" for r in refs)


def test_export_round_trip(v2_env, source_dir: Path, export_dir: Path):
    """JSON export reflects the post-migration database state."""
    from crmbuilder_v2.bootstrap.migrate import migrate

    migrate(source_dir)
    decisions_export = json.loads((export_dir / "decisions.json").read_text())
    assert {row["identifier"] for row in decisions_export} == {"DEC-001", "DEC-002"}

    sessions_export = json.loads((export_dir / "sessions.json").read_text())
    assert {row["identifier"] for row in sessions_export} == {"SES-001"}

    refs_export = json.loads((export_dir / "references.json").read_text())
    assert len(refs_export) == 2
    assert all(r["relationship_kind"] == "decided_in" for r in refs_export)

    charter_export = json.loads((export_dir / "charter.json").read_text())
    assert len(charter_export) == 2
    current = [r for r in charter_export if r["is_current"]]
    assert len(current) == 1


def test_change_log_marked_actor_migration(v2_env, source_dir: Path):
    """All change-log entries from the migration are tagged ``actor=migration``."""
    from sqlalchemy import select

    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import ChangeLog
    from crmbuilder_v2.bootstrap.migrate import migrate

    migrate(source_dir)
    with session_scope(export=False) as s:
        rows = s.scalars(select(ChangeLog)).all()
    assert all(r.actor == "migration" for r in rows)
    assert len(rows) > 0
