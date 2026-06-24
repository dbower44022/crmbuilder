"""Migration 0086 (PI-051) — security-rule tables + entity-type CHECK rebuild.

create_all, drop the two new tables, stamp 0085, upgrade 0086, assert both
tables are back and the change_log / refs CHECKs admit the two new entity types,
then downgrade to 0085 and assert the tables are gone.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_DOWN = "0085_pi_301_agent_capability_description"
_MIGRATION = "0086_pi_051_security_rules"
_TABLES = ("field_permission_rules", "field_visibility_rules")


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def test_0086_creates_and_drops_security_rule_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for table in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {table}"))
    engine.dispose()

    stamp = _alembic(["stamp", _DOWN], db)
    assert stamp.returncode == 0, (
        f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    )
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    names = set(insp.get_table_names())
    for table in _TABLES:
        assert table in names
    with eng.begin() as c:
        # The recreated tables accept valid rows (CHECKs carried over).
        c.execute(text(
            "INSERT INTO field_permission_rules (engagement_id, "
            "field_permission_rule_identifier, field_permission_rule_name, "
            "field_permission_rule_role, field_permission_rule_target_field, "
            "field_permission_rule_permission_level, "
            "field_permission_rule_status, "
            "field_permission_rule_deployment_status, "
            "field_permission_rule_created_at, "
            "field_permission_rule_updated_at) VALUES ('ENG-001', 'FPR-001', "
            "'Mentor — backgroundCheck', 'ROL-001', 'FLD-001', 'read_only', "
            "'candidate', 'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        c.execute(text(
            "INSERT INTO field_visibility_rules (engagement_id, "
            "field_visibility_rule_identifier, field_visibility_rule_name, "
            "field_visibility_rule_role, field_visibility_rule_target_field, "
            "field_visibility_rule_visible, field_visibility_rule_status, "
            "field_visibility_rule_deployment_status, "
            "field_visibility_rule_created_at, "
            "field_visibility_rule_updated_at) VALUES ('ENG-001', 'FVR-001', "
            "'Mentor — salaryBand', 'ROL-001', 'FLD-001', 0, 'candidate', "
            "'pending', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ))
        # The rebuilt change_log CHECK admits the new entity types.
        for ident, etype in (
            ("FPR-001", "field_permission_rule"),
            ("FVR-001", "field_visibility_rule"),
        ):
            c.execute(text(
                "INSERT INTO change_log (timestamp, entity_type, "
                "entity_identifier, operation, actor, engagement_id) VALUES "
                "(CURRENT_TIMESTAMP, :etype, :ident, 'insert', "
                "'claude_session', 'ENG-001')"
            ), {"etype": etype, "ident": ident})
        # The rebuilt refs CHECK admits the new types as reference targets.
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, "
            "engagement_id) VALUES ('REF-9501', 'field_permission_rule', "
            "'FPR-001', 'role', 'ROL-001', 'is_about', CURRENT_TIMESTAMP, "
            "'ENG-001')"
        ))
        c.execute(text(
            "INSERT INTO refs (reference_identifier, source_type, source_id, "
            "target_type, target_id, relationship_kind, created_at, "
            "engagement_id) VALUES ('REF-9502', 'field_visibility_rule', "
            "'FVR-001', 'role', 'ROL-001', 'is_about', CURRENT_TIMESTAMP, "
            "'ENG-001')"
        ))
    eng.dispose()

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, (
        f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    )
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    names2 = set(insp2.get_table_names())
    for table in _TABLES:
        assert table not in names2
