"""PI-302 — migration 0087 adds work_tasks.work_task_resolved_agent_profile.

create_all, drop the column, stamp 0086, upgrade 0087, assert the column is back;
then downgrade to 0086 and assert it is gone. The add is guarded so the migration is
a no-op on a create_all-materialised DB.
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
_DOWN = "0086_pi_051_security_rules"
_MIGRATION = "0087_pi_302_work_task_resolved_agent_profile"
_COLUMN = "work_task_resolved_agent_profile"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(f"sqlite:///{db}")).get_columns(table)}


def test_0087_adds_and_drops_resolved_agent_profile(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"ALTER TABLE work_tasks DROP COLUMN {_COLUMN}"))
    engine.dispose()
    assert _COLUMN not in _cols(db, "work_tasks")

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    assert _COLUMN in _cols(db, "work_tasks")

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _COLUMN not in _cols(db, "work_tasks")
