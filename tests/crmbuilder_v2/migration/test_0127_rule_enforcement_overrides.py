"""PI-439 — migration 0127 creates the rule_enforcement_overrides audit table.

create_all, drop the table, stamp 0126, upgrade 0127, assert it is back and a
row inserts; downgrade drops it. The create is guarded (LSN-050) so the
migration is a no-op on a create_all DB.
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
_DOWN = "0126_pi_411_publish_run_plan_fingerprint"
_MIGRATION = "0127_pi_439_rule_enforcement_overrides"
_TABLE = "rule_enforcement_overrides"


def _alembic(args: list[str], db_path: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(_ALEMBIC_DIR), env=env, capture_output=True, text=True,
    )


def _tables(db: Path) -> set[str]:
    return set(inspect(create_engine(f"sqlite:///{db}")).get_table_names())


def test_0127_creates_and_drops_the_table(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text(f"DROP TABLE {_TABLE}"))
    engine.dispose()
    assert _TABLE not in _tables(db)
    assert _alembic(["stamp", _DOWN], db).returncode == 0
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _TABLE in _tables(db)
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as c:
        c.execute(text(
            "INSERT INTO governance_rules (identifier, enforcement, body, version, status, "
            "applies_to, applies_when, created_at, updated_at) VALUES ('GVR-001', "
            "'enforced_with_override', 'b', 1, 'active', 'all', 'always', '2026-01-01', '2026-01-01')"
        ))
        c.execute(text(
            f"INSERT INTO {_TABLE} (rule_identifier, reason, created_at) "
            "VALUES ('GVR-001', 'why', '2026-01-01')"
        ))
        assert c.execute(text(f"SELECT count(*) FROM {_TABLE}")).scalar() == 1
    engine.dispose()
    down = _alembic(["downgrade", _DOWN], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _TABLE not in _tables(db)


def test_0127_is_a_no_op_on_a_create_all_db(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _alembic(["stamp", _DOWN], db).returncode == 0
    up = _alembic(["upgrade", _MIGRATION], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _TABLE in _tables(db)
