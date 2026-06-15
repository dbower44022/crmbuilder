"""PI-195 — migration 0061 creates filtered_tabs + rebuilds CHECKs.

create_all, drop filtered_tabs, stamp 0060, upgrade 0061, assert the table is
back and the change_log / refs / membership CHECKs admit the new
``filtered_tab`` entity + member types, then downgrade to 0060.
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
_DOWN = "0060_pi_193_194_layout_role_team"
_MIGRATION = "0061_pi_195_filtered_tab"
_TABLE = "filtered_tabs"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0061_creates_and_drops_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    assert _TABLE in set(inspect(eng).get_table_names())
    with eng.begin() as c:
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, "
            "'filtered_tab', 'FTB-001', 'insert', 'claude_session', 'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO instance_memberships (engagement_id, instance_identifier, "
            "member_type, member_identifier, state, last_audited_at, created_at, "
            "updated_at) VALUES ('ENG-001', 'INST-001', 'filtered_tab', 'FTB-001', "
            "'present', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _TABLE not in set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
