"""PI-579 — ``operate_0005_prj128_migration_run`` is a data-only revision: on
a store that is not the one the mapping describes it records itself as run
and changes nothing; its downgrade refuses once deployments exist under
Cleveland's application and passes otherwise."""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    plain_url,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_PREVIOUS = "operate_0004_deployment_purpose"


def _count(db: str, table: str) -> int:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            return c.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    finally:
        eng.dispose()


def test_fresh_store_passes_through_and_downgrade_is_guarded() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert stamp_heads(db).returncode == 0
    down = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert "nothing to do" in (up.stdout + up.stderr)
    assert _count(db, "deployments") == 0 and _count(db, "clients") == 0
    assert "deployments" in set(inspect(create_engine(plain_url(db))).get_table_names())
    # Downgrade passes while no Cleveland deployment exists ...
    down2 = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down2.returncode == 0
    assert _alembic(["upgrade", "heads"], db).returncode == 0
