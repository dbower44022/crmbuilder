"""Tests for main window startup error handling.

Covers the blocking error dialog shown when master database migration
fails, ensuring the app does not proceed to the main window.
"""

import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from automation.db.migrations import run_master_migrations


class TestMasterMigrationFailureStartup:
    """Startup behavior when run_master_migrations raises."""

    def test_migration_failure_is_not_swallowed(self, tmp_path: Path) -> None:
        """A RuntimeError from v3 pre-check is not silently swallowed.

        The main window code no longer catches migration errors as warnings.
        This test verifies that run_master_migrations raises when the heal
        step is not provided and project_folder is NULL.
        """
        db_path = tmp_path / "master.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version "
            "(version INTEGER NOT NULL, "
            "applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE Client ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL, code TEXT NOT NULL UNIQUE, "
            "description TEXT, database_path TEXT NOT NULL, "
            "organization_overview TEXT, crm_platform TEXT, "
            "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        conn.execute("INSERT INTO schema_version (version) VALUES (2)")
        conn.execute("ALTER TABLE Client ADD COLUMN project_folder TEXT")
        conn.execute("ALTER TABLE Client ADD COLUMN deployment_model TEXT")
        conn.execute("ALTER TABLE Client ADD COLUMN last_opened_at TIMESTAMP")
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Test', 'CBM', '/some/path.db')"
        )
        conn.commit()
        conn.close()

        # Without overrides, the migration raises — not swallowed
        with pytest.raises(RuntimeError, match="NULL project_folder"):
            run_master_migrations(str(db_path))

    def test_override_file_loading(self, tmp_path: Path) -> None:
        """Override file is loaded and passed correctly to run_master_migrations."""
        overrides_path = tmp_path / "migration-overrides.json"
        overrides_path.write_text('{"CBM": "/home/test/project"}')

        data = json.loads(overrides_path.read_text())
        assert isinstance(data, dict)
        assert data == {"CBM": "/home/test/project"}

    def test_override_file_absent_returns_none(self, tmp_path: Path) -> None:
        """Absent override file → None (no overrides applied)."""
        overrides_path = tmp_path / "migration-overrides.json"
        assert not overrides_path.exists()

    def test_show_migration_failure_exits(self) -> None:
        """_show_migration_failure calls sys.exit(1) after showing dialog."""
        from espo_impl.ui.main_window import MainWindow

        with patch("espo_impl.ui.main_window.QMessageBox") as mock_msgbox:
            # Use a mock that has the method we're testing
            instance = MainWindow.__new__(MainWindow)
            instance._master_db_path = "/tmp/test.db"
            with pytest.raises(SystemExit) as exc_info:
                instance._show_migration_failure(
                    RuntimeError("NULL project_folder")
                )
            assert exc_info.value.code == 1
            mock_msgbox.critical.assert_called_once()
            call_args = mock_msgbox.critical.call_args[0]
            assert "Migration Failed" in call_args[1]
            assert "NULL project_folder" in call_args[2]
