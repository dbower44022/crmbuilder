"""PI-189 slice 3 — migration 0056 creates dedup_rules + message_templates
and rebuilds the entity-type CHECKs.

Mirrors the test_0055 pattern: create_all, drop the two new tables to
simulate the pre-0056 state, stamp at 0055, upgrade to 0056 (explicit
revision so later chain growth doesn't perturb the single-step downgrade),
assert the tables are back, the change_log/refs CHECKs admit the two new
``dedup_rule`` / ``message_template`` types, the non-empty-array CHECK on
``dedup_rule_match_fields`` bites, and the pre-existing plain ``refs`` indexes
(``ix_refs_source`` / ``ix_refs_target``) survive the batch recreate, then
downgrade to 0055.
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
_MIGRATION_DOWN = "0057_pi_189_condition_design_records"
_MIGRATION_UP = "0058_pi_189_dedup_template_design_records"
_TABLES = ("dedup_rules", "message_templates")


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


def test_0056_creates_and_drops_dedup_template_tables(tmp_path: Path) -> None:
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
        assert table in names, f"{table} missing after 0056"

    # The pre-existing plain refs indexes survive the batch recreate.
    refs_indexes = {ix["name"] for ix in insp.get_indexes("refs")}
    assert "ix_refs_source" in refs_indexes
    assert "ix_refs_target" in refs_indexes

    with eng.begin() as c:
        # The recreated tables accept valid rows (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO dedup_rules "
                "(engagement_id, dedup_rule_identifier, dedup_rule_name, "
                "dedup_rule_entity, dedup_rule_match_fields, "
                "dedup_rule_on_match, dedup_rule_status, "
                "dedup_rule_created_at, dedup_rule_updated_at) "
                "VALUES ('ENG-001', 'DUP-001', 'Email match', 'ENT-001', "
                "'[\"email\"]', 'block', 'candidate', CURRENT_TIMESTAMP, "
                "CURRENT_TIMESTAMP)"
            )
        )
        c.execute(
            text(
                "INSERT INTO message_templates "
                "(engagement_id, message_template_identifier, "
                "message_template_name, message_template_body, "
                "message_template_status, message_template_created_at, "
                "message_template_updated_at) "
                "VALUES ('ENG-001', 'MSG-001', 'Welcome', 'Hello', "
                "'candidate', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits the two new entity types.
        for etype, ident in (
            ("dedup_rule", "DUP-001"),
            ("message_template", "MSG-001"),
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
                "VALUES ('REF-9401', 'dedup_rule', 'DUP-001', "
                "'message_template', 'MSG-001', 'references', "
                "CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )

    # The non-empty-array CHECK on dedup_rule_match_fields bites.
    with pytest.raises(IntegrityError):
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO dedup_rules "
                    "(engagement_id, dedup_rule_identifier, dedup_rule_name, "
                    "dedup_rule_entity, dedup_rule_match_fields, "
                    "dedup_rule_on_match, dedup_rule_status, "
                    "dedup_rule_created_at, dedup_rule_updated_at) "
                    "VALUES ('ENG-001', 'DUP-002', 'Empty', 'ENT-001', "
                    "'[]', 'block', 'candidate', CURRENT_TIMESTAMP, "
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
