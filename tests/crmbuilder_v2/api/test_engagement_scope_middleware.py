"""PI-123 Slice 2c — per-request engagement-scope middleware + resolver.

Covers the resolver (code / identifier / marker / unknown), the middleware's
ContextVar set+reset (flag on) and pass-through (flag off), and an end-to-end
API filtering test: with scoping enabled, ``GET /references`` returns only the
rows of the engagement named by ``X-Engagement``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access import engagement_scope
from crmbuilder_v2.access.db import (
    bootstrap_database,
    get_session_factory,
    reset_engine_cache,
)
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.models import EngagementRow, Reference
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.scope_middleware import (
    EngagementScopeMiddleware,
    resolve_engagement_identifier,
)
from crmbuilder_v2.config import reset_settings_cache
from fastapi.testclient import TestClient


def _seed_two_engagements() -> None:
    # PI-123: seed the unified DB's engagements table (the resolver's registry
    # source), inserting EngagementRow directly — NOT engagement_repo, whose
    # snapshot refresh writes the git-tracked db-export/meta/ path.
    factory = get_session_factory()
    s = factory()
    now = datetime.now(UTC)
    for ident, code, name in [
        ("ENG-001", "ALPHA", "Alpha"),
        ("ENG-002", "BETA", "Beta"),
    ]:
        s.add(
            EngagementRow(
                engagement_identifier=ident,
                engagement_code=code,
                engagement_name=name,
                engagement_purpose="p",
                engagement_status="active",
                engagement_created_at=now,
                engagement_updated_at=now,
            )
        )
    s.commit()
    s.close()


@pytest.fixture
def scoped_env(tmp_path: Path, monkeypatch):
    """A unified DB with scoping enabled and ALPHA/BETA seeded in the registry.

    Self-contained (not built on ``v2_env``) so it controls its own
    active-engagement/enforcement state: these middleware tests exercise the
    *resolution* path from a clean slate (no active engagement set, enforcement
    off, so the no-header dormant case still returns all rows)."""
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    export = tmp_path / "db-export"
    export.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(export))
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    reset_settings_cache()
    reset_engine_cache()
    bootstrap_database()
    _seed_two_engagements()
    # No active engagement and enforcement off: these tests drive resolution
    # explicitly and rely on the dormant (no-active) behaviour for the
    # no-header case.
    engagement_scope.set_active_engagement(None)
    prev_enforce = engagement_scope.set_enforcement(False)
    try:
        yield tmp_path
    finally:
        engagement_scope.set_enforcement(prev_enforce)
        reset_engine_cache()
        reset_settings_cache()


def _ref(source_id, target_id, engagement_id):
    return Reference(
        source_type="session",
        source_id=source_id,
        target_type="session",
        target_id=target_id,
        relationship_kind="references",
        engagement_id=engagement_id,
    )


def _seed_refs() -> None:
    factory = get_session_factory()
    s = factory()
    s.add_all(
        [
            _ref("SES-001", "SES-002", "ENG-001"),
            _ref("SES-003", "SES-004", "ENG-001"),
            _ref("SES-010", "SES-011", "ENG-002"),
        ]
    )
    s.commit()
    s.close()


# --------------------------------------------------------------------------
# Resolver
# --------------------------------------------------------------------------
def test_resolver_by_code(scoped_env):
    assert resolve_engagement_identifier("ALPHA") == "ENG-001"
    assert resolve_engagement_identifier("beta") == "ENG-002"  # case-insensitive


def test_resolver_by_identifier(scoped_env):
    assert resolve_engagement_identifier("ENG-002") == "ENG-002"


def test_resolver_unknown_is_none(scoped_env):
    assert resolve_engagement_identifier("NOPE") is None


def test_resolver_none_without_header_or_marker(scoped_env):
    # No X-Engagement and no current_engagement.json marker in the test env.
    assert resolve_engagement_identifier(None) is None


# --------------------------------------------------------------------------
# Middleware ContextVar behaviour
# --------------------------------------------------------------------------
async def _run_middleware(header_value: str | None):
    seen = {}

    async def dummy_app(scope, receive, send):
        seen["active"] = get_active_engagement()

    headers = [(b"x-engagement", header_value.encode())] if header_value else []
    mw = EngagementScopeMiddleware(dummy_app)
    await mw({"type": "http", "headers": headers}, None, None)
    return seen.get("active")


async def test_middleware_sets_and_resets_contextvar(scoped_env):
    assert get_active_engagement() is None
    seen = await _run_middleware("ALPHA")
    assert seen == "ENG-001"  # set during the request
    assert get_active_engagement() is None  # reset after


async def test_middleware_passthrough_when_disabled(scoped_env, monkeypatch):
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "false")
    reset_settings_cache()
    seen = await _run_middleware("ALPHA")
    assert seen is None  # flag off → middleware sets nothing


# --------------------------------------------------------------------------
# End-to-end API filtering
# --------------------------------------------------------------------------
def test_get_references_filtered_by_x_engagement(scoped_env):
    _seed_refs()
    client = TestClient(create_app())

    r_alpha = client.get("/references", headers={"X-Engagement": "ALPHA"})
    assert r_alpha.status_code == 200
    assert len(r_alpha.json()["data"]) == 2

    r_beta = client.get("/references", headers={"X-Engagement": "BETA"})
    assert len(r_beta.json()["data"]) == 1

    # Identifier form of the header resolves the same way.
    r_ident = client.get("/references", headers={"X-Engagement": "ENG-001"})
    assert len(r_ident.json()["data"]) == 2


def test_get_references_unscoped_without_header_returns_all(scoped_env):
    """No header + no marker → dormant (enforcement is a later cutover step)."""
    _seed_refs()
    client = TestClient(create_app())
    r = client.get("/references")
    assert r.status_code == 200
    assert len(r.json()["data"]) == 3
