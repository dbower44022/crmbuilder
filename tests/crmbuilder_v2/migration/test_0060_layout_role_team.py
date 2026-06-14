"""PI-193/194 — migration 0060 creates layouts/roles/teams + rebuilds CHECKs.

Mirrors the 0052 pattern: create_all, drop the three new tables, stamp 0059,
upgrade 0060, assert the tables are back and the change_log / refs / membership
CHECKs admit the new entity + member types, then downgrade to 0059.
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
_DOWN = "0059_pi_185_instance_membership"
_MIGRATION = "0060_pi_193_194_layout_role_team"
_TABLES = ("layouts", "roles", "teams")


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0060_creates_and_drops_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for t in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    engine.dispose()

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert set(_TABLES) <= set(insp.get_table_names())
    with eng.begin() as c:
        # change_log + refs + membership CHECKs admit the new types.
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, 'layout', "
            "'LAY-001', 'insert', 'claude_session', 'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, engagement_id) "
            "VALUES ('REF-9301', 'decision', 'DEC-001', 'role', 'ROL-001', "
            "'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO instance_memberships (engagement_id, instance_identifier, "
            "member_type, member_identifier, state, last_audited_at, created_at, "
            "updated_at) VALUES ('ENG-001', 'INST-001', 'team', 'TM-001', 'present', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert not (set(_TABLES) & set(insp2.get_table_names()))
