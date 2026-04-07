"""Tests for master database schema."""

import sqlite3

import pytest

from automation.db.master_schema import SCHEMA_VERSION_TABLE, get_master_schema_sql


@pytest.fixture()
def master_db(tmp_path):
    """Create a master database with the full schema applied."""
    db_path = tmp_path / "master.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(SCHEMA_VERSION_TABLE)
    for stmt in get_master_schema_sql():
        conn.execute(stmt)
    conn.commit()
    yield conn
    conn.close()


class TestClientTable:
    """Tests for the Client table."""

    def test_create_client(self, master_db):
        master_db.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Cleveland Business Mentors', 'CBM', '/data/cbm.db')"
        )
        master_db.commit()
        row = master_db.execute("SELECT * FROM Client WHERE code = 'CBM'").fetchone()
        assert row is not None

    def test_name_not_null(self, master_db):
        with pytest.raises(sqlite3.IntegrityError):
            master_db.execute(
                "INSERT INTO Client (code, database_path) "
                "VALUES ('CBM', '/data/cbm.db')"
            )

    def test_code_not_null(self, master_db):
        with pytest.raises(sqlite3.IntegrityError):
            master_db.execute(
                "INSERT INTO Client (name, database_path) "
                "VALUES ('Test Org', '/data/test.db')"
            )

    def test_database_path_not_null(self, master_db):
        with pytest.raises(sqlite3.IntegrityError):
            master_db.execute(
                "INSERT INTO Client (name, code) "
                "VALUES ('Test Org', 'TST')"
            )

    def test_code_unique(self, master_db):
        master_db.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Org A', 'DUP', '/data/a.db')"
        )
        master_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            master_db.execute(
                "INSERT INTO Client (name, code, database_path) "
                "VALUES ('Org B', 'DUP', '/data/b.db')"
            )

    def test_optional_fields_nullable(self, master_db):
        master_db.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Org', 'ORG', '/data/org.db')"
        )
        master_db.commit()
        row = master_db.execute(
            "SELECT description, organization_overview, crm_platform "
            "FROM Client WHERE code = 'ORG'"
        ).fetchone()
        assert row == (None, None, None)

    def test_organization_overview_and_crm_platform(self, master_db):
        master_db.execute(
            "INSERT INTO Client (name, code, database_path, "
            "organization_overview, crm_platform) "
            "VALUES ('Org', 'ORG', '/data/org.db', "
            "'A nonprofit...', 'EspoCRM')"
        )
        master_db.commit()
        row = master_db.execute(
            "SELECT organization_overview, crm_platform "
            "FROM Client WHERE code = 'ORG'"
        ).fetchone()
        assert row == ("A nonprofit...", "EspoCRM")

    def test_timestamps_default(self, master_db):
        master_db.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Org', 'ORG', '/data/org.db')"
        )
        master_db.commit()
        row = master_db.execute(
            "SELECT created_at, updated_at FROM Client WHERE code = 'ORG'"
        ).fetchone()
        assert row[0] is not None
        assert row[1] is not None

    def test_table_can_be_dropped(self, master_db):
        master_db.execute("DROP TABLE Client")


class TestSchemaVersionTable:
    """Tests for the schema_version table."""

    def test_create_schema_version(self, master_db):
        master_db.execute(
            "INSERT INTO schema_version (version) VALUES (1)"
        )
        master_db.commit()
        row = master_db.execute(
            "SELECT version, applied_at FROM schema_version"
        ).fetchone()
        assert row[0] == 1
        assert row[1] is not None
