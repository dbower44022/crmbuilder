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

from crmbuilder_v2.access.models import (
    ApiTokenRow,
    Base,
    EngagementScopedMixin,
    PrincipalRow,
    RoleAssignmentRow,
)
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_0040 = "0002_drop_engagement_export_dir"
_MIGRATION_0041 = "0003_pi_gamma_principals_tokens_roles"
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




def test_0041_creates_and_drops_rbac_tables() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    # Drop the RBAC tables to simulate the pre-0041 state (FK-safe order).
    with engine.begin() as c:
        c.execute(text("SET session_replication_role = replica"))
        for t in _RBAC_TABLES:
            c.execute(text(f"DROP TABLE IF EXISTS {t}"))
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_0040], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    # Upgrade to exactly 0041 (not head) so later revisions don't interfere
    # with the single-step downgrade assertion below.
    up = _alembic(["upgrade", _MIGRATION_0041], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"

    insp = inspect(create_engine(db))
    have = set(insp.get_table_names())
    for t in _RBAC_TABLES:
        assert t in have, f"{t} missing after 0041"
    # Columns match the models.
    principal_cols = {c["name"] for c in insp.get_columns("principals")}
    assert {"principal_id", "kind", "identity", "status"} <= principal_cols
    token_cols = {c["name"] for c in insp.get_columns("api_tokens")}
    assert {"token_id", "principal_id", "token_hash"} <= token_cols

    down = _alembic(["downgrade", _MIGRATION_0040], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    insp2 = inspect(create_engine(db))
    have2 = set(insp2.get_table_names())
    for t in _RBAC_TABLES:
        assert t not in have2, f"{t} present after downgrade"
