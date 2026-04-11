"""Tests for master database schema and migrations.

Covers the Client table definition from L2 PRD v1.16 §3.1, the
_master_v2 migration that adds project_folder, deployment_model, and
last_opened_at columns, the _master_v3 migration that rebuilds the
Client table to relax the database_path NOT NULL constraint, and the
pre-v3 heal step that repairs NULL project_folder rows via overrides.
"""

import sqlite3
from pathlib import Path

import pytest

from automation.db.migrations import run_master_migrations

# ---------------------------------------------------------------------------
# The v1 CLIENT_TABLE definition (before v1.16 changes) used by migration
# path tests.  Reproduces the schema that _master_v1 would have created.
# ---------------------------------------------------------------------------
_V1_CLIENT_TABLE = """
CREATE TABLE Client (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    description TEXT,
    database_path TEXT NOT NULL,
    organization_overview TEXT,
    crm_platform TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def _col_names(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names for *table*."""
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


class TestFreshMasterDatabase:
    """Tests on a freshly-created master database (no prior schema)."""

    @pytest.fixture()
    def db(self, tmp_path: Path) -> sqlite3.Connection:
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        yield conn
        conn.close()

    def test_client_table_exists(self, db: sqlite3.Connection) -> None:
        assert _table_exists(db, "Client")

    def test_new_columns_present(self, db: sqlite3.Connection) -> None:
        cols = _col_names(db, "Client")
        assert "project_folder" in cols
        assert "deployment_model" in cols
        assert "last_opened_at" in cols

    def test_crm_platform_accepts_espocrm(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO Client (name, code, project_folder, crm_platform) "
            "VALUES ('Test', 'TE', '/tmp/test', 'EspoCRM')"
        )
        db.commit()

    def test_crm_platform_accepts_null(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO Client (name, code, project_folder, crm_platform) "
            "VALUES ('Test', 'TE', '/tmp/test', NULL)"
        )
        db.commit()

    def test_crm_platform_rejects_invalid(self, db: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Client (name, code, project_folder, crm_platform) "
                "VALUES ('Test', 'TE', '/tmp/test', 'Salesforce')"
            )

    def test_deployment_model_accepts_valid_values(
        self, db: sqlite3.Connection
    ) -> None:
        for i, model in enumerate(
            ["self_hosted", "cloud_hosted", "bring_your_own"]
        ):
            db.execute(
                "INSERT INTO Client (name, code, project_folder, deployment_model) "
                "VALUES (?, ?, ?, ?)",
                (f"Client {i}", f"C{i}X", f"/tmp/c{i}", model),
            )
        db.commit()

    def test_deployment_model_accepts_null(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO Client (name, code, project_folder, deployment_model) "
            "VALUES ('Test', 'TE', '/tmp/test', NULL)"
        )
        db.commit()

    def test_deployment_model_rejects_invalid(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Client (name, code, project_folder, deployment_model) "
                "VALUES ('Test', 'TE', '/tmp/test', 'saas')"
            )

    def test_code_check_rejects_lowercase(self, db: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Client (name, code, project_folder) "
                "VALUES ('Test', 'abc', '/tmp/test')"
            )

    def test_code_check_rejects_single_char(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Client (name, code, project_folder) "
                "VALUES ('Test', 'A', '/tmp/test')"
            )

    def test_code_check_accepts_two_chars(self, db: sqlite3.Connection) -> None:
        db.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Test', 'AB', '/tmp/test')"
        )
        db.commit()

    def test_code_check_accepts_ten_chars(
        self, db: sqlite3.Connection
    ) -> None:
        db.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Test', 'ABCDEFGH90', '/tmp/test')"
        )
        db.commit()

    def test_code_check_rejects_eleven_chars(
        self, db: sqlite3.Connection
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO Client (name, code, project_folder) "
                "VALUES ('Test', 'ABCDEFGHIJK', '/tmp/test')"
            )

    def test_schema_version_is_3(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 3


# ---------------------------------------------------------------------------
# Migration path tests (v1 → v2)
# ---------------------------------------------------------------------------


class TestMasterV2Migration:
    """Tests for the _master_v2 migration on a pre-existing v1 database."""

    def _create_v1_db(self, path: Path) -> None:
        """Manually create a v1-era master database."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        conn.execute(_V1_CLIENT_TABLE)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (1)"
        )
        conn.commit()
        conn.close()

    def test_migration_adds_new_columns(self, tmp_path: Path) -> None:
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        conn = run_master_migrations(str(db_path))
        cols = _col_names(conn, "Client")
        assert "project_folder" in cols
        assert "deployment_model" in cols
        assert "last_opened_at" in cols
        conn.close()

    def test_backfill_project_folder(self, tmp_path: Path) -> None:
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        # Insert a row with a realistic database_path before migration.
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Test Client', 'TEST', '/tmp/test_client/.crmbuilder/TEST.db')"
        )
        conn.commit()
        conn.close()

        conn = run_master_migrations(str(db_path))
        row = conn.execute(
            "SELECT project_folder FROM Client WHERE code = 'TEST'"
        ).fetchone()
        assert row[0] == "/tmp/test_client"
        conn.close()

    def test_backfill_edge_case_no_match_aborts_v3(self, tmp_path: Path) -> None:
        """database_path that doesn't match leaves project_folder NULL; v3 aborts."""
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Odd Client', 'ODD', '/some/random/path.db')"
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="NULL project_folder"):
            run_master_migrations(str(db_path))

    def test_idempotency(self, tmp_path: Path) -> None:
        """Running migrations twice does not fail or duplicate columns."""
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        conn = run_master_migrations(str(db_path))
        conn.close()
        # Run again — should be a no-op.
        conn = run_master_migrations(str(db_path))
        cols = _col_names(conn, "Client")
        assert "project_folder" in cols
        # Verify schema_version has exactly versions 1, 2, 3, no duplicates.
        versions = conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3]
        conn.close()

    def test_v3_rebuild_enforces_crm_platform_check(
        self, tmp_path: Path
    ) -> None:
        """v3 table rebuild now enforces the crm_platform CHECK constraint.

        v2 could not add a CHECK to an existing column, but v3 rebuilds
        the table from master_schema.py which includes the constraint.
        Non-conforming data causes the migration to fail.
        """
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path, crm_platform) "
            "VALUES ('Old', 'OLD', '/tmp/old/.crmbuilder/OLD.db', 'WordPress')"
        )
        conn.commit()
        conn.close()
        # v3 rejects the non-conforming crm_platform during table rebuild.
        with pytest.raises(sqlite3.IntegrityError):
            run_master_migrations(str(db_path))


