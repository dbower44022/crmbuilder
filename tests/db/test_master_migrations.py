"""Tests for master database schema and migrations.

Covers the Client table definition from L2 PRD v1.16 §3.1 and the
_master_v2 migration that adds project_folder, deployment_model, and
last_opened_at columns.
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

    def test_schema_version_is_2(self, db: sqlite3.Connection) -> None:
        row = db.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 2


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

    def test_backfill_edge_case_no_match(self, tmp_path: Path) -> None:
        """database_path that doesn't match the pattern leaves project_folder NULL."""
        db_path = tmp_path / "master.db"
        self._create_v1_db(db_path)
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Odd Client', 'ODD', '/some/random/path.db')"
        )
        conn.commit()
        conn.close()

        conn = run_master_migrations(str(db_path))
        row = conn.execute(
            "SELECT project_folder FROM Client WHERE code = 'ODD'"
        ).fetchone()
        assert row[0] is None
        conn.close()

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
        # Verify schema_version has exactly version 1 and 2, no duplicates.
        versions = conn.execute(
            "SELECT version FROM schema_version ORDER BY version"
        ).fetchall()
        assert [v[0] for v in versions] == [1, 2]
        conn.close()

    def test_existing_crm_platform_not_constrained(
        self, tmp_path: Path
    ) -> None:
        """On a migrated (non-fresh) database, crm_platform has no CHECK.

        The migration cannot add a CHECK to an existing column in SQLite.
        The application enforces it in code instead.
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
        # Migration should succeed even with a non-conforming value.
        conn = run_master_migrations(str(db_path))
        row = conn.execute(
            "SELECT crm_platform FROM Client WHERE code = 'OLD'"
        ).fetchone()
        assert row[0] == "WordPress"
        conn.close()
