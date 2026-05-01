"""Tests for persist_deploy_config_from_wizard.

Covers the success-path hook that saves InstanceDeployConfig from a
SelfHostedConfig immediately after a successful deploy.
"""

import sqlite3
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.deploy_config_repo import load_deploy_config
from automation.core.deployment.ssh_deploy import SelfHostedConfig
from automation.core.deployment.wizard_logic import (
    create_wizard_instance,
    persist_deploy_config_from_wizard,
)
from automation.db.migrations import run_client_migrations


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


def _make_self_hosted_config(**overrides) -> SelfHostedConfig:
    defaults = {
        "ssh_host": "1.2.3.4",
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_credential": "ssh-secret",
        "ssh_auth_type": "password",
        "domain": "crm.example.com",
        "letsencrypt_email": "ops@example.com",
        "db_password": "db-app-password",
        "db_root_password": "db-root-secret",
        "admin_username": "admin",
        "admin_password": "admin-secret",
        "admin_email": "admin@example.com",
    }
    defaults.update(overrides)
    return SelfHostedConfig(**defaults)


def _make_instance(conn: sqlite3.Connection) -> int:
    return create_wizard_instance(
        conn, name="Production", code="PROD", environment="production"
    )


# ── Persistence on success ────────────────────────────────────────────


def test_persist_creates_row(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _make_self_hosted_config()

    ok = persist_deploy_config_from_wizard(db, inst_id, cfg)
    assert ok is True

    loaded = load_deploy_config(db, inst_id)
    assert loaded is not None
    assert loaded.ssh_host == "1.2.3.4"
    assert loaded.domain == "crm.example.com"
    assert loaded.ssh_credential == "ssh-secret"
    assert loaded.db_root_password == "db-root-secret"
    assert loaded.admin_email == "admin@example.com"


def test_persist_does_not_store_secrets_in_db(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    persist_deploy_config_from_wizard(
        db, inst_id, _make_self_hosted_config(db_root_password="leaky")
    )

    raw = db.execute(
        "SELECT db_root_password_ref FROM InstanceDeployConfig "
        "WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    assert "leaky" not in raw[0]
    assert raw[0].startswith(secrets.REF_PREFIX)


def test_persist_routes_password_through_keyring(
    db: sqlite3.Connection, _memory_keyring: _MemoryBackend
) -> None:
    inst_id = _make_instance(db)
    persist_deploy_config_from_wizard(
        db,
        inst_id,
        _make_self_hosted_config(
            ssh_auth_type="password",
            ssh_credential="ssh-pass",
            db_root_password="root-pass",
        ),
    )

    stored_values = set(_memory_keyring._store.values())
    assert "ssh-pass" in stored_values
    assert "root-pass" in stored_values


def test_persist_with_key_auth_keeps_path_inline(
    db: sqlite3.Connection,
    tmp_path: Path,
    _memory_keyring: _MemoryBackend,
) -> None:
    key_file = tmp_path / "id_ed25519"
    key_file.write_text("fake-key-content")
    inst_id = _make_instance(db)

    persist_deploy_config_from_wizard(
        db,
        inst_id,
        _make_self_hosted_config(
            ssh_auth_type="key", ssh_credential=str(key_file)
        ),
    )

    raw = db.execute(
        "SELECT ssh_credential_ref FROM InstanceDeployConfig "
        "WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    assert raw[0] == str(key_file)
    # Only the db_root_password should have hit the keyring
    assert len(_memory_keyring._store) == 1


def test_persist_is_idempotent_on_re_run(db: sqlite3.Connection) -> None:
    """Re-running persist for the same instance updates rather than failing."""
    inst_id = _make_instance(db)
    persist_deploy_config_from_wizard(
        db, inst_id, _make_self_hosted_config(db_root_password="first")
    )
    persist_deploy_config_from_wizard(
        db, inst_id, _make_self_hosted_config(db_root_password="second")
    )

    loaded = load_deploy_config(db, inst_id)
    assert loaded.db_root_password == "second"

    rows = db.execute(
        "SELECT COUNT(*) FROM InstanceDeployConfig WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    assert rows[0] == 1


# ── Failure tolerance ────────────────────────────────────────────────


def test_persist_returns_false_on_keyring_failure(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    inst_id = _make_instance(db)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("keyring locked")

    monkeypatch.setattr(secrets, "put_secret", _raise)

    ok = persist_deploy_config_from_wizard(
        db, inst_id, _make_self_hosted_config()
    )
    assert ok is False
    assert load_deploy_config(db, inst_id) is None


def test_persist_does_not_propagate_exception(
    db: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure to persist must never abort the deploy itself."""
    inst_id = _make_instance(db)

    def _raise(*_args, **_kwargs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(
        "automation.core.deployment.deploy_config_repo.save_deploy_config",
        _raise,
    )

    # Should not raise — caller is the deploy success path
    persist_deploy_config_from_wizard(
        db, inst_id, _make_self_hosted_config()
    )