# ---------------------------------------------------------------------------
# Migration path tests (v1 → v2 → v3)
# ---------------------------------------------------------------------------


class TestMasterV3Migration:
    """Tests for the _master_v3 migration (Client table rebuild)."""

    def _create_v1_db_with_row(self, path: Path) -> None:
        """Create a v1-era master database with one Client row."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        conn.execute(_V1_CLIENT_TABLE)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (1)"
        )
        conn.execute(
            "INSERT INTO Client (name, code, database_path, description, "
            "organization_overview, crm_platform) "
            "VALUES ('Acme Corp', 'ACME', "
            "'/tmp/acme/.crmbuilder/ACME.db', 'Test client', "
            "'An overview', 'EspoCRM')"
        )
        conn.commit()
        conn.close()

    def _col_info(
        self, conn: sqlite3.Connection, table: str
    ) -> dict[str, dict]:
        """Return column metadata keyed by name.

        Each value is a dict with keys: cid, name, type, notnull, dflt_value, pk.
        """
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {
            row[1]: {
                "cid": row[0],
                "name": row[1],
                "type": row[2],
                "notnull": row[3],
                "dflt_value": row[4],
                "pk": row[5],
            }
            for row in rows
        }

    def test_happy_path_database_path_nullable(self, tmp_path: Path) -> None:
        """v1-era db → all migrations → database_path is nullable."""
        db_path = tmp_path / "master.db"
        self._create_v1_db_with_row(db_path)

        conn = run_master_migrations(str(db_path))

        # database_path should now be nullable (notnull == 0)
        col_info = self._col_info(conn, "Client")
        assert col_info["database_path"]["notnull"] == 0

        # All original row data preserved
        row = conn.execute(
            "SELECT name, code, database_path, description, "
            "organization_overview, crm_platform, project_folder "
            "FROM Client WHERE code = 'ACME'"
        ).fetchone()
        assert row[0] == "Acme Corp"
        assert row[1] == "ACME"
        assert row[2] == "/tmp/acme/.crmbuilder/ACME.db"
        assert row[3] == "Test client"
        assert row[4] == "An overview"
        assert row[5] == "EspoCRM"
        # project_folder was backfilled by v2
        assert row[6] == "/tmp/acme"

        # INSERT without database_path succeeds
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('New Client', 'NEW', '/tmp/new')"
        )
        conn.commit()
        new_row = conn.execute(
            "SELECT database_path FROM Client WHERE code = 'NEW'"
        ).fetchone()
        assert new_row[0] is None

        conn.close()

    def test_preserves_row_identity(self, tmp_path: Path) -> None:
        """id, created_at, and updated_at are preserved across rebuild."""
        db_path = tmp_path / "master.db"
        self._create_v1_db_with_row(db_path)

        # Record original values before migration
        conn = sqlite3.connect(str(db_path))
        orig = conn.execute(
            "SELECT id, created_at, updated_at FROM Client WHERE code = 'ACME'"
        ).fetchone()
        orig_id, orig_created, orig_updated = orig
        conn.close()

        conn = run_master_migrations(str(db_path))
        row = conn.execute(
            "SELECT id, created_at, updated_at FROM Client WHERE code = 'ACME'"
        ).fetchone()
        assert row[0] == orig_id
        assert row[1] == orig_created
        assert row[2] == orig_updated
        conn.close()

    def test_precheck_aborts_on_null_project_folder(
        self, tmp_path: Path
    ) -> None:
        """v3 aborts with actionable message if project_folder is NULL."""
        db_path = tmp_path / "master.db"
        self._create_v1_db_with_row(db_path)

        # Insert a row with non-matching database_path so v2 leaves
        # project_folder NULL
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Bad Client', 'BAD', '/weird/path.db')"
        )
        conn.commit()
        conn.close()

        with pytest.raises(RuntimeError, match="NULL project_folder") as exc_info:
            run_master_migrations(str(db_path))

        # Error message lists the offending row
        assert "BAD" in str(exc_info.value)

        # Database is unchanged: Client table still present, no Client_new
        conn = sqlite3.connect(str(db_path))
        assert _table_exists(conn, "Client")
        assert not _table_exists(conn, "Client_new")
        # Original rows still intact
        count = conn.execute("SELECT COUNT(*) FROM Client").fetchone()[0]
        assert count == 2
        conn.close()

    def test_idempotency_via_version_tracking(self, tmp_path: Path) -> None:
        """Running migrations twice: v3 runs exactly once."""
        db_path = tmp_path / "master.db"
        self._create_v1_db_with_row(db_path)

        conn = run_master_migrations(str(db_path))
        conn.close()

        # Run again — should be a no-op
        conn = run_master_migrations(str(db_path))
        versions = conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2, 3]

        # Table still works
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Another', 'AN', '/tmp/an')"
        )
        conn.commit()
        conn.close()

    def test_fresh_database_reaches_v3(self, tmp_path: Path) -> None:
        """A fresh database created via run_master_migrations is at v3."""
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))

        version = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        assert version == 3

        # Schema is correct — database_path is nullable
        col_info = self._col_info(conn, "Client")
        assert col_info["database_path"]["notnull"] == 0
        assert col_info["project_folder"]["notnull"] == 1

        # INSERT without database_path works
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('Fresh', 'FR', '/tmp/fresh')"
        )
        conn.commit()
        conn.close()


# ---------------------------------------------------------------------------
# Integration test: end-to-end create_client on migrated v1 database
# ---------------------------------------------------------------------------


class TestCreateClientIntegration:
    """Regression test: create_client succeeds on a migrated v1 database."""

    def test_create_client_on_migrated_v1_database(
        self, tmp_path: Path
    ) -> None:
        """Reproduces the NOT NULL constraint failure and confirms the fix."""
        from automation.core.create_client import (
            CreateClientParams,
            create_client,
        )
        from automation.db.migrations import run_client_migrations

        # Step 1: Create a v1-era master database
        master_path = tmp_path / "master.db"
        conn = sqlite3.connect(str(master_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        conn.execute(_V1_CLIENT_TABLE)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.commit()
        conn.close()

        # Step 2: Run migrations (v2 + v3)
        conn = run_master_migrations(str(master_path))
        conn.close()

        # Step 3: Create a project folder on disk (required by validation)
        project_folder = tmp_path / "test_project"
        project_folder.mkdir()

        # Step 4: Call create_client — this was the failing operation
        result = create_client(
            params=CreateClientParams(
                name="Test Client",
                code="TC",
                description="Integration test",
                project_folder=str(project_folder),
            ),
            master_db_path=str(master_path),
            run_migrations=run_client_migrations,
        )

        assert result.success, f"create_client failed: {result.error}"
        assert result.client is not None
        assert result.client.name == "Test Client"
        assert result.client.code == "TC"
        assert result.client.project_folder == str(project_folder)


# ---------------------------------------------------------------------------
# Heal step tests (pre-v3 NULL project_folder repair via overrides)
# ---------------------------------------------------------------------------


class TestMasterHealStep:
    """Tests for the _heal_null_project_folders step and backup."""

    def _create_v2_db_with_null_folder(
        self, path: Path, code: str = "CBM", db_path_val: str = "/some/path.db"
    ) -> None:
        """Create a v2 master DB with one Client row that has NULL project_folder."""
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(_SCHEMA_VERSION_TABLE)
        conn.execute(_V1_CLIENT_TABLE)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        # Add v2 columns manually (simulating v2 already applied)
        conn.execute("ALTER TABLE Client ADD COLUMN project_folder TEXT")
        conn.execute("ALTER TABLE Client ADD COLUMN deployment_model TEXT")
        conn.execute("ALTER TABLE Client ADD COLUMN last_opened_at TIMESTAMP")
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Test Client', ?, ?)",
            (code, db_path_val),
        )
        conn.commit()
        conn.close()

    def test_override_heals_row_and_v3_succeeds(self, tmp_path: Path) -> None:
        """Override present with matching code → row healed, v3 passes."""
        db_path = tmp_path / "master.db"
        self._create_v2_db_with_null_folder(db_path)

        conn = run_master_migrations(
            str(db_path),
            project_folder_overrides={"CBM": "/home/test/project"},
        )

        # project_folder was set by heal step
        row = conn.execute(
            "SELECT project_folder FROM Client WHERE code = 'CBM'"
        ).fetchone()
        assert row[0] == "/home/test/project"

        # v3 ran successfully — schema version is 3
        version = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()[0]
        assert version == 3
        conn.close()

    def test_no_override_leaves_row_and_v3_aborts(self, tmp_path: Path) -> None:
        """Override file absent → row untouched, v3 pre-check aborts."""
        db_path = tmp_path / "master.db"
        self._create_v2_db_with_null_folder(db_path)

        with pytest.raises(RuntimeError, match="NULL project_folder"):
            run_master_migrations(str(db_path))

    def test_override_unknown_code_warns_not_errors(
        self, tmp_path: Path
    ) -> None:
        """Override references a code that doesn't exist → warning, not error."""
        db_path = tmp_path / "master.db"
        self._create_v2_db_with_null_folder(db_path)

        # Override has wrong code — the CBM row won't be healed, v3 aborts
        with pytest.raises(RuntimeError, match="NULL project_folder"):
            run_master_migrations(
                str(db_path),
                project_folder_overrides={"WRONG": "/some/path"},
            )

    def test_backup_created_before_heal(self, tmp_path: Path) -> None:
        """Master DB backup file is created before heal runs."""
        db_path = tmp_path / "master.db"
        self._create_v2_db_with_null_folder(db_path)

        # Count files before
        files_before = set(tmp_path.iterdir())

        conn = run_master_migrations(
            str(db_path),
            project_folder_overrides={"CBM": "/home/test/project"},
        )
        conn.close()

        # A backup file should exist
        files_after = set(tmp_path.iterdir())
        new_files = files_after - files_before
        backup_files = [f for f in new_files if "pre-v3-heal" in f.name]
        assert len(backup_files) == 1

    def test_no_backup_when_no_heal_needed(self, tmp_path: Path) -> None:
        """No backup when overrides are provided but no rows need healing."""
        db_path = tmp_path / "master.db"
        # Create a fresh DB (no NULL project_folder rows)
        conn = run_master_migrations(str(db_path))
        conn.close()

        files_before = set(tmp_path.iterdir())

        # Run again with overrides — should be no-op
        conn = run_master_migrations(
            str(db_path),
            project_folder_overrides={"CBM": "/home/test/project"},
        )
        conn.close()

        files_after = set(tmp_path.iterdir())
        new_files = files_after - files_before
        backup_files = [f for f in new_files if "pre-v3-heal" in f.name]
        assert len(backup_files) == 0

    def test_override_applied_then_v3_rebuild_succeeds(
        self, tmp_path: Path
    ) -> None:
        """Full end-to-end: override → heal → v3 rebuild → database_path nullable."""
        db_path = tmp_path / "master.db"
        self._create_v2_db_with_null_folder(db_path)

        conn = run_master_migrations(
            str(db_path),
            project_folder_overrides={"CBM": "/home/test/project"},
        )

        # database_path is now nullable after v3 rebuild
        col_info = conn.execute("PRAGMA table_info(Client)").fetchall()
        db_path_col = [c for c in col_info if c[1] == "database_path"][0]
        assert db_path_col[3] == 0  # notnull == 0

        # Insert without database_path works
        conn.execute(
            "INSERT INTO Client (name, code, project_folder) "
            "VALUES ('New', 'NW', '/tmp/new')"
        )
        conn.commit()
        conn.close()
