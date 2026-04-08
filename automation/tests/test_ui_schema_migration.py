"""Tests for the ChangeImpact action_required column migration (ISS-012)."""

import sqlite3

from automation.db.client_schema import SCHEMA_VERSION_TABLE
from automation.db.connection import open_connection
from automation.db.migrations import run_client_migrations


def _get_column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    """Return column names for a table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


class TestActionRequiredMigration:

    def test_fresh_database_has_column(self, tmp_path):
        """A fresh database created via run_client_migrations has action_required."""
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        cols = _get_column_names(conn, "ChangeImpact")
        assert "action_required" in cols
        conn.close()

    def test_old_database_gets_column(self, tmp_path):
        """An old database without the column gets it added by migration v2."""
        db_path = tmp_path / "client.db"
        conn = open_connection(str(db_path))
        # Create schema_version table and record v1 as applied
        conn.execute(SCHEMA_VERSION_TABLE)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        # Create a ChangeImpact table WITHOUT action_required (simulating v1)
        conn.execute("""
            CREATE TABLE ChangeImpact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_log_id INTEGER NOT NULL,
                affected_table TEXT NOT NULL,
                affected_record_id INTEGER NOT NULL,
                impact_description TEXT,
                requires_review BOOLEAN NOT NULL DEFAULT TRUE,
                reviewed BOOLEAN NOT NULL DEFAULT FALSE,
                reviewed_at TIMESTAMP
            )
        """)
        # Create the other tables the migration runner needs (WorkItem, etc.)
        # We just need ChangeImpact to exist for the v2 migration to run
        conn.commit()
        conn.close()

        # Re-open via migration runner — should apply v2
        conn = run_client_migrations(str(db_path))
        cols = _get_column_names(conn, "ChangeImpact")
        assert "action_required" in cols
        conn.close()

    def test_column_default_value(self, tmp_path):
        """The action_required column defaults to 0 (FALSE)."""
        db_path = tmp_path / "client.db"
        conn = run_client_migrations(str(db_path))
        # Create supporting data for ChangeImpact FK
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (1, 'master_prd', 'in_progress')"
        )
        conn.execute(
            "INSERT INTO AISession (id, work_item_id, session_type, "
            "generated_prompt, import_status, started_at) "
            "VALUES (1, 1, 'initial', 'p', 'imported', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, changed_at) VALUES (1, 1, 'Field', 1, 'insert', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO ChangeImpact (change_log_id, affected_table, "
            "affected_record_id, requires_review) VALUES (1, 'Field', 1, 1)"
        )
        conn.commit()

        row = conn.execute(
            "SELECT action_required FROM ChangeImpact WHERE id = 1"
        ).fetchone()
        assert row[0] == 0
        conn.close()

    def test_migration_idempotent(self, tmp_path):
        """Running migrations twice does not error."""
        db_path = tmp_path / "client.db"
        conn1 = run_client_migrations(str(db_path))
        conn1.close()

        conn2 = run_client_migrations(str(db_path))
        cols = _get_column_names(conn2, "ChangeImpact")
        assert "action_required" in cols
        # Version should still be 2
        row = conn2.execute(
            "SELECT MAX(version) FROM schema_version"
        ).fetchone()
        assert row[0] == 2
        conn2.close()

    def test_existing_data_preserved(self, tmp_path):
        """Existing ChangeImpact rows are preserved after migration."""
        db_path = tmp_path / "client.db"
        conn = open_connection(str(db_path))
        conn.execute(SCHEMA_VERSION_TABLE)
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        # Create v1 ChangeImpact table
        conn.execute("""
            CREATE TABLE ChangeImpact (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_log_id INTEGER NOT NULL,
                affected_table TEXT NOT NULL,
                affected_record_id INTEGER NOT NULL,
                impact_description TEXT,
                requires_review BOOLEAN NOT NULL DEFAULT TRUE,
                reviewed BOOLEAN NOT NULL DEFAULT FALSE,
                reviewed_at TIMESTAMP
            )
        """)
        conn.execute(
            "INSERT INTO ChangeImpact (change_log_id, affected_table, "
            "affected_record_id, requires_review) VALUES (1, 'Field', 1, 1)"
        )
        conn.commit()
        conn.close()

        conn = run_client_migrations(str(db_path))
        row = conn.execute(
            "SELECT change_log_id, affected_table, action_required "
            "FROM ChangeImpact WHERE id = 1"
        ).fetchone()
        assert row[0] == 1
        assert row[1] == "Field"
        assert row[2] == 0  # Default applied to existing row
        conn.close()
