"""PI-185 — migration 0059 creates the instance_memberships join table.

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
_MIGRATION_DOWN = "0058_pi_189_dedup_template_design_records"
_MIGRATION = "0059_pi_185_instance_membership"
_TABLE = "instance_memberships"


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


def test_0059_creates_and_drops_membership_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names())
    cols = {col["name"] for col in insp.get_columns(_TABLE)}
    assert {"instance_identifier", "member_type", "member_identifier",
            "state", "override", "last_audited_at", "engagement_id"} <= cols
    ddl = eng.connect().execute(
        text("select sql from sqlite_master where name=:n"), {"n": _TABLE}
    ).fetchone()[0]
    assert "member_type" in ddl and "state" in ddl  # CHECKs present
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names())
