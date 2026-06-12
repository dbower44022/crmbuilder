"""WTK-106 — migration 0048 creates migration_mappings + rebuilds CHECKs.

Mirrors the test_0045 pattern: create_all, drop the migration_mappings table
to simulate the pre-0048 state, stamp at 0047, upgrade to 0048 (explicit
revision so later chain growth doesn't perturb the single-step downgrade),
assert the table is back and the change_log/refs CHECKs admit the new
``migration_mapping`` type + edge kinds, then downgrade to 0047.
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
_MIGRATION_0047 = "0047_wtk_089_deposit_event_kind"
_MIGRATION_0048 = "0048_wtk_106_migration_mapping_entity"
_TABLE = "migration_mappings"


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


def test_0048_creates_and_drops_migration_mappings_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0047], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0048], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), (
        "migration_mappings missing after 0048"
    )
    with eng.begin() as c:
        # The recreated table accepts a valid row (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO migration_mappings "
                "(engagement_id, migration_mapping_identifier, "
                "migration_mapping_level, migration_mapping_disposition, "
                "migration_mapping_source_system_label, "
                "migration_mapping_source_entity_name, "
                "migration_mapping_source_attribute_name, "
                "migration_mapping_status, migration_mapping_created_at, "
                "migration_mapping_updated_at) "
                "VALUES ('ENG-001', 'MIG-001', 'field', 'transform', "
                "'espocrm @ crm.cbmentors.org', 'Contact', 'cContactType', "
                "'confirmed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits the new entity type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'migration_mapping', 'MIG-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit a migration_mapping source + both
        # new edge kinds against the two data-bearing capture types.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9001', 'migration_mapping', 'MIG-001', 'field', 'FLD-041', "
                "'migration_mapping_migrates_from_record', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9002', 'migration_mapping', 'MIG-001', 'field', 'FLD-118', "
                "'migration_mapping_migrates_to_record', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        # The rejected_by_decision source-set extension needs no CHECK change
        # (the kind is already admitted); a mapping-sourced rationale edge works.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9003', 'migration_mapping', 'MIG-001', 'decision', 'DEC-001', "
                "'rejected_by_decision', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0047], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names()), (
        "migration_mappings present after downgrade"
    )
