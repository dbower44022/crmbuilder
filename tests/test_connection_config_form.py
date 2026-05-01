"""Tests for the backfill ConnectionConfigDialog form logic.

Exercises the pure validate_form / save_form helpers — the Qt dialog
itself wraps these and has no logic worth testing in isolation.
"""

import sqlite3
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.deploy_config_repo import load_deploy_config
from automation.core.deployment.wizard_logic import create_wizard_instance
from automation.db.migrations import run_client_migrations
from automation.ui.deployment.connection_config_dialog import (
    ConnectionForm,
    save_form,
    validate_form,
)


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
def db(tmp_path: Path) -> sqlite3.Connection:
    conn = run_client_migrations(str(tmp_path / "client.db"))
    yield conn
    conn.close()


def _make_instance(conn: sqlite3.Connection) -> int:
    return create_wizard_instance(
        conn, name="Production", code="PROD", environment="production"
    )


def _valid_form(tmp_path: Path | None = None) -> ConnectionForm:
    return ConnectionForm(
        ssh_host="1.2.3.4",
        ssh_port=22,
        ssh_username="root",
        ssh_auth_type="password",
        ssh_credential="ssh-secret",
        domain="crm.example.com",
        letsencrypt_email="ops@example.com",
        db_root_password="db-root-secret",
        admin_email="admin@example.com",
    )


# ── Validation ────────────────────────────────────────────────────────


def test_valid_form_passes() -> None:
    assert validate_form(_valid_form()) == []


def test_missing_ssh_host_fails() -> None:
    form = _valid_form()
    form.ssh_host = ""
    errors = validate_form(form)
    assert any("SSH host" in e for e in errors)


def test_invalid_port_fails() -> None:
    form = _valid_form()
    form.ssh_port = 0
    assert any("port" in e.lower() for e in validate_form(form))

    form.ssh_port = 70000
    assert any("port" in e.lower() for e in validate_form(form))


def test_invalid_auth_type_fails() -> None:
    form = _valid_form()
    form.ssh_auth_type = "hmac"
    assert any("auth type" in e.lower() for e in validate_form(form))


def test_password_auth_requires_credential() -> None:
    form = _valid_form()
    form.ssh_auth_type = "password"
    form.ssh_credential = ""
    errors = validate_form(form)
    assert any("password" in e.lower() for e in errors)


def test_key_auth_requires_credential() -> None:
    form = _valid_form()
    form.ssh_auth_type = "key"
    form.ssh_credential = ""
    errors = validate_form(form)
    assert any("key file" in e.lower() for e in errors)


def test_key_auth_requires_existing_file(tmp_path: Path) -> None:
    form = _valid_form()
    form.ssh_auth_type = "key"
    form.ssh_credential = str(tmp_path / "missing-key")
    errors = validate_form(form)
    assert any("not found" in e.lower() for e in errors)


def test_key_auth_accepts_existing_file(tmp_path: Path) -> None:
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("fake")
    form = _valid_form()
    form.ssh_auth_type = "key"
    form.ssh_credential = str(key_file)
    assert validate_form(form) == []


def test_invalid_letsencrypt_email_fails() -> None:
    form = _valid_form()
    form.letsencrypt_email = "not-an-email"
    assert any("Let's Encrypt" in e for e in validate_form(form))


def test_invalid_admin_email_fails() -> None:
    form = _valid_form()
    form.admin_email = "no-at-sign"
    assert any("Admin email" in e for e in validate_form(form))


def test_admin_email_optional() -> None:
    form = _valid_form()
    form.admin_email = ""
    assert validate_form(form) == []


def test_missing_domain_fails() -> None:
    form = _valid_form()
    form.domain = ""
    assert any("Domain" in e for e in validate_form(form))


def test_missing_db_root_password_fails() -> None:
    form = _valid_form()
    form.db_root_password = ""
    assert any("MariaDB" in e for e in validate_form(form))


# ── Save ─────────────────────────────────────────────────────────────


def test_save_form_persists_config(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    saved = save_form(db, inst_id, _valid_form())

    assert saved.id is not None
    assert saved.instance_id == inst_id
    assert saved.scenario == "self_hosted"

    loaded = load_deploy_config(db, inst_id)
    assert loaded is not None
    assert loaded.ssh_host == "1.2.3.4"


def test_save_form_strips_whitespace(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    form = _valid_form()
    form.ssh_host = "  1.2.3.4  "
    form.domain = "  crm.example.com  "
    save_form(db, inst_id, form)

    loaded = load_deploy_config(db, inst_id)
    assert loaded.ssh_host == "1.2.3.4"
    assert loaded.domain == "crm.example.com"


def test_save_form_rejects_invalid(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    form = _valid_form()
    form.ssh_host = ""
    with pytest.raises(ValueError):
        save_form(db, inst_id, form)


def test_save_form_admin_email_optional(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    form = _valid_form()
    form.admin_email = ""
    save_form(db, inst_id, form)

    loaded = load_deploy_config(db, inst_id)
    assert loaded.admin_email is None
