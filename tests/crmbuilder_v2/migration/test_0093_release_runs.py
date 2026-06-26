"""PI-326 — migration 0093 creates release_runs + rebuilds CHECKs.

Mirrors the test_0088 pattern: create_all, drop the release_runs table to simulate
the pre-0093 state, stamp at 0092, upgrade to 0093 (explicit revision so later
chain growth doesn't perturb the single-step downgrade), assert the table is back
and the change_log/refs CHECKs admit the new ``release_run`` type + the
``release_run_relates_to_finding`` edge kind, then downgrade to 0092.
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
_MIGRATION_0092 = "0092_rel_025_field_label"
_MIGRATION_0093 = "0093_pi_326_release_runs"
_TABLE = "release_runs"


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


def test_models_define_release_runs_table() -> None:
    assert _TABLE in Base.metadata.tables


def test_0093_creates_and_drops_release_runs_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text(f"DROP TABLE IF EXISTS {_TABLE}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0092], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0093], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    assert _TABLE in set(insp.get_table_names()), "release_runs missing after 0093"
    with eng.begin() as c:
        # The rebuilt change_log CHECK admits the new 'release_run' type.
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'release_run', 'RUN-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
        # A release row to satisfy the composite FK.
        c.execute(
            text(
                "INSERT INTO releases "
                "(release_identifier, release_title, release_status, "
                "release_description, release_back_half, release_created_at, "
                "release_updated_at, engagement_id) "
                "VALUES ('REL-001', 'R', 'preliminary_planning', 'd', 'per_pi', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        # A release_run row inserts (identifier-format + outcome CHECKs).
        c.execute(
            text(
                "INSERT INTO release_runs "
                "(release_run_identifier, release_identifier, release_run_scope, "
                "release_run_phases_run, release_run_halt_point, release_run_cause, "
                "release_run_cause_code, release_run_outcome, release_run_created_at, "
                "engagement_id) "
                "VALUES ('RUN-001', 'REL-001', '{}', '[]', 'development', "
                "'malformed', 'malformed_decomposition', 'abandoned', "
                "CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
        # The rebuilt refs CHECKs admit a release_run source + the new kind.
        c.execute(
            text(
                "INSERT INTO refs "
                "(reference_identifier, source_type, source_id, target_type, target_id, "
                "relationship_kind, created_at, engagement_id) "
                "VALUES ('REF-9301', 'release_run', 'RUN-001', 'finding', 'FND-001', "
                "'release_run_relates_to_finding', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0092], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    assert _TABLE not in set(insp2.get_table_names()), "release_runs present after downgrade"
