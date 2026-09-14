"""PI-134 — migration 0045 creates the findings table + rebuilds CHECKs.

Mirrors the test_0043 pattern: create_all, drop the findings table to simulate
the pre-0045 state, stamp at 0044, upgrade to 0045 (explicit revision so later
chain growth doesn't perturb the single-step downgrade), assert the table is
back and the change_log/refs CHECKs admit the new ``finding`` type + edge kinds,
then downgrade to 0044.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_0044 = "0006_pi_122_registry_binding_edges"
_MIGRATION_0045 = "0007_pi_134_findings_entity"
_TABLE = "findings"




def test_models_define_findings_table() -> None:
    assert _TABLE in Base.metadata.tables


def test_0045_creates_and_drops_findings_table() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0044], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0045], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(db)
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), "findings missing after 0045"
    with eng.begin() as c:
        # The rebuilt change_log CHECK admits the new 'finding' entity type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'finding', 'FND-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit a finding source + the new edge kinds.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9001', 'finding', 'FND-001', 'planning_item', 'PI-001', "
                "'finding_relates_to', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9002', 'finding', 'FND-001', 'decision', 'DEC-001', "
                "'finding_resolved_by', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0044], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(db))
    assert _TABLE not in set(insp2.get_table_names()), "findings present after downgrade"
