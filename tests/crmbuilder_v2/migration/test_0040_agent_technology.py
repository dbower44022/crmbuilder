"""PI-271 — migration 0083 adds the technology discriminator columns.

create_all, drop the two columns, stamp 0082, upgrade 0083, assert both columns
are back; then downgrade to 0082 and assert they are gone. Column-adds are guarded
so the migration is a no-op on a create_all-materialised DB.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0039_pi_273_pipeline_events"
_MIGRATION = "0040_pi_271_agent_technology"




def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db)).get_columns(table)}


def test_0083_adds_and_drops_technology_columns() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text("ALTER TABLE agent_profiles DROP COLUMN technology"))
        c.execute(text("ALTER TABLE work_tasks DROP COLUMN work_task_technology"))
    engine.dispose()
    assert "technology" not in _cols(db, "agent_profiles")

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    assert "technology" in _cols(db, "agent_profiles")
    assert "work_task_technology" in _cols(db, "work_tasks")

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "technology" not in _cols(db, "agent_profiles")
    assert "work_task_technology" not in _cols(db, "work_tasks")
