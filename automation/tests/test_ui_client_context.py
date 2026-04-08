"""Tests for automation.ui.client_context — client selection state."""

from automation.db.migrations import run_master_migrations
from automation.ui.client_context import ClientContext, ClientInfo, load_clients


class TestClientInfo:

    def test_fields(self):
        info = ClientInfo(id=1, name="Test Client", code="TST", database_path="/tmp/test.db")
        assert info.id == 1
        assert info.name == "Test Client"
        assert info.code == "TST"
        assert info.database_path == "/tmp/test.db"


class TestClientContext:

    def test_initially_no_client(self):
        ctx = ClientContext()
        assert ctx.client is None
        assert ctx.is_selected is False
        assert ctx.client_name == ""
        assert ctx.database_path is None

    def test_select_client(self):
        ctx = ClientContext()
        client = ClientInfo(1, "Acme Corp", "ACME", "/tmp/acme.db")
        ctx.select(client)
        assert ctx.client is client
        assert ctx.is_selected is True
        assert ctx.client_name == "Acme Corp"
        assert ctx.database_path == "/tmp/acme.db"

    def test_clear_client(self):
        ctx = ClientContext()
        ctx.select(ClientInfo(1, "Acme", "ACME", "/tmp/a.db"))
        ctx.clear()
        assert ctx.client is None
        assert ctx.is_selected is False

    def test_on_change_callback(self):
        ctx = ClientContext()
        changes = []
        ctx.on_change(lambda c: changes.append(c))

        client = ClientInfo(1, "Test", "TST", "/tmp/t.db")
        ctx.select(client)
        assert len(changes) == 1
        assert changes[0] is client

    def test_on_change_called_on_clear(self):
        ctx = ClientContext()
        changes = []
        ctx.on_change(lambda c: changes.append(c))
        ctx.select(ClientInfo(1, "Test", "TST", "/tmp/t.db"))
        ctx.clear()
        assert len(changes) == 2
        assert changes[1] is None

    def test_multiple_callbacks(self):
        ctx = ClientContext()
        calls_a = []
        calls_b = []
        ctx.on_change(lambda c: calls_a.append(c))
        ctx.on_change(lambda c: calls_b.append(c))
        ctx.select(ClientInfo(1, "X", "X", "/tmp/x.db"))
        assert len(calls_a) == 1
        assert len(calls_b) == 1

    def test_select_replaces_previous(self):
        ctx = ClientContext()
        ctx.select(ClientInfo(1, "A", "A", "/a.db"))
        ctx.select(ClientInfo(2, "B", "B", "/b.db"))
        assert ctx.client.id == 2
        assert ctx.client_name == "B"


class TestLoadClients:

    def test_load_from_empty_database(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        conn.close()
        clients = load_clients(str(db_path))
        assert clients == []

    def test_load_clients(self, tmp_path):
        db_path = tmp_path / "master.db"
        conn = run_master_migrations(str(db_path))
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Zebra Corp', 'ZEB', '/tmp/zeb.db')"
        )
        conn.execute(
            "INSERT INTO Client (name, code, database_path) "
            "VALUES ('Alpha Inc', 'ALP', '/tmp/alp.db')"
        )
        conn.commit()
        conn.close()

        clients = load_clients(str(db_path))
        assert len(clients) == 2
        # Sorted by name
        assert clients[0].name == "Alpha Inc"
        assert clients[1].name == "Zebra Corp"
        assert clients[0].code == "ALP"
