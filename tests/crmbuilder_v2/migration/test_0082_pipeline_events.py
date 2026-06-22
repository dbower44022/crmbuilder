"""PI-273 — migration 0082 creates the pipeline_events table.

Mirrors the 0080/0081 pattern: create_all, drop the new table, stamp 0081,
upgrade 0082, assert the table is back with its CHECK admitting the event kinds,
then downgrade to 0081 and assert the table is gone. A telemetry satellite, so
there are no change_log / refs CHECK rebuilds to exercise.
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
_MIGRATION = "0082_pi_273_pipeline_events"
_TABLE = "pipeline_events"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def test_0082_creates_and_drops_pipeline_events(tmp_path: Path) -> None:
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
    assert _TABLE in inspect(eng).get_table_names()
    with eng.begin() as c:
        # A valid event kind is admitted...
        c.execute(text(
            "INSERT INTO pipeline_events (engagement_id, event_kind, "
            "pipeline_event_created_at) VALUES ('ENG-001', 'agent_outcome', "
            "CURRENT_TIMESTAMP)"
        ))
        # ...and an unknown kind is rejected by the CHECK.
        try:
            c.execute(text(
                "INSERT INTO pipeline_events (engagement_id, event_kind, "
                "pipeline_event_created_at) VALUES ('ENG-001', 'bogus', "
                "CURRENT_TIMESTAMP)"
            ))
            raise AssertionError("CHECK should have rejected an unknown event_kind")
        except Exception as exc:  # noqa: BLE001
            assert "constraint" in str(exc).lower() or "check" in str(exc).lower()
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _TABLE not in inspect(create_engine(f"sqlite:///{db}")).get_table_names()
