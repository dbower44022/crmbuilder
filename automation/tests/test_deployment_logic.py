"""Tests for deployment tab view-model logic (Qt-free).

Covers: instance CRUD, picker population and default selection, phase
status banner work-item resolution per entry, empty-state resolution,
and default-flag semantics.
"""

from __future__ import annotations

import sqlite3

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deployment_logic import (
    ENTRY_TO_WORK_ITEM_TYPE,
    InstanceRow,
    create_instance,
    get_default_instance_id,
    get_phase_work_item,
    load_deployment_runs,
    load_instance_detail,
    load_instances,
    load_yaml_files,
    picker_display_text,
    set_default_instance,
    update_instance,
)


@pytest.fixture()
def client_db(tmp_path) -> sqlite3.Connection:
    """Create a fresh per-client database with all tables."""
    db_path = str(tmp_path / "client.db")
    conn = run_client_migrations(db_path)
    return conn


class TestInstanceCRUD:

    def test_load_empty(self, client_db):
        assert load_instances(client_db) == []

    def test_create_and_load(self, client_db):
        new_id = create_instance(
            client_db, name="Test", code="TS", environment="production",
            url="https://example.com", username="admin", password="pw",
        )
        assert new_id > 0

        instances = load_instances(client_db)
        assert len(instances) == 1
        assert instances[0].name == "Test"
        assert instances[0].code == "TS"
        assert instances[0].environment == "production"

    def test_load_detail(self, client_db):
        new_id = create_instance(
            client_db, name="Detail Test", code="DT", environment="staging",
            url="https://staging.example.com", username="admin",
            password="secret", description="A test instance",
        )
        detail = load_instance_detail(client_db, new_id)
        assert detail is not None
        assert detail.name == "Detail Test"
        assert detail.code == "DT"
        assert detail.environment == "staging"
        assert detail.url == "https://staging.example.com"
        assert detail.username == "admin"
        assert detail.password == "secret"
        assert detail.description == "A test instance"

    def test_load_detail_not_found(self, client_db):
        assert load_instance_detail(client_db, 9999) is None

    def test_update_instance(self, client_db):
        new_id = create_instance(
            client_db, name="Old Name", code="ON", environment="test",
        )
        update_instance(
            client_db, new_id, name="New Name",
            url="https://new.example.com", description="Updated",
        )
        detail = load_instance_detail(client_db, new_id)
        assert detail.name == "New Name"
        assert detail.url == "https://new.example.com"
        assert detail.description == "Updated"

    def test_update_preserves_unchanged(self, client_db):
        new_id = create_instance(
            client_db, name="Keep", code="KP", environment="production",
            url="https://keep.com", username="admin",
        )
        # Update only name — url/username should be unchanged
        update_instance(client_db, new_id, name="Kept")
        detail = load_instance_detail(client_db, new_id)
        assert detail.name == "Kept"
        assert detail.url == "https://keep.com"
        assert detail.username == "admin"


class TestDefaultFlagSemantics:

    def test_first_instance_default(self, client_db):
        create_instance(
            client_db, name="A", code="AA", environment="production",
            is_default=True,
        )
        assert get_default_instance_id(client_db) is not None

    def test_no_default(self, client_db):
        create_instance(
            client_db, name="A", code="AA", environment="production",
            is_default=False,
        )
        assert get_default_instance_id(client_db) is None

    def test_set_default_clears_previous(self, client_db):
        id1 = create_instance(
            client_db, name="A", code="AA", environment="production",
            is_default=True,
        )
        id2 = create_instance(
            client_db, name="B", code="BB", environment="test",
            is_default=False,
        )
        assert get_default_instance_id(client_db) == id1

        set_default_instance(client_db, id2)
        assert get_default_instance_id(client_db) == id2

        # Verify old default is cleared
        detail1 = load_instance_detail(client_db, id1)
        assert detail1.is_default is False
        detail2 = load_instance_detail(client_db, id2)
        assert detail2.is_default is True

    def test_create_with_default_clears_existing(self, client_db):
        id1 = create_instance(
            client_db, name="A", code="AA", environment="production",
            is_default=True,
        )
        id2 = create_instance(
            client_db, name="B", code="BB", environment="test",
            is_default=True,
        )
        # Only the new one should be default
        assert get_default_instance_id(client_db) == id2
        detail1 = load_instance_detail(client_db, id1)
        assert detail1.is_default is False


