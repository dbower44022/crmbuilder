"""PI-304 — migration 0088 creates task_transitions + rebuilds CHECKs.

Mirrors the test_0045 pattern: create_all, drop the task_transitions table to
simulate the pre-0088 state, stamp at 0087, upgrade to 0088 (explicit revision so
later chain growth doesn't perturb the single-step downgrade), assert the table is
back and the change_log/refs CHECKs admit the new ``task_transition`` type + the
``task_transition_records_task`` edge kind, then downgrade to 0087.
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
_MIGRATION_0087 = "0087_pi_302_work_task_resolved_agent_profile"
_MIGRATION_0088 = "0088_pi_304_task_transitions"
_TABLE = "task_transitions"


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


def test_models_define_task_transitions_table() -> None:
    assert _TABLE in Base.metadata.tables


def test_0088_creates_and_drops_task_transitions_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0087], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0088], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), "task_transitions missing after 0088"
    with eng.begin() as c:
        # The rebuilt change_log CHECK admits the new 'task_transition' type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'task_transition', 'TXN-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit a task_transition source + the new kind.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9101', 'task_transition', 'TXN-001', 'work_task', 'WTK-001', "
                "'task_transition_records_task', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        # A task_transition row inserts (identifier-format + status-union CHECKs).
        c.execute(
            text(
                "INSERT INTO task_transitions "
                "(task_transition_identifier, task_transition_task_type, "
                "task_transition_task_identifier, task_transition_from_status, "
                "task_transition_to_status, task_transition_reason, "
                "task_transition_sequence, task_transition_at, "
                "task_transition_created_at, engagement_id) "
                "VALUES ('TXN-001', 'work_task', 'WTK-001', NULL, 'Ready', "
                "'Planned -> Ready', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0087], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names()), "task_transitions present after downgrade"
