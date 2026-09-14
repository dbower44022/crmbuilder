"""Migration 0084 (REQ-337 / PI-297) — entities.entity_tracks_activities.

Mirrors the test_0055 column-add round-trip: create_all (column present from the
ORM), stamp at 0084, downgrade to 0083 (drops the column), assert the pre-state,
then upgrade back to 0084 (the real add path) and assert the column is present.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_PREV = "0040_pi_271_agent_technology"
_MIGRATION_THIS = "0041_pi_297_entity_tracks_activities"
_NEW_COLUMN = "entity_tracks_activities"




def _cols(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(db))
    return {c["name"] for c in insp.get_columns(table)}


def test_0084_column_round_trip() -> None:
    db = fresh_db()
    engine = create_engine(db)
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
