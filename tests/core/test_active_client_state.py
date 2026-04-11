"""Tests for automation.core.active_client_state — pure state transitions."""

from automation.core.active_client_state import ActiveClientState, Client


def _make_client(**overrides) -> Client:
    defaults = {
        "id": 1, "name": "Test Corp", "code": "TST", "description": None,
        "project_folder": "/tmp/test",
    }
    defaults.update(overrides)
    return Client(**defaults)


class TestClient:

    def test_database_path(self):
        c = _make_client(project_folder="/home/user/project", code="CBM")
        assert c.database_path == "/home/user/project/.crmbuilder/CBM.db"

    def test_fields(self):
        c = _make_client(
            id=5, name="Acme", code="ACM", description="desc",
            project_folder="/acme",
            crm_platform="EspoCRM",
            deployment_model="self_hosted",
            last_opened_at="2024-01-01",
            created_at="2024-01-01",
            updated_at="2024-01-01",
        )
        assert c.id == 5
        assert c.name == "Acme"
        assert c.code == "ACM"
        assert c.description == "desc"
        assert c.project_folder == "/acme"
        assert c.crm_platform == "EspoCRM"
        assert c.deployment_model == "self_hosted"

    def test_optional_fields_default_none(self):
        c = _make_client()
        assert c.crm_platform is None
        assert c.deployment_model is None
        assert c.last_opened_at is None
        assert c.created_at is None
        assert c.updated_at is None


class TestActiveClientState:

    def test_initially_no_client(self):
        state = ActiveClientState()
        assert state.client is None
        assert state.is_active is False

    def test_activate(self):
        state = ActiveClientState()
        client = _make_client()
        state.activate(client)
        assert state.client is client
        assert state.is_active is True

    def test_clear(self):
        state = ActiveClientState()
        state.activate(_make_client())
        state.clear()
        assert state.client is None
        assert state.is_active is False

    def test_activate_replaces_previous(self):
        state = ActiveClientState()
        state.activate(_make_client(id=1, name="A"))
        state.activate(_make_client(id=2, name="B"))
        assert state.client.id == 2
        assert state.client.name == "B"

    def test_activate_after_clear(self):
        state = ActiveClientState()
        c = _make_client()
        state.activate(c)
        state.clear()
        state.activate(c)
        assert state.is_active is True

    def test_clear_when_already_empty(self):
        state = ActiveClientState()
        state.clear()
        assert state.client is None
