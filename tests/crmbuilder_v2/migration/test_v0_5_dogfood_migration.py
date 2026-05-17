"""v0.5 slice A — dogfood-migration tests.

Each test runs in a per-test temp workspace via the ``v0_4_workspace``
fixture below. The fixture seeds a minimal v0.4-shape ``v2.db`` and
points ``CRMBUILDER_V2_DB_PATH`` at it so the migration's
path-derivation helpers (``meta_db_path``, ``engagement_db_path``)
land in the temp directory.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from crmbuilder_v2.access.db import reset_engine_cache
from crmbuilder_v2.access.meta_db import reset_meta_engine_cache
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.dogfood_v0_5 import (
    needs_migration,
    run_dogfood_migration,
)
from crmbuilder_v2.migration.lazy_migration import engagement_db_path


def _seed_v0_4_v2_db(path: Path, *, with_sessions: int = 0, with_decisions: int = 0):
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(
            """
            CREATE TABLE sessions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE decisions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE planning_items (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE change_log (id INTEGER PRIMARY KEY);
            CREATE TABLE charter (id INTEGER PRIMARY KEY);
            CREATE TABLE status (id INTEGER PRIMARY KEY);
            CREATE TABLE risks (id INTEGER PRIMARY KEY);
            CREATE TABLE topics (id INTEGER PRIMARY KEY);
            CREATE TABLE refs (id INTEGER PRIMARY KEY);
            CREATE TABLE domains (domain_identifier TEXT PRIMARY KEY);
            CREATE TABLE entities (entity_identifier TEXT PRIMARY KEY);
            CREATE TABLE processes (process_identifier TEXT PRIMARY KEY);
            CREATE TABLE crm_candidates (crm_candidate_identifier TEXT PRIMARY KEY);
            """
        )
        for i in range(with_sessions):
            conn.execute(
                "INSERT INTO sessions(identifier) VALUES(?)", (f"SES-{i:03d}",)
            )
        for i in range(with_decisions):
            conn.execute(
                "INSERT INTO decisions(identifier) VALUES(?)", (f"DEC-{i:03d}",)
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def v0_4_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A temp workspace mirroring the v0.4 ``crmbuilder-v2/data/`` layout."""
    data = tmp_path / "crmbuilder-v2" / "data"
    data.mkdir(parents=True)
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(data / "v2.db"))
    monkeypatch.setenv(
        "CRMBUILDER_V2_EXPORT_DIR", str(tmp_path / "exports")
    )
    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()
    yield data
    reset_meta_engine_cache()
    reset_engine_cache()
    reset_settings_cache()


def test_needs_migration_true_when_v2_db_present(v0_4_workspace):
    _seed_v0_4_v2_db(v0_4_workspace / "v2.db")
    assert needs_migration() is True


def test_needs_migration_false_for_fresh_install(v0_4_workspace):
    assert needs_migration() is False


def test_needs_migration_false_after_successful_migration(v0_4_workspace):
    _seed_v0_4_v2_db(v0_4_workspace / "v2.db", with_sessions=2)
    result = run_dogfood_migration()
    assert result.success, result.error
    assert needs_migration() is False


def test_full_migration_happy_path(v0_4_workspace):
    _seed_v0_4_v2_db(
        v0_4_workspace / "v2.db", with_sessions=3, with_decisions=5
    )
    result = run_dogfood_migration()

    assert result.success, result.error
    assert "backup" in result.steps_completed
    assert "meta_db_created" in result.steps_completed
    assert "crmbuilder_row_inserted" in result.steps_completed
    assert "v2_db_copied" in result.steps_completed
    assert "row_counts_verified" in result.steps_completed
    assert "v2_db_deleted" in result.steps_completed
    assert "current_engagement_written" in result.steps_completed

    # Backup persists; original deleted; destination present.
    assert not (v0_4_workspace / "v2.db").exists()
    assert (v0_4_workspace / "v2.db.pre-v0.5-backup").exists()
    assert (v0_4_workspace / "engagements.db").exists()
    assert engagement_db_path("CRMBUILDER").exists()

    # Row counts match across both sides.
    assert result.row_count_verifications["sessions"] == (3, 3)
    assert result.row_count_verifications["decisions"] == (5, 5)

    # current_engagement.json holds CRMBUILDER.
    payload = json.loads(
        (v0_4_workspace / "current_engagement.json").read_text()
    )
    assert payload["engagement_identifier"] == "ENG-001"
    assert payload["engagement_code"] == "CRMBUILDER"
    assert "set_at" in payload


def test_rerun_is_idempotent(v0_4_workspace):
    _seed_v0_4_v2_db(v0_4_workspace / "v2.db", with_sessions=2)

    first = run_dogfood_migration()
    assert first.success
    assert "current_engagement_written" in first.steps_completed

    # Second run detects already-migrated state.
    second = run_dogfood_migration()
    assert second.success
    assert second.steps_completed == ["already_migrated"]


def test_meta_db_contains_crmbuilder_row(v0_4_workspace):
    _seed_v0_4_v2_db(v0_4_workspace / "v2.db", with_sessions=1)
    result = run_dogfood_migration()
    assert result.success, result.error

    # Query the meta DB directly.
    meta_path = v0_4_workspace / "engagements.db"
    conn = sqlite3.connect(str(meta_path))
    try:
        rows = conn.execute(
            "SELECT engagement_identifier, engagement_code, "
            "engagement_name, engagement_status "
            "FROM engagements"
        ).fetchall()
    finally:
        conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "ENG-001"
    assert rows[0][1] == "CRMBUILDER"
    assert rows[0][2] == "CRMBuilder v2"
    assert rows[0][3] == "active"


def test_failure_recovery_preserves_backup(v0_4_workspace, monkeypatch):
    """A failure mid-migration leaves the backup intact."""
    _seed_v0_4_v2_db(v0_4_workspace / "v2.db", with_sessions=1)

    # Monkeypatch the row-count helper to force a mismatch.
    from crmbuilder_v2.migration import dogfood_v0_5

    real_verify = dogfood_v0_5._verify_row_counts

    def fake_verify(source, dest):
        result = real_verify(source, dest)
        # Inject a mismatch
        if "sessions" in result:
            src, _ = result["sessions"]
            result["sessions"] = (src, src + 999)
        return result

    monkeypatch.setattr(
        dogfood_v0_5, "_verify_row_counts", fake_verify
    )

    result = run_dogfood_migration()
    assert result.success is False
    assert result.error is not None
    # Backup MUST be preserved.
    assert (v0_4_workspace / "v2.db.pre-v0.5-backup").exists()
    # Legacy v2.db was NOT deleted because the verify step failed
    # before the delete step.
    assert (v0_4_workspace / "v2.db").exists()
