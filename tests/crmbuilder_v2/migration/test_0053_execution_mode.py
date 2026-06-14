"""PI-183 — migration 0053 adds execution_mode + dispatch_approved columns.

Mirrors the test_0049 pattern: 0053 adds columns (not a table), so the genuine
pre-0053 state is reached via the migration's own downgrade. create_all (columns
present from the ORM), stamp at 0053, downgrade to 0052 (drops the columns +
CHECKs), assert the pre-state, then upgrade back to 0053 (the real column-add
path) and assert the columns + CHECKs are in place and the CHECKs reject
out-of-vocab values.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0052 = "0052_pi_161_service_entity"
_MIGRATION_0053 = "0053_pi_183_execution_mode"

_NEW_PROJECT_COLS = {"project_execution_mode"}
_NEW_PLANNING_COLS = {"execution_mode", "dispatch_approved"}
_NEW_PROJECT_CHECKS = {"ck_project_execution_mode"}
_NEW_PLANNING_CHECKS = {"ck_planning_execution_mode", "ck_planning_dispatch_approved"}


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


def _cols(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_columns(table)}


def _checks(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_check_constraints(table)}


def _insert_project(db: Path, ident: str, mode: str) -> None:
    eng = create_engine(f"sqlite:///{db}")
    try:
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO projects (project_identifier, project_name, "
                    "project_status, project_purpose, project_description, "
                    "project_created_at, project_updated_at, project_execution_mode, "
                    "engagement_id) VALUES "
                    f"('{ident}', 'n', 'planned', 'p', 'd', CURRENT_TIMESTAMP, "
                    f"CURRENT_TIMESTAMP, '{mode}', 'ENG-001')"
                )
            )
    finally:
        eng.dispose()


def test_0053_execution_mode_columns_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    # Stamp at head (0053) then downgrade to reach the genuine pre-0053 state.
    stamp = _alembic(["stamp", _MIGRATION_0053], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_0052], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: new columns + CHECKs gone.
    assert not (_NEW_PROJECT_COLS & _cols(db, "projects")), "project col present"
    assert not (_NEW_PLANNING_COLS & _cols(db, "planning_items")), "planning cols present"
    assert not (_NEW_PROJECT_CHECKS & _checks(db, "projects")), "project check present"
    assert not (_NEW_PLANNING_CHECKS & _checks(db, "planning_items")), "planning checks"

    # The real add path: upgrade to 0053 with the columns absent.
    up = _alembic(["upgrade", _MIGRATION_0053], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_PROJECT_COLS <= _cols(db, "projects"), "project col missing"
    assert _NEW_PLANNING_COLS <= _cols(db, "planning_items"), "planning cols missing"
    assert _NEW_PROJECT_CHECKS <= _checks(db, "projects"), "project check missing"
    assert _NEW_PLANNING_CHECKS <= _checks(db, "planning_items"), "planning checks missing"

    # A valid mode inserts; an out-of-vocab mode is rejected by the CHECK.
    _insert_project(db, "PRJ-900", "interactive")
    bogus_rejected = False
    try:
        _insert_project(db, "PRJ-901", "not_a_real_mode")
    except (IntegrityError, OperationalError):
        bogus_rejected = True
    assert bogus_rejected, "out-of-vocab execution_mode should be rejected"
