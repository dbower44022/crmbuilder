"""PI-509 — ``solution_design_0002_drop_services`` drops ``services`` and its
downgrade recreates it from the frozen definition.

Head shape via create_all (no ``services`` table any more), stamp every head,
downgrade the ``solution_design`` branch one revision (the table comes back and
accepts a row shaped as the retired model was), then ``upgrade heads`` (it is
gone again). Other branches are untouched throughout.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    all_heads,
    fresh_db,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_TABLE = "services"
_FORK = "solution_design_0001_branch"


def _tables(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_drop_and_recreate_services() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _TABLE not in _tables(db), "the model is gone, create_all must not build it"
    stamped = stamp_heads(db)
    assert stamped.returncode == 0, stamped.stderr

    down = _alembic(["downgrade", f"solution_design@{_FORK}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _TABLE in _tables(db), "downgrade must recreate services"
    eng = create_engine(db)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO services (engagement_id, service_identifier, service_name, "
                "service_purpose, service_status, service_created_at, service_updated_at) "
                "VALUES ('ENG-001', 'SVC-001', 'Document Storage', 'Store documents.', "
                "'confirmed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        c.execute(text("DELETE FROM services"))
    eng.dispose()

    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _TABLE not in _tables(db), "upgrade heads must drop services"
    current = _alembic(["current"], db)
    stamped_now = {ln.split()[0] for ln in current.stdout.splitlines() if ln and not ln.startswith("INFO")}
    assert stamped_now == set(all_heads())
