"""Tests for the migration runner."""

import sqlite3

import pytest

from automation.db.migrations import (
    run_client_migrations,
    run_master_migrations,
)


class TestMasterMigrations:
    def test_creates_schema_version_table(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = 'schema_version'"
        ).fetchall()
        assert len(tables) == 1
        conn.close()

    def test_creates_client_table(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name = 'Client'"
        ).fetchall()
        assert len(tables) == 1
        conn.close()

    def test_records_version(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 1
        conn.close()

    def test_idempotent(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn1 = run_master_migrations(str(db_path))
        conn1.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Test', 'TST', '/test.db')"
        )
        conn1.commit()
        conn1.close()

        conn2 = run_master_migrations(str(db_path))
        row = conn2.execute("SELECT COUNT(*) FROM Client").fetchone()
        assert row[0] == 1
        versions = conn2.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()
        assert versions[0] == 1
        conn2.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()


class TestClientMigrations:
    def test_creates_all_tables(self, tmp_path):
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        tables = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'schema_version'"
        ).fetchone()
        assert tables[0] == 25
        conn.close()

    def test_records_version(self, tmp_path):
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        row = conn.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 1
        conn.close()

    def test_idempotent(self, tmp_path):
        db_path = tmp_path / "client.db"
        conn1 = run_client_migrations(str(db_path))
        conn1.execute(
            "INSERT INTO Domain (name, code) VALUES ('Test', 'TST')"
        )
        conn1.commit()
        conn1.close()

        conn2 = run_client_migrations(str(db_path))
        row = conn2.execute("SELECT COUNT(*) FROM Domain").fetchone()
        assert row[0] == 1
        versions = conn2.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()
        assert versions[0] == 1
        conn2.close()

    def test_foreign_keys_enabled(self, tmp_path):
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        result = conn.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1
        conn.close()

    def test_constraints_enforced_after_migration(self, tmp_path):
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO Entity (name, code, entity_type, is_native) "
                "VALUES ('Bad', 'BAD', 'Invalid', 0)"
            )
        conn.close()

    def test_idempotent_no_extra_version_rows(self, tmp_path):
        db_path = tmp_path / "client.db"
        for _ in range(3):
            conn = run_client_migrations(str(db_path))
            conn.close()
        conn = run_client_migrations(str(db_path))
        versions = conn.execute(
            "SELECT COUNT(*) FROM schema_version"
        ).fetchone()
        assert versions[0] == 1
        conn.close()
