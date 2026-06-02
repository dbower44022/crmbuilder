"""PI-123 Slice 1 — migration 0037 folds the engagements table into the unified DB.

Two tests, neither needing the (decommissioned) catalog YAMLs:

- ``test_engagements_model_parity`` — pure-metadata proof that the new
  unified-DB model ``access/models.py::EngagementRow`` is column-for-column,
  constraint-for-constraint, index-for-index identical to the legacy meta-DB
  model ``access/meta_models.py::EngagementRow``. This pins the transitional
  duplication (two definitions of one table, one on ``Base`` and one on
  ``MetaBase``) so they cannot drift before the meta DB is retired at cutover.

- ``test_0037_creates_and_drops_engagements_table`` — runs migration 0037 in
  isolation by stamping the DB at 0036 (its down_revision) and upgrading one
  step, so the catalog-seed migration (0004) never runs. Asserts the table and
  its five indexes appear, then downgrades and asserts they are gone.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.meta_models import EngagementRow as MetaEngagementRow
from crmbuilder_v2.access.models import EngagementRow as MainEngagementRow
from sqlalchemy import CheckConstraint, create_engine, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_DOWN_REVISION = "0036_ado_workstream_state_model_substrate"


def _table_fingerprint(table) -> tuple[dict, dict, dict]:
    """A comparable shape: columns, check constraints, indexes."""
    cols = {
        c.name: (str(c.type), bool(c.nullable), bool(c.primary_key))
        for c in table.columns
    }
    checks = {
        con.name: str(con.sqltext)
        for con in table.constraints
        if isinstance(con, CheckConstraint)
    }
    indexes = {
        ix.name: (bool(ix.unique), tuple(str(e) for e in ix.expressions))
        for ix in table.indexes
    }
    return cols, checks, indexes


def test_engagements_model_parity() -> None:
    main = _table_fingerprint(MainEngagementRow.__table__)
    meta = _table_fingerprint(MetaEngagementRow.__table__)
    assert MainEngagementRow.__tablename__ == "engagements"
    assert MetaEngagementRow.__tablename__ == "engagements"
    assert main[0] == meta[0], f"column mismatch: {main[0]} != {meta[0]}"
    assert main[1] == meta[1], f"check-constraint mismatch: {main[1]} != {meta[1]}"
    assert main[2] == meta[2], f"index mismatch: {main[2]} != {meta[2]}"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    export_dir = db_path.parent / "db-export"
    export_dir.mkdir(parents=True, exist_ok=True)
    env["CRMBUILDER_V2_EXPORT_DIR"] = str(export_dir)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR),
        env=env,
        capture_output=True,
        text=True,
    )


def _index_names(conn) -> set[str]:
    return {
        r[0]
        for r in conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND tbl_name='engagements'"
            )
        )
    }


def _has_engagements_table(conn) -> bool:
    rows = list(
        conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='engagements'"
            )
        )
    )
    return len(rows) == 1


def test_0037_creates_and_drops_engagements_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"

    # Stamp at 0037's down_revision so only 0037 runs on the next upgrade —
    # the catalog-seed migration (0004) and the rest of the chain are skipped.
    stamp = _alembic(["stamp", _DOWN_REVISION], db)
    assert stamp.returncode == 0, (
        f"alembic stamp failed:\nSTDOUT:\n{stamp.stdout}\nSTDERR:\n{stamp.stderr}"
    )

    up = _alembic(["upgrade", "head"], db)
    assert up.returncode == 0, (
        f"alembic upgrade head failed:\n"
        f"STDOUT:\n{up.stdout}\nSTDERR:\n{up.stderr}"
    )

    engine = create_engine(f"sqlite:///{db}")
    with engine.connect() as c:
        assert _has_engagements_table(c), "engagements table missing after 0037"
        idx = _index_names(c)
        for name in (
            "ux_engagements_code_lower",
            "ux_engagements_name_lower",
            "ix_engagements_status",
            "ix_engagements_last_opened_at",
            "ix_engagements_deleted_at",
        ):
            assert name in idx, f"index {name} missing after 0037 (have {idx})"

    down = _alembic(["downgrade", "-1"], db)
    assert down.returncode == 0, (
        f"alembic downgrade -1 failed:\n"
        f"STDOUT:\n{down.stdout}\nSTDERR:\n{down.stderr}"
    )
    engine2 = create_engine(f"sqlite:///{db}")
    with engine2.connect() as c:
        assert not _has_engagements_table(
            c
        ), "engagements table still present after downgrade"
