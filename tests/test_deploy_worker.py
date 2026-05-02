"""Tests for deploy worker's Deployment Record generation hook.

Exercises the worker's ``_persist_and_generate_record`` helper directly
as a unit test. Spinning up a real paramiko ``SSHClient`` and Qt event
loop is far heavier than the value adds for verifying the integration
seam — the helper is the actual seam between the deploy worker and the
Prompt-A generator.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.record_generator import (
    AdministratorInputs,
    DeploymentRecordValues,
)
from automation.core.deployment.ssh_deploy import SelfHostedConfig
from automation.core.deployment.wizard_logic import create_wizard_instance
from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deploy_wizard.deploy_worker import (
    SelfHostedWorker,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "deployment_record_values_cbmtest.json"
)


# ── Test fixtures ────────────────────────────────────────────────────


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
def db_path(tmp_path: Path) -> str:
    """Migrated per-client database; returns the file path."""
    db_file = tmp_path / "client.db"
    conn = run_client_migrations(str(db_file))
    create_wizard_instance(
        conn, name="CBM Test", code="CBMTEST", environment="test",
    )
    conn.close()
    return str(db_file)


@pytest.fixture()
def project_folder(tmp_path: Path) -> str:
    """A project_folder layout that the worker can write into."""
    folder = tmp_path / "project"
    folder.mkdir()
    return str(folder)


def _make_self_hosted_config() -> SelfHostedConfig:
    return SelfHostedConfig(
        ssh_host="1.2.3.4",
        ssh_port=22,
        ssh_username="root",
        ssh_credential="ssh-secret",
        ssh_auth_type="password",
        domain="crm.example.com",
        letsencrypt_email="ops@example.com",
        db_password="db-app-password",
        db_root_password="db-root-secret",
        admin_username="admin",
        admin_password="admin-secret",
        admin_email="admin@example.com",
    )


def _make_administrator_inputs() -> AdministratorInputs:
    return AdministratorInputs(
        domain_registrar="Porkbun",
        dns_provider="Porkbun",
        primary_domain="example.com",
        instance_subdomain="crm",
        droplet_id="987654321",
        backups_enabled=True,
        proton_pass_admin_entry="CBMTEST-ESPOCRM-Test Instance Admin",
        proton_pass_db_root_entry="CBMTEST-ESPOCRM-Test DB Root",
        proton_pass_hosting_entry="CBMTEST DigitalOcean Account",
    )


def _fixture_values(**overrides) -> DeploymentRecordValues:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    data.update(overrides)
    return DeploymentRecordValues(**data)


# ── Helpers to instantiate the worker without QThread.start() ────────


def _build_worker(
    db_path: str, project_folder: str, instance_id: int,
) -> SelfHostedWorker:
    """Build a worker without invoking QThread/Qt event loop machinery.

    ``QThread.__init__`` requires a QCoreApplication on some platforms
    when a parent is provided. With ``parent=None`` it is safe to
    construct without a running app, and we never call ``.start()`` —
    we exercise ``_persist_and_generate_record`` directly.
    """
    return SelfHostedWorker(
        _make_self_hosted_config(),
        administrator_inputs=_make_administrator_inputs(),
        instance_id=instance_id,
        db_path=db_path,
        project_folder=project_folder,
        parent=None,
    )


def _instance_id_for(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT id FROM Instance WHERE code = ?", ("CBMTEST",)
        ).fetchone()[0]
    finally:
        conn.close()


# ── Success path ─────────────────────────────────────────────────────


def test_generate_record_success_emits_path(
    tmp_path: Path, db_path: str, project_folder: str,
) -> None:
    """Successful generation: emits ``record_generated`` with the .docx path."""
    instance_id = _instance_id_for(db_path)
    worker = _build_worker(db_path, project_folder, instance_id)

    captured: dict[str, str] = {}
    worker.record_generated.connect(lambda p: captured.setdefault("path", p))
    worker.record_generation_failed.connect(
        lambda m: captured.setdefault("error", m)
    )

    fake_values = _fixture_values()

    with patch(
        "automation.core.deployment.record_generator."
        "inspect_server_for_record_values",
        return_value=fake_values,
    ) as mock_inspect, patch(
        "automation.core.deployment.record_generator."
        "generate_deployment_record",
        side_effect=lambda values, output: output,
    ) as mock_generate:
        ssh = MagicMock()
        worker._persist_and_generate_record(ssh)

    assert "error" not in captured
    assert captured.get("path", "").endswith(
        "PRDs/deployment/CBMTEST-Instance-Deployment-Record.docx"
    )
    expected = (
        Path(project_folder)
        / "PRDs"
        / "deployment"
        / "CBMTEST-Instance-Deployment-Record.docx"
    )
    mock_generate.assert_called_once()
    args, _ = mock_generate.call_args
    assert args[1] == expected
    mock_inspect.assert_called_once()


def test_generate_record_persists_admin_inputs_to_deploy_config(
    db_path: str, project_folder: str,
) -> None:
    """The four administrator-supplied fields land in InstanceDeployConfig."""
    instance_id = _instance_id_for(db_path)
    worker = _build_worker(db_path, project_folder, instance_id)

    with patch(
        "automation.core.deployment.record_generator."
        "inspect_server_for_record_values",
        return_value=_fixture_values(),
    ), patch(
        "automation.core.deployment.record_generator."
        "generate_deployment_record",
        side_effect=lambda values, output: output,
    ):
        worker._persist_and_generate_record(MagicMock())

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT domain_registrar, dns_provider, droplet_id, "
            "backups_enabled FROM InstanceDeployConfig "
            "WHERE instance_id = ?",
            (instance_id,),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("Porkbun", "Porkbun", "987654321", 1)


# ── Failure paths ────────────────────────────────────────────────────


def test_generate_record_failure_emits_warning(
    db_path: str, project_folder: str,
) -> None:
    """Generator failure is non-fatal: warning emitted, no path emitted."""
    instance_id = _instance_id_for(db_path)
    worker = _build_worker(db_path, project_folder, instance_id)

    captured: dict[str, str] = {}
    worker.record_generated.connect(
        lambda p: captured.setdefault("path", p)
    )
    worker.record_generation_failed.connect(
        lambda m: captured.setdefault("error", m)
    )

    with patch(
        "automation.core.deployment.record_generator."
        "inspect_server_for_record_values",
        return_value=_fixture_values(),
    ), patch(
        "automation.core.deployment.record_generator."
        "generate_deployment_record",
        side_effect=RuntimeError("python-docx broke"),
    ):
        worker._persist_and_generate_record(MagicMock())

    assert "path" not in captured
    assert "python-docx broke" in captured.get("error", "")


def test_generate_record_missing_project_folder(
    tmp_path: Path, db_path: str,
) -> None:
    """A missing project_folder is reported but does not raise."""
    instance_id = _instance_id_for(db_path)
    bogus_folder = tmp_path / "does_not_exist"
    worker = _build_worker(db_path, str(bogus_folder), instance_id)

    captured: dict[str, str] = {}
    worker.record_generation_failed.connect(
        lambda m: captured.setdefault("error", m)
    )

    with patch(
        "automation.core.deployment.record_generator."
        "inspect_server_for_record_values"
    ) as mock_inspect, patch(
        "automation.core.deployment.record_generator."
        "generate_deployment_record"
    ) as mock_generate:
        worker._persist_and_generate_record(MagicMock())

    assert "Project folder does not exist" in captured.get("error", "")
    mock_inspect.assert_not_called()
    mock_generate.assert_not_called()
