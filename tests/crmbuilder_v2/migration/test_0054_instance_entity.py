"""PI-186 — migration 0054 creates instances + rebuilds entity-type CHECKs.

Mirrors the test_0052 pattern: create_all, drop the instances table to
simulate the pre-0054 state, stamp at 0053, upgrade to 0054 (explicit
revision), assert the table is back and the change_log/refs CHECKs admit the
new ``instance`` type, then downgrade to 0053.
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
_MIGRATION_DOWN = "0053_pi_183_execution_mode"
_MIGRATION_INSTANCE = "0054_pi_186_instance_entity"
_TABLE = "instances"


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


def test_0054_creates_and_drops_instances_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_DOWN], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_INSTANCE], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), "instances missing after 0054"
    with eng.begin() as c:
        # The recreated table accepts a valid row (CHECKs carried over).
        c.execute(
            text(
                "INSERT INTO instances "
                "(engagement_id, instance_identifier, instance_name, "
                "instance_vendor, instance_url, instance_role, "
                "instance_auth_method, instance_status, instance_created_at, "
                "instance_updated_at) "
                "VALUES ('ENG-001', 'INST-001', 'CBM sandbox', 'espocrm', "
                "'https://sandbox.example.org', 'both', 'api_key', 'active', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        # The rebuilt change_log CHECK admits the new entity type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'instance', 'INST-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit an instance as a reference target.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, "
                "target_id, relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9201', 'decision', 'DEC-001', 'instance', "
                "'INST-001', 'is_about', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names()), (
        "instances present after downgrade"
    )
