"""PI-123 Slice 1 — migration 0037 folds the engagements table into the unified DB.

- ``test_0037_creates_and_drops_engagements_table`` — enters the chain
  mid-stream by stamping the DB at 0036 (0037's down_revision) and upgrading
  to head, so the catalog-seed migration (0004) never runs. Asserts the
  engagements table and its five indexes appear (and survive the rest of the
  chain — 0040's batch recreate must restore the expression indexes), then
  downgrades back to 0036 and asserts they are gone. Every migration after
  0036 therefore has to tolerate a DB containing only what 0037+ created.

(PI-β removed the separate meta DB; the former ``test_engagements_model_parity``
pinned the unified ``EngagementRow`` against the now-deleted meta model.)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_DOWN_REVISION = "0036_ado_workstream_state_model_substrate"


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

    # Downgrade back to the stamped base — head has moved past 0037, so this
    # replays every downgrade from head through 0037 (which drops the table).
    down = _alembic(["downgrade", _DOWN_REVISION], db)
    assert down.returncode == 0, (
        f"alembic downgrade {_DOWN_REVISION} failed:\n"
        f"STDOUT:\n{down.stdout}\nSTDERR:\n{down.stderr}"
    )
    engine2 = create_engine(f"sqlite:///{db}")
    with engine2.connect() as c:
        assert not _has_engagements_table(
            c
        ), "engagements table still present after downgrade"
