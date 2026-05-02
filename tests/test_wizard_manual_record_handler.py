"""Tests for the wizard's manual Deployment Record regeneration handler.

Covers ``DeployWizard._on_generate_record_manually`` — the Result page
button shown when automatic Record generation fails after a successful
deploy. The handler is supposed to launch
``launch_regeneration_dialog`` from
:mod:`automation.ui.deployment.regenerate_record_dialog`, not the
placeholder QMessageBox that lived there during Prompt C's authoring.

Tests use a SimpleNamespace-style stub of the wizard rather than
constructing a full :class:`DeployWizard` instance — the handler reads
only ``self._conn``, ``self._instance_id``, ``self._master_db_path``,
``self._client_id``, plus the ``_read_project_folder`` method, so a
partial fake is sufficient and far more reliable than booting Qt and
the wizard's nine-page stack.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    save_deploy_config,
)
from automation.core.deployment.wizard_logic import create_wizard_instance
from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deploy_wizard import wizard_dialog

pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY", "") == ""
    and os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Qt-dependent tests require a display or QT_QPA_PLATFORM=offscreen",
)


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class _MemoryBackend(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            from keyring.errors import PasswordDeleteError
            raise PasswordDeleteError(username)
        del self._store[(service, username)]


@pytest.fixture(autouse=True)
def _memory_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    backend = _MemoryBackend()
    original = keyring.get_keyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(original)


@pytest.fixture()
def populated_db(tmp_path: Path):
    """A migrated client DB with one Instance and its deploy config."""
    db_file = tmp_path / "client.db"
    conn = run_client_migrations(str(db_file))
    instance_id = create_wizard_instance(
        conn, name="CBM Test", code="CBMTEST", environment="test",
    )
    save_deploy_config(
        conn,
        InstanceDeployConfig(
            instance_id=instance_id,
            scenario="self_hosted",
            ssh_host="1.2.3.4",
            ssh_port=22,
            ssh_username="root",
            ssh_auth_type="password",
            ssh_credential="ssh-secret",
            domain="crm-test.example.com",
            letsencrypt_email="ops@example.com",
            db_root_password="db-root-secret",
            admin_email="admin@example.com",
            domain_registrar="Porkbun",
        ),
    )
    yield conn, instance_id, str(db_file)
    conn.close()


def _stub_wizard(
    conn: sqlite3.Connection,
    instance_id: int | None,
    project_folder: str | None,
) -> SimpleNamespace:
    """Build a partial-wizard stub the handler can run against."""
    stub = SimpleNamespace(
        _conn=conn,
        _instance_id=instance_id,
        _master_db_path="/unused",
        _client_id=1,
        _record_generation_error="inspection failed",
    )
    stub._read_project_folder = lambda: project_folder
    stub._read_client_name = lambda: "Cleveland Business Mentors"
    return stub


def _invoke_handler(stub: SimpleNamespace) -> None:
    """Invoke the unbound wizard method with the stub as ``self``."""
    wizard_dialog.DeployWizard._on_generate_record_manually(stub)


# ── Success: handler launches the regeneration dialog ───────────────


def test_on_generate_record_manually_launches_regeneration_dialog(
    populated_db, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, instance_id, _ = populated_db
    project_folder = tmp_path / "project"
    project_folder.mkdir()

    launch_mock = MagicMock()
    monkeypatch.setattr(
        wizard_dialog, "launch_regeneration_dialog", launch_mock,
    )

    stub = _stub_wizard(conn, instance_id, str(project_folder))
    _invoke_handler(stub)

    launch_mock.assert_called_once()
    kwargs = launch_mock.call_args.kwargs
    assert kwargs["parent"] is stub
    assert kwargs["instance"].code == "CBMTEST"
    assert kwargs["instance"].id == instance_id
    assert kwargs["deploy_config"].instance_id == instance_id
    assert kwargs["project_folder"] == str(project_folder)
    assert kwargs["db_path"].endswith("client.db")
    assert kwargs["client_name"] == "Cleveland Business Mentors"


# ── Defensive guards: handler warns instead of crashing ─────────────


def test_on_generate_record_manually_warns_when_no_instance_id(
    populated_db, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, _instance_id, _ = populated_db

    launch_mock = MagicMock()
    warning_mock = MagicMock()
    monkeypatch.setattr(
        wizard_dialog, "launch_regeneration_dialog", launch_mock,
    )
    monkeypatch.setattr(
        wizard_dialog.QMessageBox, "warning", warning_mock,
    )

    stub = _stub_wizard(conn, None, str(tmp_path))
    _invoke_handler(stub)

    launch_mock.assert_not_called()
    warning_mock.assert_called_once()


def test_on_generate_record_manually_warns_when_no_deploy_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_file = tmp_path / "client.db"
    conn = run_client_migrations(str(db_file))
    instance_id = create_wizard_instance(
        conn, name="No Config", code="NOCFG", environment="test",
    )
    project_folder = tmp_path / "project"
    project_folder.mkdir()

    launch_mock = MagicMock()
    warning_mock = MagicMock()
    monkeypatch.setattr(
        wizard_dialog, "launch_regeneration_dialog", launch_mock,
    )
    monkeypatch.setattr(
        wizard_dialog.QMessageBox, "warning", warning_mock,
    )

    stub = _stub_wizard(conn, instance_id, str(project_folder))
    try:
        _invoke_handler(stub)
    finally:
        conn.close()

    launch_mock.assert_not_called()
    warning_mock.assert_called_once()


def test_on_generate_record_manually_warns_when_no_project_folder(
    populated_db, monkeypatch: pytest.MonkeyPatch,
) -> None:
    conn, instance_id, _ = populated_db

    launch_mock = MagicMock()
    warning_mock = MagicMock()
    monkeypatch.setattr(
        wizard_dialog, "launch_regeneration_dialog", launch_mock,
    )
    monkeypatch.setattr(
        wizard_dialog.QMessageBox, "warning", warning_mock,
    )

    stub = _stub_wizard(conn, instance_id, None)
    _invoke_handler(stub)

    launch_mock.assert_not_called()
    warning_mock.assert_called_once()


def test_placeholder_message_is_gone() -> None:
    """The Prompt-C-era placeholder string must not be present anymore."""
    source = Path(wizard_dialog.__file__).read_text(encoding="utf-8")
    assert "Manual regeneration is not yet wired up" not in source
