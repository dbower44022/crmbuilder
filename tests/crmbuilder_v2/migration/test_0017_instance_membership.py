"""PI-185 — migration 0059 creates the instance_memberships join table.

Mirrors the 0054 pattern but simpler: instance_memberships is a lightweight
child table (no entity-type / relationship CHECK rebuilds), so the test asserts
the table is created with its member_type/state CHECKs and dropped on downgrade.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_DOWN = "0016_pi_186_instance_entity"
_MIGRATION = "0017_pi_185_instance_membership"
_TABLE = "instance_memberships"




def test_0059_creates_and_drops_membership_table() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(db)
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names())
    cols = {col["name"] for col in insp.get_columns(_TABLE)}
    assert {"instance_identifier", "member_type", "member_identifier",
            "state", "override", "last_audited_at", "engagement_id"} <= cols
    checks = " ".join(c["sqltext"] for c in inspect(eng).get_check_constraints(_TABLE))
    assert "member_type" in checks and "state" in checks  # CHECKs present
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(db))
    assert _TABLE not in set(insp2.get_table_names())