class TestPickerHelpers:

    def test_picker_display_text(self):
        inst = InstanceRow(
            id=1, name="My CRM", code="MC", environment="production",
            url="https://example.com", is_default=True,
        )
        assert picker_display_text(inst) == "My CRM (production)"

    def test_picker_with_staging(self):
        inst = InstanceRow(
            id=2, name="Staging", code="ST", environment="staging",
            url=None, is_default=False,
        )
        assert picker_display_text(inst) == "Staging (staging)"


class TestDeploymentRuns:

    def test_load_empty(self, client_db):
        assert load_deployment_runs(client_db) == []

    def test_load_runs(self, client_db):
        # Create an instance first
        inst_id = create_instance(
            client_db, name="Inst", code="IN", environment="production",
        )
        # Insert a deployment run
        client_db.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, outcome) "
            "VALUES (?, ?, ?, ?, ?)",
            (inst_id, "self_hosted", "EspoCRM", "2025-01-01T00:00:00", "success"),
        )
        client_db.commit()

        runs = load_deployment_runs(client_db)
        assert len(runs) == 1
        assert runs[0].instance_name == "Inst"
        assert runs[0].scenario == "self_hosted"
        assert runs[0].outcome == "success"


class TestYamlFiles:

    def test_no_project_folder(self):
        assert load_yaml_files(None) == []

    def test_empty_programs_dir(self, tmp_path):
        (tmp_path / "programs").mkdir()
        assert load_yaml_files(str(tmp_path)) == []

    def test_missing_programs_dir(self, tmp_path):
        assert load_yaml_files(str(tmp_path)) == []

    def test_loads_yaml_files(self, tmp_path):
        programs = tmp_path / "programs"
        programs.mkdir()
        (programs / "contacts.yaml").write_text("entities: []")
        (programs / "accounts.yml").write_text("entities: []")
        (programs / "readme.txt").write_text("ignore")

        files = load_yaml_files(str(tmp_path))
        assert len(files) == 2
        names = [f.name for f in files]
        assert "accounts.yml" in names
        assert "contacts.yaml" in names


class TestPhaseWorkItem:

    def test_entry_to_work_item_type_mapping(self):
        assert ENTRY_TO_WORK_ITEM_TYPE["Deploy"] == "crm_deployment"
        assert ENTRY_TO_WORK_ITEM_TYPE["Configure"] == "crm_configuration"
        assert ENTRY_TO_WORK_ITEM_TYPE["Verify"] == "verification"
        assert "Instances" not in ENTRY_TO_WORK_ITEM_TYPE
        assert "Output" not in ENTRY_TO_WORK_ITEM_TYPE

    def test_no_work_item(self, client_db):
        result = get_phase_work_item(client_db, "crm_deployment")
        assert result is None

    def test_loads_work_item(self, client_db):
        client_db.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES (?, ?)",
            ("crm_deployment", "not_started"),
        )
        client_db.commit()

        result = get_phase_work_item(client_db, "crm_deployment")
        assert result is not None
        assert result.item_type == "crm_deployment"
        assert result.status == "not_started"


class TestEmptyStates:
    """Verify the empty-state resolution logic."""

    def test_no_instances_implies_empty(self, client_db):
        instances = load_instances(client_db)
        assert len(instances) == 0

    def test_with_instances_not_empty(self, client_db):
        create_instance(
            client_db, name="A", code="AA", environment="production",
        )
        instances = load_instances(client_db)
        assert len(instances) == 1
