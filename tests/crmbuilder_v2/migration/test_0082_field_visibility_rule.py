"""PI-051 — migration 0082 creates field_visibility_rules + rebuilds CHECKs.

Mirrors the 0081 pattern: create_all, drop the new table, stamp 0081, upgrade
0082, assert the table is back and the change_log / refs CHECKs admit the new
``field_visibility_rule`` entity type, then downgrade to 0081 and assert the
table is gone.
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
_DOWN = "0081_pi_255_source_mapping_tables"
_MIGRATION = "0082_pi_051_field_visibility_rule"
_TABLE = "field_visibility_rules"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0082_creates_and_drops_table(tmp_path: Path) -> None:
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
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names())
    with eng.begin() as c:
        # The new table accepts a minimal row.
        c.execute(text(
            "INSERT INTO field_visibility_rules "
            "(field_visibility_rule_identifier, field_visibility_rule_visible, "
            "field_visibility_rule_role, field_visibility_rule_target_field, "
            "field_visibility_rule_deployment_status, "
            "field_visibility_rule_created_at, field_visibility_rule_updated_at, "
            "engagement_id) VALUES ('FVR-001', 1, 'ROL-001', 'FLD-001', "
            "'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'ENG-001')"
        ))
        # change_log + refs CHECKs admit the new entity type.
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, "
            "'field_visibility_rule', 'FVR-001', 'insert', 'claude_session', "
            "'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, engagement_id) "
            "VALUES ('REF-9501', 'decision', 'DEC-001', 'field_visibility_rule', "
            "'FVR-001', 'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names())
