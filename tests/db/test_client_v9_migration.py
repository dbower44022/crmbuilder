"""Tests for the InstanceDeployConfig table and _client_v9 migration.

Covers schema shape, CHECK constraints, FK behavior (ON DELETE
CASCADE, UNIQUE on instance_id), and idempotent re-application of
the migration.
"""

import sqlite3
from pathlib import Path

import pytest

from automation.db.migrations import (
    CLIENT_MIGRATIONS,
    _apply_migration,
    run_client_migrations,
)


def _col_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


@pytest.fixture()
def db(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "client.db"
    conn = run_client_migrations(str(db_path))
    yield conn
    conn.close()


def _make_instance(conn: sqlite3.Connection, code: str = "INST") -> int:
    """Insert an Instance row and return its id."""
    conn.execute(
        "INSERT INTO Instance (name, code, environment) "
        "VALUES (?, ?, 'production')",
        (f"Inst {code}", code),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _insert_deploy_config(
    conn: sqlite3.Connection,
    instance_id: int,
    *,
    scenario: str = "self_hosted",
    ssh_auth_type: str = "key",
) -> None:
    conn.execute(
        "INSERT INTO InstanceDeployConfig ("
        "    instance_id, scenario, ssh_host, ssh_port, ssh_username, "
        "    ssh_auth_type, ssh_credential_ref, domain, "
        "    letsencrypt_email, db_root_password_ref"
        ") VALUES (?, ?, '1.2.3.4', 22, 'root', ?, "
        "'crmbuilder:abc', 'crm.example.com', 'a@b.com', "
        "'crmbuilder:def')",
        (instance_id, scenario, ssh_auth_type),
    )


# ── Table shape ───────────────────────────────────────────────────────


def test_table_exists(db: sqlite3.Connection) -> None:
    assert _table_exists(db, "InstanceDeployConfig")


def test_columns(db: sqlite3.Connection) -> None:
    expected = {
        "id", "instance_id", "scenario",
        "ssh_host", "ssh_port", "ssh_username",
        "ssh_auth_type", "ssh_credential_ref",
        "domain", "letsencrypt_email", "db_root_password_ref",
        "admin_email",
        "current_espocrm_version", "latest_espocrm_version",
        "last_upgrade_at", "last_backup_paths", "cert_expiry_date",
        "created_at", "updated_at",
    }
    assert _col_names(db, "InstanceDeployConfig") == expected


# ── CHECK constraints ────────────────────────────────────────────────


def test_scenario_accepts_self_hosted(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    _insert_deploy_config(db, inst_id, scenario="self_hosted")
    db.commit()


def test_scenario_rejects_cloud_hosted(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_deploy_config(db, inst_id, scenario="cloud_hosted")


def test_scenario_rejects_bring_your_own(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_deploy_config(db, inst_id, scenario="bring_your_own")


def test_ssh_auth_type_accepts_key(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    _insert_deploy_config(db, inst_id, ssh_auth_type="key")
    db.commit()


def test_ssh_auth_type_accepts_password(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    _insert_deploy_config(db, inst_id, ssh_auth_type="password")
    db.commit()


def test_ssh_auth_type_rejects_invalid(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    with pytest.raises(sqlite3.IntegrityError):
        _insert_deploy_config(db, inst_id, ssh_auth_type="hmac")


# ── FK and uniqueness ────────────────────────────────────────────────


def test_unique_instance_id(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    _insert_deploy_config(db, inst_id)
    db.commit()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_deploy_config(db, inst_id)


def test_fk_rejects_unknown_instance(db: sqlite3.Connection) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        _insert_deploy_config(db, instance_id=999)


def test_on_delete_cascade(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    _insert_deploy_config(db, inst_id)
    db.commit()
    db.execute("DELETE FROM Instance WHERE id = ?", (inst_id,))
    db.commit()
    row = db.execute(
        "SELECT 1 FROM InstanceDeployConfig WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()
    assert row is None


# ── Defaults ──────────────────────────────────────────────────────────


def test_ssh_port_defaults_to_22(db: sqlite3.Connection) -> None:
    inst_id = _make_instance(db)
    db.execute(
        "INSERT INTO InstanceDeployConfig ("
        "    instance_id, scenario, ssh_host, ssh_username, "
        "    ssh_auth_type, ssh_credential_ref, domain, "
        "    letsencrypt_email, db_root_password_ref"
        ") VALUES (?, 'self_hosted', '1.2.3.4', 'root', 'key', "
        "'crmbuilder:abc', 'crm.example.com', 'a@b.com', "
        "'crmbuilder:def')",
        (inst_id,),
    )
    db.commit()
    port = db.execute(
        "SELECT ssh_port FROM InstanceDeployConfig WHERE instance_id = ?",
        (inst_id,),
    ).fetchone()[0]
    assert port == 22


# ── Migration version ────────────────────────────────────────────────


def test_v9_in_migration_list(db: sqlite3.Connection) -> None:
    versions = [v for v, _ in CLIENT_MIGRATIONS]
    assert 9 in versions


def test_schema_version_recorded(db: sqlite3.Connection) -> None:
    rows = db.execute(
        "SELECT version FROM schema_version ORDER BY version"
    ).fetchall()
    versions = {row[0] for row in rows}
    assert 9 in versions


# ── Migration idempotency: applying v9 to a v8 DB ────────────────────


def test_v9_creates_table_when_missing(tmp_path: Path) -> None:
    """Simulate a pre-v9 database (table missing) and verify v9 creates it.

    A real v8 database can be in either state — fresh databases created
    via _client_v1 already include the table because it's in
    ALL_CLIENT_TABLES, but databases created before v9 was added will
    not. v9 must work for the latter case.
    """
    db_path = tmp_path / "pre_v9.db"
    conn = run_client_migrations(str(db_path))

    # Simulate a database that pre-dates v9 by dropping the table.
    conn.execute("DROP TABLE InstanceDeployConfig")
    conn.commit()
    assert not _table_exists(conn, "InstanceDeployConfig")

    v9_fn = dict(CLIENT_MIGRATIONS)[9]
    _apply_migration(conn, 9, v9_fn)
    assert _table_exists(conn, "InstanceDeployConfig")
    conn.close()


def test_v9_skips_when_instance_table_missing(tmp_path: Path) -> None:
    """v9 is a no-op on databases that pre-date the Instance table."""
    db_path = tmp_path / "pre_v3.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER NOT NULL, "
        "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )

    v9_fn = dict(CLIENT_MIGRATIONS)[9]
    v9_fn(conn)  # should not raise
    conn.commit()
    assert not _table_exists(conn, "InstanceDeployConfig")
    conn.close()


def test_v9_migration_idempotent(tmp_path: Path) -> None:
    """Applying v9 twice does not error."""
    db_path = tmp_path / "v9.db"
    conn = run_client_migrations(str(db_path))

    v9_fn = dict(CLIENT_MIGRATIONS)[9]
    v9_fn(conn)
    conn.commit()
    assert _table_exists(conn, "InstanceDeployConfig")
    conn.close()
