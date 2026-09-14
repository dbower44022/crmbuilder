"""PI-255 — migration 0081 creates the seven source mapping tables + CHECKs.

Mirrors the 0060 pattern: create_all, drop the new tables, stamp 0080, upgrade
0081, assert the tables are back and the change_log / refs CHECKs admit the new
entity types and the membership-state CHECK admits the canonical states, then
downgrade to 0080 and assert the tables are gone. (0081 originally also added the
candidate_pending / mapping_stale membership states; the reconciler design pass
removed them — SES-247, DEC-650, migration 0095.)
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0037_pi_263_cost_events"
_MIGRATION = "0038_pi_255_source_mapping_tables"
_TABLES = (
    "source_mappings",
    "source_mapping_targets",
    "source_mapping_joins",
    "field_mappings",
    "field_mapping_translations",
    "value_mappings",
    "mapping_candidates",
)




def test_0081_creates_and_drops_tables() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        for t in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    engine.dispose()

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(db)
    insp = inspect(eng)
    assert set(_TABLES) <= set(insp.get_table_names())
    with eng.begin() as c:
        # change_log + refs CHECKs admit the new entity types.
        c.execute(text(
            "INSERT INTO change_log (timestamp, entity_type, entity_identifier, "
            "operation, actor, engagement_id) VALUES (CURRENT_TIMESTAMP, "
            "'source_mapping', 'SMG-001', 'insert', 'claude_session', 'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, engagement_id) "
            "VALUES ('REF-9401', 'source_mapping', 'SMG-001', 'field_mapping', "
            "'FMP-001', 'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
        ))
        # membership state CHECK admits the canonical states. (The two
        # candidate_pending / mapping_stale states 0081 originally added were
        # removed by the reconciler design pass — SES-247, DEC-650, migration
        # 0095 — so the membership join stays canonical-only.)
        c.execute(text(
            "INSERT INTO instance_memberships (engagement_id, instance_identifier, "
            "member_type, member_identifier, state, last_audited_at, created_at, "
            "updated_at) VALUES ('ENG-001', 'INST-001', 'entity', 'ENT-001', "
            "'present', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP)"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(db))
    assert not (set(_TABLES) & set(insp2.get_table_names()))
