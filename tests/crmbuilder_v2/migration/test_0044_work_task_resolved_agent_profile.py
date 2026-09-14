"""PI-302 — migration 0087 adds work_tasks.work_task_resolved_agent_profile.

create_all, drop the column, stamp 0086, upgrade 0087, assert the column is back;
then downgrade to 0086 and assert it is gone. The add is guarded so the migration is
a no-op on a create_all-materialised DB.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0043_pi_051_security_rules"
_MIGRATION = "0044_pi_302_work_task_resolved_agent_profile"
_COLUMN = "work_task_resolved_agent_profile"




def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db)).get_columns(table)}


def test_0087_adds_and_drops_resolved_agent_profile() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text(f"ALTER TABLE work_tasks DROP COLUMN {_COLUMN}"))
    engine.dispose()
    assert _COLUMN not in _cols(db, "work_tasks")

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    assert _COLUMN in _cols(db, "work_tasks")

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _COLUMN not in _cols(db, "work_tasks")
