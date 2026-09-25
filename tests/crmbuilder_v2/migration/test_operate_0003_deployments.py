"""PI-576 — ``operate_0003_deployments`` creates ``deployments`` and adds the
deployment link to ``deploy_runs`` and ``provider_credentials``, replacing the
credential table's per-provider uniqueness with a per-scope one. Bootstrap-safe
(create_all + stamp passes through), re-runnable, and the downgrade refuses
while a credential is scoped to a deployment."""

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

_PREVIOUS = "operate_0002_deploy_needs_action"


def _columns(db: str, table: str) -> set[str]:
    eng = create_engine(db)
    try:
        return {c["name"] for c in inspect(eng).get_columns(table)}
    finally:
        eng.dispose()


def _tables(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def _uniques(db: str, table: str) -> set[str]:
    eng = create_engine(db)
    try:
        return {u["name"] for u in inspect(eng).get_unique_constraints(table)}
    finally:
        eng.dispose()


def _exec(db: str, sql: str, **params) -> None:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(text(sql), params)
    finally:
        eng.dispose()


def _seed(db: str) -> None:
    _exec(
        db,
        "INSERT INTO engagements (engagement_identifier, engagement_code, "
        "engagement_name, engagement_purpose, engagement_status, "
        "engagement_created_at, engagement_updated_at) VALUES "
        "('ENG-001', 'ENG001', 'Engagement', 'p', 'active', NOW(), NOW())",
    )
    _exec(
        db,
        "INSERT INTO clients (client_identifier, client_name, client_status, "
        "client_created_at, client_updated_at) VALUES "
        "('CLI-001', 'Cleveland', 'active', NOW(), NOW())",
    )


def test_create_link_rescope_rerun_and_refused_downgrade() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert "deployments" in _tables(db)
    assert stamp_heads(db).returncode == 0

    # Downgrade the operate branch one step: table and columns go, the old
    # uniqueness rule returns.
    down = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert "deployments" not in _tables(db)
    assert "deployment_identifier" not in _columns(db, "deploy_runs")
    assert "deployment_identifier" not in _columns(db, "provider_credentials")
    assert "uq_provider_credential_provider" in _uniques(db, "provider_credentials")

    _seed(db)
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert "deployments" in _tables(db)
    assert "deployment_identifier" in _columns(db, "deploy_runs")
    assert "deployment_identifier" in _columns(db, "provider_credentials")
    assert "uq_provider_credential_provider" not in _uniques(db, "provider_credentials")

    # Re-running is a no-op.
    again = _alembic(["upgrade", "heads"], db)
    assert again.returncode == 0

    # The identifier format and the vocabularies are enforced.
    live = plain_url(db)
    _exec(
        live,
        "INSERT INTO deployments (deployment_identifier, deployment_application, "
        "deployment_client, deployment_hosting_provider, deployment_name, "
        "deployment_status, deployment_created_at, deployment_updated_at) VALUES "
        "('DPL-001', 'ENG-001', 'CLI-001', 'digitalocean', 'Cleveland', 'active', "
        "NOW(), NOW())",
    )
    with pytest.raises(IntegrityError):
        _exec(
            live,
            "INSERT INTO deployments (deployment_identifier, deployment_application, "
            "deployment_client, deployment_hosting_provider, deployment_name, "
            "deployment_status, deployment_created_at, deployment_updated_at) VALUES "
            "('INST-002', 'ENG-001', 'CLI-001', 'digitalocean', 'Bad', 'active', "
            "NOW(), NOW())",
        )
    with pytest.raises(IntegrityError):
        _exec(
            live,
            "INSERT INTO deployments (deployment_identifier, deployment_application, "
            "deployment_client, deployment_hosting_provider, deployment_name, "
            "deployment_status, deployment_created_at, deployment_updated_at) VALUES "
            "('DPL-002', 'ENG-001', 'CLI-001', 'aws', 'Bad', 'active', NOW(), NOW())",
        )

    # One application-level row per provider, plus one per deployment.
    cred = (
        "INSERT INTO provider_credentials (engagement_id, provider, token_ref, "
        "deployment_identifier, created_at, updated_at) VALUES "
        "('ENG-001', 'digitalocean', :ref, :dpl, NOW(), NOW())"
    )
    _exec(live, cred, ref="crmbuilder:a", dpl=None)
    _exec(live, cred, ref="crmbuilder:b", dpl="DPL-001")
    with pytest.raises(IntegrityError):
        _exec(live, cred, ref="crmbuilder:c", dpl=None)
    with pytest.raises(IntegrityError):
        _exec(live, cred, ref="crmbuilder:d", dpl="DPL-001")

    # A run may point at the deployment it built.
    _exec(
        live,
        "INSERT INTO deploy_runs (engagement_id, deploy_run_identifier, "
        "deploy_run_status, deployment_identifier, created_at, updated_at) VALUES "
        "('ENG-001', 'DEP-001', 'queued', 'DPL-001', NOW(), NOW())",
    )

    # The downgrade refuses while a credential is scoped to a deployment ...
    refused = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert refused.returncode != 0
    assert "scoped to a deployment" in (refused.stdout + refused.stderr)
    assert "deployments" in _tables(db)

    # ... and proceeds once that row is gone.
    _exec(live, "DELETE FROM provider_credentials WHERE deployment_identifier IS NOT NULL")
    down2 = _alembic(["downgrade", f"operate@{_PREVIOUS}"], db)
    assert down2.returncode == 0, f"downgrade failed:\n{down2.stdout}\n{down2.stderr}"
    assert "deployments" not in _tables(db)
    assert "deployment_identifier" not in _columns(db, "deploy_runs")
