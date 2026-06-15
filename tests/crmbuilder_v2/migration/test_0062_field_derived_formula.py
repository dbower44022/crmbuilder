"""Migration 0062 — PI-197 derived/formula columns on ``fields``.

Mirrors the 0055 column-add round-trip. The genuine pre-0062 state is
reached via the migration's own downgrade: create_all (everything present
from the ORM), stamp at 0062, downgrade to 0061 (drops the two new
columns), assert the pre-state, then upgrade back to 0062 (the real add
path) and assert both columns are in place. The pre-existing
identifier-format / boolean CHECKs survive the SQLite batch recreate.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0061 = "0061_pi_195_filtered_tab"
_MIGRATION_0062 = "0062_pi_197_field_derived_formula"

_NEW_FIELD_COLUMNS = {"field_derived_result_type", "field_formula"}


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


def test_0062_columns_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    # Stamp at head (0062) then downgrade to reach the genuine pre-0062 state.
    stamp = _alembic(["stamp", _MIGRATION_0062], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_0061], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: the two new columns are gone.
    assert not (_NEW_FIELD_COLUMNS & _cols(db, "fields")), "new cols present"
    # Pre-existing CHECKs survived the batch downgrade recreate.
    assert "ck_field_identifier_format" in _checks(db, "fields")
    assert "ck_field_required_boolean" in _checks(db, "fields")

    # The real add path: upgrade to 0062 with the columns absent.
    up = _alembic(["upgrade", _MIGRATION_0062], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_FIELD_COLUMNS <= _cols(db, "fields"), "new cols missing"
    # Pre-existing CHECKs still present after the batch recreate.
    assert "ck_field_identifier_format" in _checks(db, "fields")
    assert "ck_field_required_boolean" in _checks(db, "fields")
