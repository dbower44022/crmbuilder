"""PI-301 — migration 0085 adds agent_profiles.capability_description.

create_all, drop the column, stamp 0084, upgrade 0085, assert the column is back;
then downgrade to 0084 and assert it is gone. The add is guarded so the migration is
a no-op on a create_all-materialised DB.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0041_pi_297_entity_tracks_activities"
_MIGRATION = "0042_pi_301_agent_capability_description"




def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db)).get_columns(table)}


def test_0085_adds_and_drops_capability_description() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text("ALTER TABLE agent_profiles DROP COLUMN capability_description"))
    engine.dispose()
    assert "capability_description" not in _cols(db, "agent_profiles")

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    assert "capability_description" in _cols(db, "agent_profiles")

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "capability_description" not in _cols(db, "agent_profiles")
