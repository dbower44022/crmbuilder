"""PI-438 — migration 0125 adds governance_rules.applies_to / applies_when and backfills.

create_all, stamp 0125, run the real downgrade to 0124 (SQLite cannot DROP a
column named in a CHECK, so the batch-mode downgrade is the only honest way to
reach the pre-migration shape), seed rules + one profile binding, upgrade 0125:
the columns are back, the CHECKs exist, the profile-bound rule is ``ado_agent``,
the unbound rules are ``claude_code``, and the identifier-keyed moments landed.
The add is guarded so the migration is a no-op on a create_all-materialised DB
(LSN-050).
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_DOWN = "0081_pi_406_system_settings"
_MIGRATION = "0082_pi_438_rule_audience_moment"




def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(db)).get_columns(table)}


def _checks(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(db))
    return {c["name"] for c in insp.get_check_constraints(table) if c.get("name")}


def _rule(identifier: str, body: str) -> str:
    return (
        "INSERT INTO governance_rules (identifier, enforcement, body, version, status, "
        "created_at, updated_at) VALUES "
        f"('{identifier}', 'advisory', '{body}', 1, 'active', '2026-01-01', '2026-01-01')"
    )


def test_0125_adds_backfills_and_drops() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0
    down0 = _alembic(["downgrade", _DOWN], db)
    assert down0.returncode == 0, f"downgrade failed:\n{down0.stdout}\n{down0.stderr}"
    assert "applies_to" not in _cols(db, "governance_rules")
    engine = create_engine(db)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        c.execute(
            text(
                "INSERT INTO engagements (engagement_identifier, engagement_code, "
                "engagement_name, engagement_purpose, engagement_status, "
                "engagement_created_at, engagement_updated_at) VALUES ('ENG-001', "
                "'CRMBUILDER', 'CRMBuilder', 'dogfood', 'active', '2026-01-01', "
                "'2026-01-01')"
            )
        )
        c.execute(text(_rule("GVR-005", "agent rule")))
        c.execute(text(_rule("GVR-229", "trailer rule")))
        c.execute(text(_rule("GVR-238", "ssot rule")))
        c.execute(
            text(
                "INSERT INTO refs (engagement_id, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at) VALUES ('ENG-001', "
                "'agent_profile', 'AGP-002', 'governance_rule', 'GVR-005', "
                "'agent_profile_governed_by_rule', '2026-01-01')"
            )
        )
    engine.dispose()

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    assert {"applies_to", "applies_when"} <= _cols(db, "governance_rules")
    assert {"ck_governance_rule_applies_to", "ck_governance_rule_applies_when"} <= _checks(
        db, "governance_rules"
    )
    engine = create_engine(db)
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        rows = dict(
            c.execute(
                text("SELECT identifier, applies_to || '/' || applies_when FROM governance_rules")
            ).all()
        )
    engine.dispose()
    assert rows == {
        "GVR-005": "ado_agent/always",
        "GVR-229": "claude_code/commit",
        "GVR-238": "claude_code/always",
    }

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "applies_to" not in _cols(db, "governance_rules")
    assert "applies_when" not in _cols(db, "governance_rules")


def test_0125_is_a_no_op_on_a_create_all_db() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _alembic(["stamp", _DOWN], db).returncode == 0
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert {"applies_to", "applies_when"} <= _cols(db, "governance_rules")
