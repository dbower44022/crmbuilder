"""Widget smoke tests for the five deployment sidebar entries.

Verifies each entry view renders without error against a fixture
per-client database containing zero, one, and multiple instances.

These tests require PySide6 and are skipped if the display is not
available (e.g. headless CI without Xvfb).
"""

from __future__ import annotations

import os
import sqlite3
import sys

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deployment_logic import create_instance


def _pyside6_available() -> bool:
    """Check if PySide6 is importable and a display server is available."""
    try:
        import PySide6  # noqa: F401
    except ImportError:
        return False
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return True
    return sys.platform in ("darwin", "win32")


# Skip all tests in this module if PySide6 or display is unavailable
pytestmark = pytest.mark.skipif(
    not _pyside6_available(),
    reason="PySide6 or display not available for widget tests",
)


@pytest.fixture()
def qapp():
    """Create or return the QApplication instance."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture()
def empty_db(tmp_path) -> sqlite3.Connection:
    """Per-client database with zero instances."""
    conn = run_client_migrations(str(tmp_path / "empty.db"))
    return conn


@pytest.fixture()
def single_db(tmp_path) -> sqlite3.Connection:
    """Per-client database with one instance."""
    conn = run_client_migrations(str(tmp_path / "single.db"))
    create_instance(conn, name="Alpha", code="AL", environment="production",
                    url="https://alpha.example.com", is_default=True)
    return conn


@pytest.fixture()
def multi_db(tmp_path) -> sqlite3.Connection:
    """Per-client database with multiple instances."""
    conn = run_client_migrations(str(tmp_path / "multi.db"))
    create_instance(conn, name="Alpha", code="AL", environment="production",
                    url="https://alpha.example.com", is_default=True)
    create_instance(conn, name="Beta", code="BE", environment="staging",
                    url="https://beta.example.com")
    create_instance(conn, name="Gamma", code="GA", environment="test")
    return conn


class TestInstancesEntry:
    def test_renders_empty(self, qapp, empty_db):
        from automation.ui.deployment.instances_entry import InstancesEntry
        w = InstancesEntry()
        w.refresh(empty_db)
        assert w._empty_label.isVisible()
        assert not w._splitter.isVisible()

    def test_renders_single(self, qapp, single_db):
        from automation.ui.deployment.instances_entry import InstancesEntry
        w = InstancesEntry()
        w.refresh(single_db)
        assert not w._empty_label.isVisible()
        assert w._splitter.isVisible()
        assert w._table.rowCount() == 1

    def test_renders_multiple(self, qapp, multi_db):
        from automation.ui.deployment.instances_entry import InstancesEntry
        w = InstancesEntry()
        w.refresh(multi_db)
        assert w._table.rowCount() == 3


class TestDeployEntry:
    def test_renders_no_instances(self, qapp, empty_db):
        from automation.ui.deployment.deploy_entry import DeployEntry
        w = DeployEntry()
        w.refresh(empty_db, None, has_instances=False)
        assert w._empty_label.isVisible()

    def test_renders_no_runs(self, qapp, single_db):
        from automation.ui.deployment.deploy_entry import DeployEntry
        from automation.ui.deployment.deployment_logic import load_instances
        inst = load_instances(single_db)[0]
        w = DeployEntry()
        w.refresh(single_db, inst, has_instances=True)
        assert w._empty_label.isVisible()

    def test_renders_with_runs(self, qapp, single_db):
        from automation.ui.deployment.deploy_entry import DeployEntry
        from automation.ui.deployment.deployment_logic import load_instances
        inst = load_instances(single_db)[0]
        # Insert a run
        single_db.execute(
            "INSERT INTO DeploymentRun "
            "(instance_id, scenario, crm_platform, started_at, outcome) "
            "VALUES (?, ?, ?, ?, ?)",
            (inst.id, "self_hosted", "EspoCRM", "2025-01-01T00:00:00", "success"),
        )
        single_db.commit()
        w = DeployEntry()
        w.refresh(single_db, inst, has_instances=True)
        assert w._table.isVisible()
        assert w._table.rowCount() == 1


class TestConfigureEntry:
    def test_renders_no_instances(self, qapp, empty_db):
        from automation.ui.deployment.configure_entry import ConfigureEntry
        w = ConfigureEntry()
        w.refresh(empty_db, None, None, has_instances=False)
        assert w._empty_label.isVisible()

    def test_renders_no_yaml(self, qapp, single_db, tmp_path):
        from automation.ui.deployment.configure_entry import ConfigureEntry
        from automation.ui.deployment.deployment_logic import load_instances
        inst = load_instances(single_db)[0]
        w = ConfigureEntry()
        w.refresh(single_db, inst, str(tmp_path), has_instances=True)
        assert w._empty_label.isVisible()

    def test_renders_with_yaml(self, qapp, single_db, tmp_path):
        from automation.ui.deployment.configure_entry import ConfigureEntry
        from automation.ui.deployment.deployment_logic import load_instances
        inst = load_instances(single_db)[0]
        programs = tmp_path / "programs"
        programs.mkdir()
        (programs / "contacts.yaml").write_text("entities: []")
        w = ConfigureEntry()
        w.refresh(single_db, inst, str(tmp_path), has_instances=True)
        assert w._table.isVisible()
        assert w._table.rowCount() == 1


class TestVerifyEntry:
    def test_renders_no_instances(self, qapp, empty_db):
        from automation.ui.deployment.verify_entry import VerifyEntry
        w = VerifyEntry()
        w.refresh(empty_db, None, has_instances=False)
        assert not w._run_btn.isVisible()

    def test_renders_with_instance(self, qapp, single_db):
        from automation.ui.deployment.deployment_logic import load_instances
        from automation.ui.deployment.verify_entry import VerifyEntry
        inst = load_instances(single_db)[0]
        w = VerifyEntry()
        w.refresh(single_db, inst, has_instances=True)
        assert w._run_btn.isVisible()


class TestOutputEntry:
    def test_renders_no_instances(self, qapp, empty_db):
        from automation.ui.deployment.output_entry import OutputEntry
        w = OutputEntry()
        w.refresh(empty_db, None, has_instances=False)
        assert w._empty_label.isVisible()

    def test_renders_with_instance(self, qapp, single_db):
        from automation.ui.deployment.deployment_logic import load_instances
        from automation.ui.deployment.output_entry import OutputEntry
        inst = load_instances(single_db)[0]
        w = OutputEntry()
        w.refresh(single_db, inst, has_instances=True)
        assert w._log_view.isVisible()

    def test_append_line(self, qapp, single_db):
        from automation.ui.deployment.deployment_logic import load_instances
        from automation.ui.deployment.output_entry import OutputEntry
        inst = load_instances(single_db)[0]
        w = OutputEntry()
        w.refresh(single_db, inst, has_instances=True)
        w.append_line("Test log message", "info")
        assert "Test log message" in w._log_view.toPlainText()


class TestInstancePicker:
    def test_empty_db(self, qapp, empty_db):
        from automation.ui.deployment.instance_picker import InstancePicker
        p = InstancePicker()
        p.refresh(empty_db)
        assert p.selected_instance is None

    def test_single_default(self, qapp, single_db):
        from automation.ui.deployment.instance_picker import InstancePicker
        p = InstancePicker()
        p.refresh(single_db)
        assert p.selected_instance is not None
        assert p.selected_instance.name == "Alpha"

    def test_preserves_selection_on_refresh(self, qapp, multi_db):
        from automation.ui.deployment.instance_picker import InstancePicker
        p = InstancePicker()
        p.refresh(multi_db)
        # Select the second instance
        p._combo.setCurrentIndex(1)
        selected_id = p.selected_instance.id
        # Refresh — should preserve
        p.refresh(multi_db)
        assert p.selected_instance.id == selected_id
