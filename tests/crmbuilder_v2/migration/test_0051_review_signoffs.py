"""Phase 6 — migration 0051 creates review_signoffs + rebuilds change_log CHECK.

create_all (the table + the change_log CHECK come from the ORM), stamp at 0051,
downgrade to 0050 (drops the table + narrows the CHECK), assert the pre-state,
upgrade back to 0051, assert the table returns and change_log admits a
``review_signoff`` row.
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
_MIGRATION_0050 = "0050_planning_item_implements_requirement"
_MIGRATION_0051 = "0051_review_signoffs"
_TABLE = "review_signoffs"


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


def _insert_changelog(db: Path) -> None:
    eng = create_engine(f"sqlite:///{db}")
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) VALUES (CURRENT_TIMESTAMP, 'review_signoff', '1', "
                "'insert', 'claude_session', 'ENG-001')"
            )
        )
    eng.dispose()


def test_0051_review_signoffs_round_trip(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()

    assert _alembic(["stamp", _MIGRATION_0051], db).returncode == 0
    down = _alembic(["downgrade", _MIGRATION_0050], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    assert _TABLE not in set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
    rejected = False
    try:
        _insert_changelog(db)
    except (IntegrityError, OperationalError):
        rejected = True
    assert rejected, "change_log should reject review_signoff before 0051"

    up = _alembic(["upgrade", _MIGRATION_0051], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _TABLE in set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())
    _insert_changelog(db)  # now admitted
