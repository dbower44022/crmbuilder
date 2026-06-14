"""Migration 0053 — PI-182 intrinsic columns + field_options child table.

Mirrors the test_0049 column-add pattern. Because 0053 adds columns plus a
new child table, the genuine pre-0053 state is reached via the migration's
own downgrade: create_all (everything present from the ORM), stamp at 0053,
downgrade to 0052 (drops the new columns/CHECKs and the field_options
table), assert the pre-state, then upgrade back to 0053 (the real add path)
and assert the columns, the boolean CHECKs, and the field_options table are
all in place.
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
_MIGRATION_0052 = "0054_pi_186_instance_entity"
_MIGRATION_0053 = "0055_pi_182_field_entity_intrinsic"

_NEW_FIELD_COLUMNS = {
    "field_tooltip",
    "field_usage_summary",
    "field_default_value",
    "field_format",
    "field_numeric_scale",
    "field_max_length",
    "field_min",
    "field_max",
    "field_read_only",
    "field_unique",
    "field_externally_populated",
}
_NEW_FIELD_CHECKS = {
    "ck_field_read_only_boolean",
    "ck_field_unique_boolean",
    "ck_field_externally_populated_boolean",
}
_NEW_ENTITY_COLUMNS = {
    "entity_default_sort_field",
    "entity_default_sort_direction",
    "entity_track_activity",
}


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


def _tables(db: Path) -> set[str]:
    return set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())


def test_0053_columns_table_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    # Stamp at head (0053) then downgrade to reach the genuine pre-0053 state.
    stamp = _alembic(["stamp", _MIGRATION_0053], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_0052], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: new columns / CHECKs / table all gone.
    assert not (_NEW_FIELD_COLUMNS & _cols(db, "fields")), "field cols present"
    assert not (_NEW_FIELD_CHECKS & _checks(db, "fields")), "field checks present"
    assert not (_NEW_ENTITY_COLUMNS & _cols(db, "entities")), "entity cols present"
    assert "field_options" not in _tables(db), "field_options present pre-0053"
    # The pre-existing identifier-format + boolean CHECK survived the batch
    # downgrade (the SQLite recreate preserves reflected constraints).
    assert "ck_field_identifier_format" in _checks(db, "fields")
    assert "ck_field_required_boolean" in _checks(db, "fields")

    # The real add path: upgrade to 0053 with the columns/table absent.
    up = _alembic(["upgrade", _MIGRATION_0053], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_FIELD_COLUMNS <= _cols(db, "fields"), "field cols missing"
    assert _NEW_FIELD_CHECKS <= _checks(db, "fields"), "field checks missing"
    assert _NEW_ENTITY_COLUMNS <= _cols(db, "entities"), "entity cols missing"
    assert "field_options" in _tables(db), "field_options missing after 0053"
    assert {"id", "engagement_id", "field_identifier", "option_value",
            "option_label", "option_order"} == _cols(db, "field_options")
    # Pre-existing CHECKs still present after the batch recreate.
    assert "ck_field_identifier_format" in _checks(db, "fields")
    assert "ck_field_required_boolean" in _checks(db, "fields")
