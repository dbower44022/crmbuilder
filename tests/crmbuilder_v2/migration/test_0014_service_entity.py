"""PI-161 — migration 0049 creates services + rebuilds CHECKs.

Mirrors the test_0048 pattern: create_all, drop the services table to
simulate the pre-0049 state, stamp at 0048, upgrade to 0049 (explicit
revision so later chain growth doesn't perturb the single-step downgrade),
assert the table is back and the change_log/refs CHECKs admit the new
``service`` type + edge kinds, then downgrade to 0048.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_DOWN = "0013_review_signoffs"
_MIGRATION_SERVICE = "0014_pi_161_service_entity"
_TABLE = "services"




def test_0049_creates_and_drops_services_table() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_SERVICE], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(db)
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), "services missing after 0049"
    with eng.begin() as c:
        # The recreated table accepts a valid row (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO services "
                "(engagement_id, service_identifier, service_name, "
                "service_purpose, service_status, service_created_at, "
                "service_updated_at) "
                "VALUES ('ENG-001', 'SVC-001', 'Document Storage', "
                "'Store and version documents across domains.', 'confirmed', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits the new entity type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'service', 'SVC-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit the inbound process_consumes_service
        # edge (process → service) ...
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9101', 'process', 'PROC-002', 'service', "
                "'SVC-001', 'process_consumes_service', CURRENT_TIMESTAMP, "
                "'ENG-001')"
            )
        )
        # ... and the outbound service_owns_entity edge (service → entity).
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9102', 'service', 'SVC-001', 'entity', "
                "'ENT-001', 'service_owns_entity', CURRENT_TIMESTAMP, "
                "'ENG-001')"
            )
        )
        # The rejected_by_decision source-set extension needs no CHECK change
        # (the kind is already admitted); a service-sourced rationale edge works.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9103', 'service', 'SVC-001', 'decision', "
                "'DEC-001', 'rejected_by_decision', CURRENT_TIMESTAMP, "
                "'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(db))
    assert _TABLE not in set(insp2.get_table_names()), (
        "services present after downgrade"
    )
