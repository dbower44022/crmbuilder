"""PI-407 — migration 0136: the data-bearing classification and the
active-subset field on settings.

create_all (post-change schema), stamp 0136, run the real downgrade to 0135
(both columns, the CHECK and the index are gone), upgrade 0136 again: they
are back, an existing field reads not-data-bearing, an existing setting names
no field.
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
_DOWN = "0135_pi_413_workflow_membership"
_MIGRATION = "0136_pi_407_active_subset"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def _cols(db: Path, table: str) -> set[str]:
    return {c["name"] for c in inspect(create_engine(f"sqlite:///{db}")).get_columns(table)}


def _checks(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(f"sqlite:///{db}"))
    return {c["name"] for c in insp.get_check_constraints(table) if c.get("name")}


def _indexes(db: Path, table: str) -> set[str]:
    return {i["name"] for i in inspect(create_engine(f"sqlite:///{db}")).get_indexes(table)}


def test_0136_round_trips_and_defaults_existing_rows(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "field_data_bearing" not in _cols(db, "fields")
    assert "ck_field_data_bearing_boolean" not in _checks(db, "fields")
    assert "system_setting_active_subset_field" not in _cols(db, "system_settings")
    assert "ix_system_settings_active_subset_field" not in _indexes(db, "system_settings")

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(
            text(
                "INSERT INTO engagements (engagement_identifier, engagement_code, "
                "engagement_name, engagement_purpose, engagement_status, "
                "engagement_created_at, engagement_updated_at) VALUES ('ENG-001', "
                "'CRMBUILDER', 'CRMBuilder', 'dogfood', 'active', '2026-01-01', "
                "'2026-01-01')"
            )
        )
        c.execute(
            text(
                "INSERT INTO fields (engagement_id, field_identifier, field_name, "
                "field_description, field_type, field_required, field_status, "
                "field_read_only, field_unique, field_built_in, field_created_at, "
                "field_updated_at) VALUES ('ENG-001', 'FLD-001', 'f', 'd', 'enum', "
                "0, 'candidate', 0, 0, 0, '2026-01-01', '2026-01-01')"
            )
        )
        c.execute(
            text(
                "INSERT INTO system_settings (engagement_id, system_setting_identifier, "
                "system_setting_key, system_setting_name, system_setting_value_type, "
                "system_setting_status, system_setting_created_at, "
                "system_setting_updated_at) VALUES ('ENG-001', 'SET-001', 'siteUrl', "
                "'Site URL', 'text', 'candidate', '2026-01-01', '2026-01-01')"
            )
        )
    engine.dispose()

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert "field_data_bearing" in _cols(db, "fields")
    assert "ck_field_data_bearing_boolean" in _checks(db, "fields")
    assert "system_setting_active_subset_field" in _cols(db, "system_settings")
    assert "ix_system_settings_active_subset_field" in _indexes(db, "system_settings")

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as c:
        flag = c.execute(
            text("SELECT field_data_bearing FROM fields WHERE field_identifier='FLD-001'")
        ).scalar()
        names = c.execute(
            text(
                "SELECT system_setting_active_subset_field FROM system_settings "
                "WHERE system_setting_identifier='SET-001'"
            )
        ).scalar()
    engine.dispose()
    assert flag == 0
    assert names is None
