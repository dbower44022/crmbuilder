"""PI-γ — migration 0041 creates principals / api_tokens / role_assignments.

CI-safe, mirroring the test_0038 pattern (no decommissioned catalog YAMLs):

- ``test_models_define_rbac_tables`` — the three RBAC tables exist on the ORM
  metadata and are system/shared (no ``engagement_id`` discriminator).
- ``test_0041_creates_and_drops_rbac_tables`` — build the full schema via
  ``create_all``, drop the three RBAC tables to simulate the pre-0041 state,
  stamp at 0040, ``upgrade head`` (runs only 0041), assert the tables are back,
  then downgrade and assert they are gone.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from crmbuilder_v2.access.models import (
    ApiTokenRow,
    Base,
    EngagementScopedMixin,
    PrincipalRow,
    RoleAssignmentRow,
)
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ALEMBIC_DIR = _REPO_ROOT / "crmbuilder-v2"
_MIGRATION_0040 = "0040_pi_beta_drop_engagement_export_dir"
_RBAC_TABLES = ("role_assignments", "api_tokens", "principals")


def test_models_define_rbac_tables() -> None:
    tables = Base.metadata.tables
    for name in _RBAC_TABLES:
        assert name in tables, f"{name} missing from ORM metadata"
    # System/shared tables: none are EngagementScopedMixin subclasses, so the
    # row-level scope filter/stamp never touches them. (role_assignments does
    # carry an ``engagement_id`` *FK* — the engagement a role is granted on —
    # but it is a plain Base, not a scoped row.)
    for model in (PrincipalRow, ApiTokenRow, RoleAssignmentRow):
        assert not issubclass(model, EngagementScopedMixin), model.__name__
    assert "engagement_id" not in tables["principals"].c
    assert "engagement_id" not in tables["api_tokens"].c


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


def test_0041_creates_and_drops_rbac_tables(tmp_path: Path) -> None:
    db = tmp_path / "v2.db"
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    # Drop the RBAC tables to simulate the pre-0041 state (FK-safe order).
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        for t in _RBAC_TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0040], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    up = _alembic(["upgrade", "head"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    insp = inspect(create_engine(f"sqlite:///{db}"))
    have = set(insp.get_table_names())
    for t in _RBAC_TABLES:
        assert t in have, f"{t} missing after 0041"
    # Columns match the models.
    principal_cols = {c["name"] for c in insp.get_columns("principals")}
    assert {"principal_id", "kind", "identity", "status"} <= principal_cols
    token_cols = {c["name"] for c in insp.get_columns("api_tokens")}
    assert {"token_id", "principal_id", "token_hash"} <= token_cols

    down = _alembic(["downgrade", "-1"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(f"sqlite:///{db}"))
    have2 = set(insp2.get_table_names())
    for t in _RBAC_TABLES:
        assert t not in have2, f"{t} present after downgrade"
