"""PI-419 — migration 0116 creates deploy_runs + provider_credentials and widens instance_deploy_configs.

Mirrors the 0054 pattern but simpler: instance_memberships is a lightweight
child table (no entity-type / relationship CHECK rebuilds), so the test asserts
the table is created with its member_type/state CHECKs and dropped on downgrade.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_DOWN = "0115_pi_414_membership_vocabulary_version"
_MIGRATION = "0116_pi_419_deploy_runs"
_TABLE = "deploy_runs"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


_NEW_CONFIG_COLUMNS = {
    "db_password_ref", "admin_username", "admin_password_ref", "droplet_ip",
    "droplet_region", "droplet_size", "dns_record_id",
    "last_deploy_run_identifier",
}


def _fresh_db_one_behind(db: Path) -> None:
    """Head schema minus this migration's delta, stamped one revision behind."""
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text("DROP TABLE IF EXISTS deploy_runs"))
        c.execute(text("DROP TABLE IF EXISTS provider_credentials"))
        for col in sorted(_NEW_CONFIG_COLUMNS):
            c.execute(text(f"ALTER TABLE instance_deploy_configs DROP COLUMN {col}"))
    engine.dispose()
    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"


def test_0116_creates_tables_and_columns_then_downgrades(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    _fresh_db_one_behind(db)
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    tables = set(insp.get_table_names())
    assert {"deploy_runs", "provider_credentials"} <= tables
    run_cols = {c["name"] for c in insp.get_columns("deploy_runs")}
    assert {"deploy_run_identifier", "deploy_run_status", "deploy_run_phase",
            "deploy_run_state", "deploy_run_log", "deploy_run_worker_id",
            "deploy_run_heartbeat_at", "engagement_id"} <= run_cols
    cfg_cols = {c["name"] for c in insp.get_columns("instance_deploy_configs")}
    assert _NEW_CONFIG_COLUMNS <= cfg_cols
    ddl = eng.connect().execute(
        text("select sql from sqlite_master where name='deploy_runs'")
    ).fetchone()[0]
    assert "deploy_run_status" in ddl and "deploy_run_phase" in ddl  # CHECKs
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert "deploy_runs" not in set(insp.get_table_names())
    assert "provider_credentials" not in set(insp.get_table_names())
    cfg_cols = {c["name"] for c in insp.get_columns("instance_deploy_configs")}
    assert not (_NEW_CONFIG_COLUMNS & cfg_cols)


def test_0116_is_a_no_op_on_a_head_schema(tmp_path: Path) -> None:
    """The bootstrap path (create_all, stamp one behind, upgrade) must not fail."""
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, stamp.stderr
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
