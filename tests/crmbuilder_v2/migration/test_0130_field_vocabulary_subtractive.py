"""PI-414 — migration 0130, the field vocabulary's subtractive half.

create_all (post-change schema), stamp 0130, run the real downgrade to 0129
(restores ``field_externally_populated`` and its boolean CHECK), seed fields
that carry the two retired spellings, upgrade 0130: the flag column and its
CHECK are gone, a flagged field now says ``supplied_by = 'another_system'``,
a field that already declared a supplier keeps it, ``multiline`` moved from
the format to the display, and a field that already declared a display keeps
that display while losing the retired format token.
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
_DOWN = "0129_pi_444_instance_feature_selection"
_MIGRATION = "0130_pi_414_field_vocabulary_subtractive"


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


def _field(identifier: str, *, flag: int, fmt: str | None,
           display: str | None, supplied_by: str | None) -> str:
    def _lit(v: str | None) -> str:
        return "NULL" if v is None else f"'{v}'"
    return (
        "INSERT INTO fields (engagement_id, field_identifier, field_name, "
        "field_description, field_type, field_required, field_status, "
        "field_read_only, field_unique, field_built_in, "
        "field_externally_populated, field_format, field_display, "
        "field_supplied_by, field_created_at, field_updated_at) VALUES "
        f"('ENG-001', '{identifier}', 'f_{identifier}', 'd', 'text', 0, "
        f"'candidate', 0, 0, 0, {flag}, {_lit(fmt)}, {_lit(display)}, "
        f"{_lit(supplied_by)}, '2026-01-01', '2026-01-01')"
    )


def test_0130_converts_then_subtracts(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _alembic(["stamp", _MIGRATION], db).returncode == 0

    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "field_externally_populated" in _cols(db, "fields")
    assert "ck_field_externally_populated_boolean" in _checks(db, "fields")

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
        # Flagged, no supplier declared -> backfills another_system.
        c.execute(text(_field("FLD-001", flag=1, fmt=None, display=None,
                              supplied_by=None)))
        # Flagged, supplier already declared -> the declaration wins.
        c.execute(text(_field("FLD-002", flag=1, fmt=None, display=None,
                              supplied_by="this_crm")))
        # Retired format token, no display -> the token becomes the display.
        c.execute(text(_field("FLD-003", flag=0, fmt="multiline", display=None,
                              supplied_by=None)))
        # Retired format token, display declared -> token dropped, display kept.
        c.execute(text(_field("FLD-004", flag=0, fmt="multiline",
                              display="rich_text", supplied_by=None)))
    engine.dispose()

    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert "field_externally_populated" not in _cols(db, "fields")
    assert "ck_field_externally_populated_boolean" not in _checks(db, "fields")

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as c:
        rows = {
            r[0]: (r[1], r[2], r[3])
            for r in c.execute(
                text(
                    "SELECT field_identifier, field_supplied_by, field_format, "
                    "field_display FROM fields ORDER BY field_identifier"
                )
            )
        }
    engine.dispose()
    assert rows["FLD-001"] == ("another_system", None, None)
    assert rows["FLD-002"] == ("this_crm", None, None)
    assert rows["FLD-003"] == (None, None, "multiline")
    assert rows["FLD-004"] == (None, None, "rich_text")
