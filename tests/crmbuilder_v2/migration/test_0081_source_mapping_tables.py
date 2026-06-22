"""PI-255 — migration 0081 creates the seven source mapping tables + CHECKs.

Mirrors the 0060 pattern: create_all, drop the new tables, stamp 0080, upgrade
0081, assert the tables are back and the change_log / refs / membership-state
CHECKs admit the new entity types + states, then downgrade to 0080 and assert the
tables are gone.
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
_DOWN = "0080_pi_263_cost_events"
_MIGRATION = "0081_pi_255_source_mapping_tables"
_TABLES = (
    "source_mappings",
    "source_mapping_targets",
    "source_mapping_joins",
    "field_mappings",
    "field_mapping_translations",
    "value_mappings",
    "mapping_candidates",
)


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0081_creates_and_drops_tables(tmp_path: Path) -> None:
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
        # change_log + refs CHECKs admit the new entity types.
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, "
            "'source_mapping', 'SMG-001', 'insert', 'claude_session', 'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, engagement_id) "
            "VALUES ('REF-9401', 'source_mapping', 'SMG-001', 'field_mapping', "
            "'FMP-001', 'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
        ))
        # membership state CHECK admits the new states.
        c.execute(text(
            "INSERT INTO instance_memberships (engagement_id, instance_identifier, "
            "member_type, member_identifier, state, last_audited_at, created_at, "
            "updated_at) VALUES ('ENG-001', 'INST-001', 'entity', 'ENT-001', "
            "'candidate_pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP)"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert not (set(_TABLES) & set(insp2.get_table_names()))
