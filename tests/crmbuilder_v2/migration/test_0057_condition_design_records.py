"""PI-189 slice 2 — migration 0055 creates rules + views + automations
and rebuilds the entity-type CHECKs.

Mirrors the test_0054 pattern: create_all, drop the three new tables to
simulate the pre-0055 state, stamp at 0054, upgrade to 0055 (explicit
revision so later chain growth doesn't perturb the single-step downgrade),
assert the tables are back, the change_log/refs CHECKs admit the three new
``rule`` / ``view`` / ``automation`` types, the non-empty-array CHECKs on
``view_columns`` / ``automation_actions`` bite, and the pre-existing plain
``refs`` indexes (``ix_refs_source`` / ``ix_refs_target``) survive the batch
recreate, then downgrade to 0054.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_DOWN = "0056_pi_189_composite_design_records"
_MIGRATION_UP = "0057_pi_189_condition_design_records"
_TABLES = ("rules", "views", "automations")


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


def test_0055_creates_and_drops_condition_design_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for table in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {table}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_UP], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    names = set(insp.get_table_names())
    for table in _TABLES:
        assert table in names, f"{table} missing after 0055"

    # The pre-existing plain refs indexes survive the batch recreate.
    refs_indexes = {ix["name"] for ix in insp.get_indexes("refs")}
    assert "ix_refs_source" in refs_indexes
    assert "ix_refs_target" in refs_indexes

    with eng.begin() as c:
        # The recreated tables accept valid rows (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO rules "
                "(engagement_id, rule_identifier, rule_name, "
                "rule_subject_type, rule_subject_identifier, rule_effect, "
                "rule_condition, rule_status, rule_created_at, "
                "rule_updated_at) "
                "VALUES ('ENG-001', 'RUL-001', 'Stage required', 'field', "
                "'FLD-001', 'required_when', "
                "'{\"field\": \"stage\", \"op\": \"eq\", \"value\": \"won\"}', "
                "'candidate', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        c.execute(
            text(
                "INSERT INTO views "
                "(engagement_id, view_identifier, view_name, view_entity, "
                "view_columns, view_status, view_created_at, view_updated_at) "
                "VALUES ('ENG-001', 'VEW-001', 'Open opps', 'ENT-001', "
                "'[\"name\", \"stage\"]', 'candidate', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        c.execute(
            text(
                "INSERT INTO automations "
                "(engagement_id, automation_identifier, automation_name, "
                "automation_entity, automation_trigger, automation_actions, "
                "automation_status, automation_created_at, "
                "automation_updated_at) "
                "VALUES ('ENG-001', 'AUT-001', 'Mark won', 'ENT-001', "
                "'on_update', '[{\"type\": \"set_field\"}]', 'candidate', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits the three new entity types.
        for etype, ident in (
            ("rule", "RUL-001"),
            ("view", "VEW-001"),
            ("automation", "AUT-001"),
        ):
            c.execute(
                text(
                    "INSERT INTO change_log "
                    "(timestamp, entity_type, entity_identifier, operation, "
                    "actor, engagement_id) "
                    f"VALUES (CURRENT_TIMESTAMP, '{etype}', '{ident}', "
                    "'insert', 'claude_session', 'ENG-001')"
                )
            )
        # The rebuilt refs CHECKs admit the new types as source/target.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9301', 'rule', 'RUL-001', 'view', 'VEW-001', "
                "'references', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )

    # The non-empty-array CHECK on view_columns bites (empty array rejected).
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO views "
                    "(engagement_id, view_identifier, view_name, view_entity, "
                    "view_columns, view_status, view_created_at, "
                    "view_updated_at) "
                    "VALUES ('ENG-001', 'VEW-002', 'Empty', 'ENT-001', "
                    "'[]', 'candidate', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                )
            )

    # The non-empty-array CHECK on automation_actions bites.
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO automations "
                    "(engagement_id, automation_identifier, automation_name, "
                    "automation_entity, automation_trigger, "
                    "automation_actions, automation_status, "
                    "automation_created_at, automation_updated_at) "
                    "VALUES ('ENG-001', 'AUT-002', 'Empty', 'ENT-001', "
                    "'manual', '[]', 'candidate', CURRENT_TIMESTAMP, "
                    "CURRENT_TIMESTAMP)"
                )
            )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    names2 = set(insp2.get_table_names())
    for table in _TABLES:
        assert table not in names2, f"{table} present after downgrade"
