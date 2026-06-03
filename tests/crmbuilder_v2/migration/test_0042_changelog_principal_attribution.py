"""PI-γ — migration 0042 adds change_log.principal_id + widens the actor CHECK.

CI-safe (mirrors the test_0041 pattern): build the full schema via create_all,
drop principal_id + narrow the actor CHECK to simulate the pre-0042 state, stamp
at 0041, ``upgrade head`` (runs only 0042), assert the column is back and the
new actor kinds are admitted; then downgrade and assert the column is gone.
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
_MIGRATION_0041 = "0041_pi_gamma_principals_tokens_roles"
_MIGRATION_0042 = "0042_pi_gamma_changelog_principal_attribution"


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


def test_model_has_principal_id() -> None:
    assert "principal_id" in Base.metadata.tables["change_log"].c


def test_0042_adds_principal_id_and_widens_actor_check(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0041], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0042], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("change_log")}
    assert "principal_id" in cols
    # A row with the new 'service_agent' actor is accepted by the widened CHECK.
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                " principal_id, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'decision', 'DEC-001', 'insert', "
                "'service_agent', 'PRN-007', 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0041], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    cols2 = {c["name"] for c in insp2.get_columns("change_log")}
    assert "principal_id" not in cols2
