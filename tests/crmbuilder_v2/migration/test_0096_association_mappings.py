"""PI-255 — migration 0096 creates the association_mappings table + CHECKs.

Mirrors the 0081 pattern: create_all, drop the new table, stamp 0095, upgrade
0096, assert the table is back and the change_log / refs CHECKs admit the new
``association_mapping`` entity type, then downgrade to 0095 and assert it is gone.
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
_DOWN = "0095_pi_255_drop_membership_candidate_states"
_MIGRATION = "0096_pi_255_association_mappings"
_TABLE = "association_mappings"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0096_creates_and_drops_table(tmp_path: Path) -> None:
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
        # change_log + refs CHECKs admit the new entity type.
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, "
            "'association_mapping', 'AMP-001', 'insert', 'claude_session', "
            "'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, engagement_id) "
            "VALUES ('REF-9402', 'association_mapping', 'AMP-001', 'association', "
            "'ASC-001', 'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _TABLE not in set(
        inspect(create_engine(f"sqlite:///{db}")).get_table_names()
    )
