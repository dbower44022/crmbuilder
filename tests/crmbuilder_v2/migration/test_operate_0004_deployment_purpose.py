"""PI-577 — ``operate_0004_deployment_purpose`` adds ``deployment_purpose`` to
``deployments``: NOT NULL, CHECK-constrained to client_own or demo_test,
back-filled to client_own for rows that predate it, re-runnable, dropped by
the downgrade."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    plain_url,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_PREVIOUS = "operate_0003_deployments"
_COLUMN = "deployment_purpose"


def _columns(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return {c["name"] for c in inspect(eng).get_columns("deployments")}
    finally:
        eng.dispose()


def _exec(db: str, sql: str, **params):
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            return c.execute(text(sql), params).all() if sql.lstrip().upper().startswith("SELECT") else c.execute(text(sql), params)
    finally:
        eng.dispose()


_ROW = (
    "INSERT INTO deployments (deployment_identifier, deployment_application, "
    "deployment_client, deployment_hosting_provider, deployment_name, "
    "deployment_status, {extra_cols}deployment_created_at, deployment_updated_at) VALUES "
    "(:i, 'ENG-001', 'CLI-001', 'digitalocean', :i, 'active', {extra_vals}NOW(), NOW())"
)


def test_add_backfill_check_rerun_and_drop() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _COLUMN in _columns(db)
    assert stamp_heads(db).returncode == 0

    down = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _COLUMN not in _columns(db)

    live = plain_url(db)
    _exec(
        live,
        "INSERT INTO engagements (engagement_identifier, engagement_code, "
        "engagement_name, engagement_purpose, engagement_status, "
        "engagement_created_at, engagement_updated_at) VALUES "
        "('ENG-001', 'ENG001', 'Engagement', 'p', 'active', NOW(), NOW())",
    )
    _exec(
        live,
        "INSERT INTO clients (client_identifier, client_name, client_status, "
        "client_created_at, client_updated_at) VALUES "
        "('CLI-001', 'Cleveland', 'active', NOW(), NOW())",
    )
    _exec(live, _ROW.format(extra_cols="", extra_vals=""), i="DPL-001")

    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _COLUMN in _columns(db)
    rows = _exec(live, "SELECT deployment_identifier, deployment_purpose FROM deployments")
    assert rows == [("DPL-001", "client_own")]

    again = _alembic(["upgrade", "heads"], db)
    assert again.returncode == 0

    _exec(
        live,
        _ROW.format(extra_cols="deployment_purpose, ", extra_vals="'demo_test', "),
        i="DPL-002",
    )
    with pytest.raises(IntegrityError):
        _exec(
            live,
            _ROW.format(extra_cols="deployment_purpose, ", extra_vals="'staging', "),
            i="DPL-003",
        )

    down2 = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down2.returncode == 0, f"downgrade failed:\n{down2.stdout}\n{down2.stderr}"
    assert _COLUMN not in _columns(db)
