"""Tests for Clients tab pure logic — list loading, sorting, validation."""

import sqlite3

from automation.core.active_client_state import Client
from automation.core.client_reachability import check_reachability
from automation.core.create_client import CODE_PATTERN
from automation.db.migrations import run_master_migrations
from automation.ui.clients_tab import load_all_clients


def _setup_master(tmp_path):
    """Create and return a master database path."""
    db_path = str(tmp_path / "master.db")
    conn = run_master_migrations(db_path)
    conn.close()
    return db_path


def _insert_client(master_db, name, code, project_folder, last_opened=None):
    """Insert a client row into the master database."""
    conn = sqlite3.connect(master_db)
    conn.execute(
        "INSERT INTO Client (name, code, project_folder, last_opened_at) "
        "VALUES (?, ?, ?, ?)",
        (name, code, project_folder, last_opened),
    )
    conn.commit()
    conn.close()


class TestLoadAllClients:

    def test_empty_database(self, tmp_path):
        master = _setup_master(tmp_path)
        clients = load_all_clients(master)
        assert clients == []

    def test_returns_client_objects(self, tmp_path):
        master = _setup_master(tmp_path)
        _insert_client(master, "Alpha", "ALP", str(tmp_path / "a"))
        clients = load_all_clients(master)
        assert len(clients) == 1
        assert isinstance(clients[0], Client)
        assert clients[0].name == "Alpha"
        assert clients[0].code == "ALP"

    def test_default_sort_last_opened_desc_nulls_last(self, tmp_path):
        master = _setup_master(tmp_path)
        _insert_client(master, "Old", "OLD", str(tmp_path / "a"), "2024-01-01")
        _insert_client(master, "New", "NEW", str(tmp_path / "b"), "2024-06-01")
        _insert_client(master, "Never", "NVR", str(tmp_path / "c"), None)

        clients = load_all_clients(master)
        names = [c.name for c in clients]
        # Most recent first, NULL last
        assert names == ["New", "Old", "Never"]

    def test_all_nulls(self, tmp_path):
        master = _setup_master(tmp_path)
        _insert_client(master, "A", "AA", str(tmp_path / "a"), None)
        _insert_client(master, "B", "BB", str(tmp_path / "b"), None)
        clients = load_all_clients(master)
        assert len(clients) == 2


class TestCodePattern:

    def test_valid_codes(self):
        for code in ("AB", "CBM", "A1", "ABCDEFGHIJ"):
            assert CODE_PATTERN.match(code), f"'{code}' should be valid"

    def test_invalid_codes(self):
        for code in ("a", "Ab", "1AB", "A", "ABCDEFGHIJK", "", "A-B"):
            assert not CODE_PATTERN.match(code), f"'{code}' should be invalid"


class TestReachabilityIntegration:
    """Integration-level tests verifying reachability with real files."""

    def test_fully_reachable(self, tmp_path):
        project = tmp_path / "project"
        project.mkdir()
        crmbuilder = project / ".crmbuilder"
        crmbuilder.mkdir()
        db_path = crmbuilder / "TST.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        result = check_reachability(str(project), "TST")
        assert result.is_reachable is True

    def test_not_reachable_no_folder(self, tmp_path):
        result = check_reachability(str(tmp_path / "missing"), "TST")
        assert result.is_reachable is False


class TestClientDatabasePath:

    def test_derived_path(self):
        c = Client(
            id=1, name="X", code="XYZ", description=None,
            project_folder="/home/user/clients/xyz",
        )
        assert c.database_path == "/home/user/clients/xyz/.crmbuilder/XYZ.db"
