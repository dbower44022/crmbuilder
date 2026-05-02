"""Tests for the InstanceDeployConfig _client_v11 and _client_v12 migrations.

Covers idempotency, additivity over an older schema, and the no-op
behavior on databases that pre-date the InstanceDeployConfig table.
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
def v10_db(tmp_path: Path) -> sqlite3.Connection:
    """Open a database, run all migrations, then drop v11/v12 columns.

    Simulates a database that was last migrated when the schema was at
    v10 — i.e. a DB created before the deployment-record-I prompt
    landed. v11 and v12 should add their columns when re-run.
    """
    db_path = tmp_path / "client.db"
    conn = run_client_migrations(str(db_path))
    # Rebuild without the v11/v12 columns by recreating the table from
    # the current row (no rows expected in a fresh test DB).
    conn.execute(
        "CREATE TABLE InstanceDeployConfig_pre_v11 ("
        "    id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "    instance_id INTEGER NOT NULL UNIQUE,"
        "    scenario TEXT NOT NULL,"
        "    ssh_host TEXT NOT NULL,"
        "    ssh_port INTEGER NOT NULL DEFAULT 22,"
        "    ssh_username TEXT NOT NULL,"
        "    ssh_auth_type TEXT NOT NULL,"
        "    ssh_credential_ref TEXT NOT NULL,"
        "    domain TEXT NOT NULL,"
        "    letsencrypt_email TEXT NOT NULL,"
        "    db_root_password_ref TEXT NOT NULL,"
        "    admin_email TEXT,"
        "    current_espocrm_version TEXT,"
        "    latest_espocrm_version TEXT,"
        "    last_upgrade_at TIMESTAMP,"
        "    last_backup_paths TEXT,"
        "    cert_expiry_date TEXT,"
        "    domain_registrar TEXT,"
        "    dns_provider TEXT,"
        "    droplet_id TEXT,"
        "    backups_enabled INTEGER,"
        "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )
    conn.execute("DROP TABLE InstanceDeployConfig")
    conn.execute(
        "ALTER TABLE InstanceDeployConfig_pre_v11 RENAME TO InstanceDeployConfig"
    )
    conn.commit()
    yield conn
    conn.close()


# ── _client_v11 ──────────────────────────────────────────────────────


def test_client_v11_adds_proton_pass_columns(v10_db: sqlite3.Connection) -> None:
    cols_before = _col_names(v10_db, "InstanceDeployConfig")
    assert "proton_pass_admin_entry" not in cols_before
    assert "proton_pass_db_root_entry" not in cols_before
    assert "proton_pass_hosting_entry" not in cols_before

    v11_fn = dict(CLIENT_MIGRATIONS)[11]
    _apply_migration(v10_db, 11, v11_fn)

    cols_after = _col_names(v10_db, "InstanceDeployConfig")
    assert "proton_pass_admin_entry" in cols_after
    assert "proton_pass_db_root_entry" in cols_after
    assert "proton_pass_hosting_entry" in cols_after


def test_client_v11_idempotent(v10_db: sqlite3.Connection) -> None:
    v11_fn = dict(CLIENT_MIGRATIONS)[11]
    v11_fn(v10_db)
    v10_db.commit()
    v11_fn(v10_db)  # second pass must not error
    v10_db.commit()
    cols = _col_names(v10_db, "InstanceDeployConfig")
    assert "proton_pass_admin_entry" in cols


def test_client_v11_skips_when_table_missing(tmp_path: Path) -> None:
    """v11 is a no-op on databases that pre-date InstanceDeployConfig."""
    conn = sqlite3.connect(str(tmp_path / "pre_v9.db"))
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER NOT NULL, "
        "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )

    v11_fn = dict(CLIENT_MIGRATIONS)[11]
    v11_fn(conn)  # must not raise
    assert not _table_exists(conn, "InstanceDeployConfig")
    conn.close()


# ── _client_v12 ──────────────────────────────────────────────────────


def test_client_v12_adds_last_record_version(v10_db: sqlite3.Connection) -> None:
    cols_before = _col_names(v10_db, "InstanceDeployConfig")
    assert "last_record_version" not in cols_before

    # v11 must run before v12 for our v10_db fixture
    v11_fn = dict(CLIENT_MIGRATIONS)[11]
    _apply_migration(v10_db, 11, v11_fn)
    v12_fn = dict(CLIENT_MIGRATIONS)[12]
    _apply_migration(v10_db, 12, v12_fn)

    cols_after = _col_names(v10_db, "InstanceDeployConfig")
    assert "last_record_version" in cols_after


def test_client_v12_idempotent(v10_db: sqlite3.Connection) -> None:
    v11_fn = dict(CLIENT_MIGRATIONS)[11]
    v12_fn = dict(CLIENT_MIGRATIONS)[12]
    v11_fn(v10_db)
    v12_fn(v10_db)
    v10_db.commit()
    v12_fn(v10_db)
    v10_db.commit()
    cols = _col_names(v10_db, "InstanceDeployConfig")
    assert "last_record_version" in cols


def test_client_v12_skips_when_table_missing(tmp_path: Path) -> None:
    conn = sqlite3.connect(str(tmp_path / "pre_v9.db"))
    conn.execute(
        "CREATE TABLE schema_version (version INTEGER NOT NULL, "
        "applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )

    v12_fn = dict(CLIENT_MIGRATIONS)[12]
    v12_fn(conn)  # must not raise
    assert not _table_exists(conn, "InstanceDeployConfig")
    conn.close()


# ── Migration registration ───────────────────────────────────────────


def test_v11_and_v12_in_migration_list() -> None:
    versions = [v for v, _ in CLIENT_MIGRATIONS]
    assert 11 in versions
    assert 12 in versions


def test_schema_version_recorded_through_v12(tmp_path: Path) -> None:
    conn = run_client_migrations(str(tmp_path / "fresh.db"))
    rows = conn.execute(
        "SELECT version FROM schema_version ORDER BY version"
    ).fetchall()
    versions = {row[0] for row in rows}
    assert 11 in versions
    assert 12 in versions
    conn.close()
