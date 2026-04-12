"""Tests for client database schema and migrations.

Covers the Instance table (L2 PRD v1.16 §6.5), DeploymentRun table (§6.6),
and the _client_v3 migration that adds them.
"""

import sqlite3
from pathlib import Path

import pytest

from automation.db.migrations import run_client_migrations

# ---------------------------------------------------------------------------
# The v2 client schema is what _client_v1 + _client_v2 would have created.
# For migration-path tests we create a minimal database at version 2 by
# running run_client_migrations on a fresh db and then verifying the new
# tables exist.  For a true v2-only test we build the DB manually.
# ---------------------------------------------------------------------------

_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

# Minimal v2 stand-in — we only need enough to test _client_v3 migration.
# The real v1/v2 schema has 25+ tables; we just need schema_version at v2.
_MINIMAL_V2_TABLES = [
    """
    CREATE TABLE WorkItem (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'not_started',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """,
]


def _col_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Fresh database tests
# ---------------------------------------------------------------------------


class TestFreshClientDatabase:
    """Tests on a freshly-created client database."""

    @pytest.fixture()
    def db(self, tmp_path: Path) -> sqlite3.Connection:
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        yield conn
        conn.close()

    def test_instance_table_exists(self, db: sqlite3.Connection) -> None:
        assert _table_exists(db, "Instance")

    def test_deployment_run_table_exists(self, db: sqlite3.Connection) -> None:
        assert _table_exists(db, "DeploymentRun")

    def test_instance_columns(self, db: sqlite3.Connection) -> None:
        expected = {
            "id", "name", "code", "description", "environment",
            "url", "username", "password", "is_default",
            "created_at", "updated_at",
        }
        assert _col_names(db, "Instance") == expected

    def test_deployment_run_columns(self, db: sqlite3.Connection) -> None:
        expected = {
            "id", "instance_id", "scenario", "crm_platform",
            "started_at", "completed_at", "outcome", "failure_reason",
            "log_path", "created_at", "updated_at",
        }
        assert _col_names(db, "DeploymentRun") == expected

    # --- Instance CHECK constraints ---

    def test_instance_environment_accepts_valid(
        self, db: sqlite3.Connection
    ) -> None:
        for i, env in enumerate(["test", "staging", "production"]):
            db.execute(
                "INSERT INTO Instance (name, code, environment) "
                "VALUES (?, ?, ?)",
                (f"Inst {i}", f"I{i}X", env),
            )
        db.commit()

    def test_instance_environment_rejects_invalid(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Instance (name, code, environment) "
                "VALUES ('Bad', 'BAD', 'dev')"
            )

    def test_instance_code_rejects_lowercase(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Instance (name, code, environment) "
                "VALUES ('Bad', 'bad', 'test')"
            )

    def test_instance_code_rejects_single_char(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Instance (name, code, environment) "
                "VALUES ('Bad', 'A', 'test')"
            )

    # --- DeploymentRun CHECK constraints ---

    def test_deployment_run_scenario_accepts_valid(
        self, db: sqlite3.Connection
    ) -> None:
        # Create an instance to satisfy the FK.
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for scenario in ["self_hosted", "cloud_hosted", "bring_your_own"]:
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at) "
                "VALUES (?, ?, 'EspoCRM', '2025-01-01')",
                (inst_id, scenario),
            )
        db.commit()

    def test_deployment_run_scenario_rejects_invalid(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at) "
                "VALUES (?, 'manual', 'EspoCRM', '2025-01-01')",
                (inst_id,),
            )

    def test_deployment_run_outcome_accepts_valid(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        for outcome in ["success", "failure", "cancelled"]:
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at, outcome) "
                "VALUES (?, 'self_hosted', 'EspoCRM', '2025-01-01', ?)",
                (inst_id, outcome),
            )
        db.commit()

    def test_deployment_run_outcome_accepts_null(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, outcome) "
            "VALUES (?, 'self_hosted', 'EspoCRM', '2025-01-01', NULL)",
            (inst_id,),
        )
        db.commit()

    def test_deployment_run_outcome_rejects_invalid(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at, outcome) "
                "VALUES (?, 'self_hosted', 'EspoCRM', '2025-01-01', 'timeout')",
                (inst_id,),
            )

    def test_deployment_run_crm_platform_rejects_invalid(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment) "
            "VALUES ('Inst', 'INST', 'production')"
        )
        inst_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at) "
                "VALUES (?, 'self_hosted', 'Salesforce', '2025-01-01')",
                (inst_id,),
            )

    # --- FK enforcement ---

    def test_deployment_run_fk_enforced(self, db: sqlite3.Connection) -> None:
        """Insert a DeploymentRun with a bogus instance_id — should fail."""
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO DeploymentRun "
                "(instance_id, scenario, crm_platform, started_at) "
                "VALUES (9999, 'self_hosted', 'EspoCRM', '2025-01-01')"
            )

    # --- is_default uniqueness ---

    def test_is_default_allows_one_true(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO Instance (name, code, environment, is_default) "
            "VALUES ('Prod', 'PROD', 'production', 1)"
        )
        db.commit()

    def test_is_default_rejects_second_true(
        self, db: sqlite3.Connection
    ) -> None:
        """Only one row may have is_default = TRUE."""
        db.execute(
            "INSERT INTO Instance (name, code, environment, is_default) "
            "VALUES ('Prod', 'PROD', 'production', 1)"
        )
        db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Instance (name, code, environment, is_default) "
                "VALUES ('Test', 'TEST', 'test', 1)"
            )

    def test_is_default_allows_multiple_false(
        self, db: sqlite3.Connection
    ) -> None:
        """Multiple rows with is_default = 0 should be fine."""
        db.execute(
            "INSERT INTO Instance (name, code, environment, is_default) "
            "VALUES ('Prod', 'PROD', 'production', 0)"
        )
        db.execute(
            "INSERT INTO Instance (name, code, environment, is_default) "
            "VALUES ('Test', 'TEST', 'test', 0)"
        )
        db.commit()

    def test_schema_version_is_4(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 4


# ---------------------------------------------------------------------------
# Migration path tests (v2 → v3)
# ---------------------------------------------------------------------------


class TestClientV3MigrationWiring:
    """Integration test: pre-v3 client DB gains Instance/DeploymentRun on open."""

    def _create_v2_db(self, path: Path) -> None:
        """Create a minimal database at schema version 2 (no Instance tables)."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        for stmt in _MINIMAL_V2_TABLES:
            conn.execute(stmt)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        conn.commit()
        conn.close()

    def test_existing_client_db_upgraded_on_open(self, tmp_path: Path) -> None:
        """A pre-v3 client database gains Instance/DeploymentRun via run_client_migrations."""
        db_path = tmp_path / "client.db"
        self._create_v2_db(db_path)

        # Verify tables don't exist yet
        conn = sqlite3.connect(str(db_path))
        assert not _table_exists(conn, "Instance")
        assert not _table_exists(conn, "DeploymentRun")
        conn.close()

        # Open through run_client_migrations (same path as active_client_context)
        conn = run_client_migrations(str(db_path))
        assert _table_exists(conn, "Instance")
        assert _table_exists(conn, "DeploymentRun")

        version = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        assert version == 4
        conn.close()


class TestClientV3Migration:
    """Tests for _client_v3 on a pre-existing v2 database."""

    def _create_v2_db(self, path: Path) -> None:
        """Create a minimal database at schema version 2."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        for stmt in _MINIMAL_V2_TABLES:
            conn.execute(stmt)
        # Record versions 1 and 2 as applied.
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        conn.commit()
        conn.close()

    def test_migration_creates_tables(self, tmp_path: Path) -> None:
        db_path = tmp_path / "client.db"
        self._create_v2_db(db_path)
        conn = run_client_migrations(str(db_path))
        assert _table_exists(conn, "Instance")
        assert _table_exists(conn, "DeploymentRun")
        conn.close()

    def test_idempotency(self, tmp_path: Path) -> None:
        """Running _client_v3 twice does not fail."""
        db_path = tmp_path / "client.db"
        self._create_v2_db(db_path)
        conn = run_client_migrations(str(db_path))
        conn.close()
        conn = run_client_migrations(str(db_path))
        assert _table_exists(conn, "Instance")
        assert _table_exists(conn, "DeploymentRun")
        versions = conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3, 4]
        conn.close()
