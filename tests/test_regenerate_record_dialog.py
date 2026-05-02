"""Tests for the manual Deployment Record regeneration dialog.

Covers the pure helpers (path resolution, Proton Pass entry templating)
and Qt-dependent behavior (form prefilling, button enable/disable).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

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
from automation.ui.deployment.deployment_logic import InstanceDetail

pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY", "") == ""
    and os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Qt dialog tests require a display or QT_QPA_PLATFORM=offscreen",
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
def db(tmp_path: Path):
    conn = run_client_migrations(str(tmp_path / "client.db"))
    yield conn, str(tmp_path / "client.db")
    conn.close()


def _make_instance_detail(instance_id: int = 1) -> InstanceDetail:
    return InstanceDetail(
        id=instance_id,
        name="CBM Test",
        code="CBMTEST",
        environment="test",
        url="https://crm-test.example.com/",
        username="admin",
        password="adminpw",
        description=None,
        is_default=False,
        created_at="2026-04-01T00:00:00+00:00",
        updated_at="2026-04-01T00:00:00+00:00",
    )


def _make_deploy_config(
    db_conn: sqlite3.Connection,
    instance_id: int,
    *,
    domain_registrar: str | None = None,
) -> InstanceDeployConfig:
    cfg = InstanceDeployConfig(
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
        domain_registrar=domain_registrar,
    )
    return save_deploy_config(db_conn, cfg)


# ── Path resolution & Proton Pass templating (pure) ─────────────────


def test_overwrite_path_is_canonical(tmp_path):
    from automation.ui.deployment.regenerate_record_dialog import (
        resolve_output_path,
    )

    path = resolve_output_path(tmp_path, "CBMTEST", versioned=False)
    assert path.name == "CBMTEST-Instance-Deployment-Record.docx"
    assert path.parent == tmp_path / "PRDs" / "deployment"
    assert path.parent.is_dir()


def test_versioned_path_has_timestamp_suffix(tmp_path):
    from automation.ui.deployment.regenerate_record_dialog import (
        resolve_output_path,
    )

    path = resolve_output_path(tmp_path, "CBMTEST", versioned=True)
    name = path.name
    assert name.startswith("CBMTEST-Instance-Deployment-Record-")
    assert name.endswith(".docx")
    middle = name[len("CBMTEST-Instance-Deployment-Record-"):-len(".docx")]
    parts = middle.split("-")
    assert len(parts) == 4
    year, month, day, hms = parts
    assert year.isdigit() and len(year) == 4
    assert month.isdigit() and len(month) == 2
    assert day.isdigit() and len(day) == 2
    assert hms.isdigit() and len(hms) == 6


def test_default_proton_pass_entry_format():
    from automation.ui.deployment.regenerate_record_dialog import (
        default_proton_pass_entry,
    )

    assert default_proton_pass_entry("CBMTEST", "test", "Instance Admin") == (
        "CBMTEST-ESPOCRM-Test Instance Admin"
    )
    assert default_proton_pass_entry(
        "CBMTEST", "production", "DigitalOcean Account",
    ) == "CBMTEST-ESPOCRM-Production DigitalOcean Account"
    assert default_proton_pass_entry("FOO", "", "DB Root") == (
        "FOO-ESPOCRM DB Root"
    )


# ── Dialog Qt behavior ──────────────────────────────────────────────


def test_dialog_disables_generate_with_no_inputs(db, tmp_path):
    from automation.ui.deployment.regenerate_record_dialog import (
        RegenerateRecordDialog,
    )

    conn, db_path = db
    instance_id = create_wizard_instance(
        conn, name="CBM Test", code="CBMTEST", environment="test",
    )
    cfg = _make_deploy_config(conn, instance_id)
    detail = _make_instance_detail(instance_id)

    dialog = RegenerateRecordDialog(
        instance=detail,
        deploy_config=cfg,
        project_folder=str(tmp_path),
        db_path=db_path,
    )
    try:
        # Default state has all required fields populated → enabled.
        assert dialog._generate_btn.isEnabled()

        # Clearing registrar disables the button.
        dialog._registrar_edit.setText("")
        assert not dialog._generate_btn.isEnabled()

        # Restoring re-enables.
        dialog._registrar_edit.setText("Porkbun")
        assert dialog._generate_btn.isEnabled()
    finally:
        dialog.deleteLater()


def test_dialog_prefills_from_deploy_config(db, tmp_path):
    from automation.ui.deployment.regenerate_record_dialog import (
        RegenerateRecordDialog,
    )

    conn, db_path = db
    instance_id = create_wizard_instance(
        conn, name="CBM Test", code="CBMTEST", environment="test",
    )
    cfg = _make_deploy_config(conn, instance_id, domain_registrar="Cloudflare")
    detail = _make_instance_detail(instance_id)

    dialog = RegenerateRecordDialog(
        instance=detail,
        deploy_config=cfg,
        project_folder=str(tmp_path),
        db_path=db_path,
    )
    try:
        assert dialog._registrar_edit.text() == "Cloudflare"
        # Proton Pass defaults templated from instance code + environment.
        assert dialog._proton_admin_edit.text() == (
            "CBMTEST-ESPOCRM-Test Instance Admin"
        )
        assert dialog._proton_db_root_edit.text() == (
            "CBMTEST-ESPOCRM-Test DB Root"
        )
        assert dialog._proton_hosting_edit.text() == (
            "CBMTEST-ESPOCRM-Test DigitalOcean Account"
        )
    finally:
        dialog.deleteLater()
