"""Tests for the InstanceDeployConfig CRUD repository."""

import sqlite3
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    delete_deploy_config,
    load_deploy_config,
    save_deploy_config,
    update_after_upgrade,
    update_version_state,
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
    db_path = tmp_path / "client.db"
    conn = run_client_migrations(str(db_path))
    yield conn
    conn.close()


def _make_instance(conn: sqlite3.Connection, code: str = "INST") -> int:
    conn.execute(
        "INSERT INTO Instance (name, code, environment) "
        "VALUES (?, ?, 'production')",
        (f"Inst {code}", code),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _build_config(
    instance_id: int,
    *,
    ssh_auth_type: str = "password",
    ssh_credential: str = "ssh-secret",
    db_root_password: str = "db-root-secret",
) -> InstanceDeployConfig:
    return InstanceDeployConfig(
        instance_id=instance_id,
        scenario="self_hosted",
        ssh_host="1.2.3.4",
        ssh_port=22,
        ssh_username="root",
        ssh_auth_type=ssh_auth_type,
        ssh_credential=ssh_credential,
        domain="crm.example.com",
        letsencrypt_email="ops@example.com",
        db_root_password=db_root_password,
        admin_email="admin@example.com",
    )


# ── Insert / load ─────────────────────────────────────────────────────


def test_load_returns_none_when_absent(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    assert load_deploy_config(db, inst_id) is None


def test_save_then_load_round_trips_values(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id)
    save_deploy_config(db, cfg)

    loaded = load_deploy_config(db, inst_id)
    assert loaded is not None
    assert loaded.ssh_host == "1.2.3.4"
    assert loaded.ssh_username == "root"
    assert loaded.domain == "crm.example.com"
    assert loaded.ssh_credential == "ssh-secret"
    assert loaded.db_root_password == "db-root-secret"
    assert loaded.admin_email == "admin@example.com"


def test_save_assigns_id(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id)
    save_deploy_config(db, cfg)
    assert cfg.id is not None


def test_save_does_not_store_plaintext_in_db(
    db: sqlite3.Connection,
) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(
        inst_id, ssh_credential="ssh-plaintext", db_root_password="db-plaintext"
    )
    save_deploy_config(db, cfg)

    row = db.execute(
        "SELECT ssh_credential_ref, db_root_password_ref "
        "FROM InstanceDeployConfig WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    ssh_ref, db_ref = row
    assert "ssh-plaintext" not in ssh_ref
    assert "db-plaintext" not in db_ref
    assert ssh_ref.startswith(secrets.REF_PREFIX)
    assert db_ref.startswith(secrets.REF_PREFIX)


# ── ssh_auth_type='key' stores path inline (not in keyring) ──────────


def test_save_with_key_auth_stores_path_inline(
    db: sqlite3.Connection,
    _memory_keyring: _MemoryBackend,
) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(
        inst_id,
        ssh_auth_type="key",
        ssh_credential="/home/doug/.ssh/id_ed25519",
    )
    save_deploy_config(db, cfg)

    row = db.execute(
        "SELECT ssh_credential_ref FROM InstanceDeployConfig "
        "WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    # Path stored verbatim, not as a keyring ref
    assert row[0] == "/home/doug/.ssh/id_ed25519"
    # Only the db_root_password should have hit the keyring
    assert len(_memory_keyring._store) == 1


def test_load_with_key_auth_returns_path(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(
        inst_id, ssh_auth_type="key", ssh_credential="/path/to/key"
    )
    save_deploy_config(db, cfg)

    loaded = load_deploy_config(db, inst_id)
    assert loaded.ssh_credential == "/path/to/key"


# ── Update path ──────────────────────────────────────────────────────


def test_resave_replaces_existing(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id, db_root_password="first")
    save_deploy_config(db, cfg)

    cfg2 = _build_config(inst_id, db_root_password="second")
    save_deploy_config(db, cfg2)

    loaded = load_deploy_config(db, inst_id)
    assert loaded.db_root_password == "second"
    rows = db.execute(
        "SELECT COUNT(*) FROM InstanceDeployConfig WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    assert rows[0] == 1


def test_resave_deletes_old_keyring_entries(
    db: sqlite3.Connection, _memory_keyring: _MemoryBackend
) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id, db_root_password="first")
    save_deploy_config(db, cfg)
    first_db_ref = cfg._db_root_password_ref

    cfg2 = _build_config(inst_id, db_root_password="second")
    save_deploy_config(db, cfg2)

    # Old reference should be gone from the keyring
    with pytest.raises(KeyError):
        secrets.get_secret(first_db_ref)


# ── Delete ───────────────────────────────────────────────────────────


def test_delete_removes_row(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    save_deploy_config(db, _build_config(inst_id))
    assert delete_deploy_config(db, inst_id) is True
    assert load_deploy_config(db, inst_id) is None


def test_delete_returns_false_when_absent(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    assert delete_deploy_config(db, inst_id) is False


def test_delete_clears_keyring_entries(
    db: sqlite3.Connection, _memory_keyring: _MemoryBackend
) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id)
    save_deploy_config(db, cfg)
    delete_deploy_config(db, inst_id)
    assert _memory_keyring._store == {}


# ── Validation ───────────────────────────────────────────────────────


def test_save_rejects_unsupported_scenario(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id)
    cfg.scenario = "cloud_hosted"
    with pytest.raises(ValueError):
        save_deploy_config(db, cfg)


def test_save_rejects_unsupported_ssh_auth_type(
    db: sqlite3.Connection,
) -> None:
    inst_id = _make_instance(db)
    cfg = _build_config(inst_id, ssh_auth_type="hmac")
    with pytest.raises(ValueError):
        save_deploy_config(db, cfg)


# ── Targeted updates ─────────────────────────────────────────────────


def test_update_version_state_persists_versions(
    db: sqlite3.Connection,
) -> None:
    inst_id = _make_instance(db)
    save_deploy_config(db, _build_config(inst_id))
    update_version_state(
        db, inst_id, current_version="8.4.0", latest_version="8.5.1"
    )

    loaded = load_deploy_config(db, inst_id)
    assert loaded.current_espocrm_version == "8.4.0"
    assert loaded.latest_espocrm_version == "8.5.1"


def test_update_version_state_partial_update(
    db: sqlite3.Connection,
) -> None:
    inst_id = _make_instance(db)
    save_deploy_config(db, _build_config(inst_id))
    update_version_state(db, inst_id, latest_version="9.0.0")

    loaded = load_deploy_config(db, inst_id)
    assert loaded.current_espocrm_version is None
    assert loaded.latest_espocrm_version == "9.0.0"


def test_update_after_upgrade_records_state(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    save_deploy_config(db, _build_config(inst_id))
    update_after_upgrade(
        db,
        inst_id,
        current_version="8.5.1",
        last_upgrade_at="2026-05-01T00:00:00Z",
        last_backup_paths=[
            "/var/backups/espocrm/20260501_000000",
            "/var/backups/espocrm/20260430_000000",
        ],
    )

    loaded = load_deploy_config(db, inst_id)
    assert loaded.current_espocrm_version == "8.5.1"
    assert loaded.last_upgrade_at == "2026-05-01T00:00:00Z"
    assert loaded.last_backup_paths == [
        "/var/backups/espocrm/20260501_000000",
        "/var/backups/espocrm/20260430_000000",
    ]


def test_last_backup_paths_round_trip_handles_empty(
    db: sqlite3.Connection,
) -> None:
    inst_id = _make_instance(db)
    save_deploy_config(db, _build_config(inst_id))
    loaded = load_deploy_config(db, inst_id)
    assert loaded.last_backup_paths == []
