"""Migration 0084 (REQ-337 / PI-297) — entities.entity_tracks_activities.

Mirrors the test_0055 column-add round-trip: create_all (column present from the
ORM), stamp at 0084, downgrade to 0083 (drops the column), assert the pre-state,
then upgrade back to 0084 (the real add path) and assert the column is present.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_PREV = "0083_pi_271_agent_technology"
_MIGRATION_THIS = "0084_pi_297_entity_tracks_activities"
_NEW_COLUMN = "entity_tracks_activities"


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


def _cols(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_columns(table)}


def test_0084_column_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_THIS], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_PREV], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: the new column is gone; the sibling stream flag survives.
    assert _NEW_COLUMN not in _cols(db, "entities")
    assert "entity_track_activity" in _cols(db, "entities")

    # The real add path.
    up = _alembic(["upgrade", _MIGRATION_THIS], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_COLUMN in _cols(db, "entities")
