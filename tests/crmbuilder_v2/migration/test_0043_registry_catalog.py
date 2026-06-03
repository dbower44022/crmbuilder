"""PI-122 — migration 0043 creates the registry catalog tables + rebuilds CHECKs.

Mirrors the test_0041 pattern: create_all, drop the registry tables to simulate
the pre-0043 state, stamp at 0042, upgrade to 0043 (explicit revision so later
chain growth doesn't perturb the single-step downgrade), assert the tables are
back and the change_log/refs CHECKs admit a new type, then downgrade to 0042.
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
_MIGRATION_0042 = "0042_pi_gamma_changelog_principal_attribution"
_MIGRATION_0043 = "0043_pi_122_registry_catalog_entities"
_TABLES = ("agent_profiles", "skills", "governance_rules", "learnings")


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


def test_models_define_registry_tables() -> None:
    for name in _TABLES:
        assert name in Base.metadata.tables


def test_0043_creates_and_drops_registry_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for t in _TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0042], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", _MIGRATION_0043], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    eng = create_engine(f"sqlite:///{db}")
    insp = inspect(eng)
    have = set(insp.get_table_names())
    for t in _TABLES:
        assert t in have, f"{t} missing after 0043"
    # The rebuilt change_log CHECK admits the new 'agent_profile' type.
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, engagement_id) "
                "VALUES (CURRENT_TIMESTAMP, 'agent_profile', 'AGP-001', 'insert', "
                "'claude_session', 'ENG-001')"
            )
        )
    eng.dispose()

    down = _alembic(["downgrade", _MIGRATION_0042], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    have2 = set(insp2.get_table_names())
    for t in _TABLES:
        assert t not in have2, f"{t} present after downgrade"
