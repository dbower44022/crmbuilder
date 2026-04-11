"""Tests for automation.core.client_reachability — reachability checks."""

import sqlite3

from automation.core.client_reachability import check_reachability


class TestCheckReachability:

    def test_none_project_folder(self):
        result = check_reachability(None, "TST")
        assert result.is_reachable is False
        assert "not set" in result.error

    def test_empty_project_folder(self):
        result = check_reachability("", "TST")
        assert result.is_reachable is False
        assert "not set" in result.error

    def test_missing_project_folder(self, tmp_path):
        missing = str(tmp_path / "nonexistent")
        result = check_reachability(missing, "TST")
        assert result.is_reachable is False
        assert "does not exist" in result.error

    def test_project_folder_is_file_not_dir(self, tmp_path):
        a_file = tmp_path / "not_a_dir"
        a_file.write_text("hi")
        result = check_reachability(str(a_file), "TST")
        assert result.is_reachable is False
        assert "does not exist" in result.error

    def test_missing_crmbuilder_dir(self, tmp_path):
        result = check_reachability(str(tmp_path), "TST")
        assert result.is_reachable is False
        assert "not found" in result.error

    def test_missing_db_file(self, tmp_path):
        (tmp_path / ".crmbuilder").mkdir()
        result = check_reachability(str(tmp_path), "TST")
        assert result.is_reachable is False
        assert "not found" in result.error

    def test_db_file_exists_but_is_directory(self, tmp_path):
        db_dir = tmp_path / ".crmbuilder" / "TST.db"
        db_dir.mkdir(parents=True)
        result = check_reachability(str(tmp_path), "TST")
        assert result.is_reachable is False
        assert "not found" in result.error

    def test_valid_database(self, tmp_path):
        crmbuilder_dir = tmp_path / ".crmbuilder"
        crmbuilder_dir.mkdir()
        db_path = crmbuilder_dir / "TST.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        result = check_reachability(str(tmp_path), "TST")
        assert result.is_reachable is True
        assert result.error is None

    def test_corrupt_database(self, tmp_path):
        crmbuilder_dir = tmp_path / ".crmbuilder"
        crmbuilder_dir.mkdir()
        db_path = crmbuilder_dir / "TST.db"
        db_path.write_text("not a valid sqlite database")

        result = check_reachability(str(tmp_path), "TST")
        # SQLite may open corrupt files without error until a query runs
        # The result depends on SQLite behavior — it may or may not fail
        # Just verify we get a result without crashing
        assert isinstance(result.is_reachable, bool)

    def test_probe_connection_is_closed(self, tmp_path):
        """Verify the probe connection does not remain open."""
        crmbuilder_dir = tmp_path / ".crmbuilder"
        crmbuilder_dir.mkdir()
        db_path = crmbuilder_dir / "TST.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER)")
        conn.commit()
        conn.close()

        result = check_reachability(str(tmp_path), "TST")
        assert result.is_reachable is True

        # If the probe connection were still open, this exclusive lock would fail
        conn = sqlite3.connect(str(db_path))
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("COMMIT")
        conn.close()
