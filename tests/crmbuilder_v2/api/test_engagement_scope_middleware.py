"""PI-123 Slice 2c — per-request engagement-scope middleware + resolver.

Covers the resolver (code / identifier / marker / unknown), the middleware's
ContextVar set+reset (flag on) and pass-through (flag off), and an end-to-end
API filtering test: with scoping enabled, ``GET /references`` returns only the
rows of the engagement named by ``X-Engagement``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import meta_db
from crmbuilder_v2.access.db import get_session_factory, reset_engine_cache
from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.meta_models import EngagementRow
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.scope_middleware import (
    EngagementScopeMiddleware,
    resolve_engagement_identifier,
)
from crmbuilder_v2.config import reset_settings_cache
from fastapi.testclient import TestClient


def _seed_two_engagements() -> None:
    # Insert directly via the meta session — NOT engagement_repo.create_engagement,
    # whose snapshot refresh (write_engagements_snapshot) writes to the real
    # repo db-export/meta/ path (meta_export_dir is hardcoded, not the test
    # export dir), polluting a git-tracked file. Mirrors test_two_database_routing.
    meta_db.reset_meta_engine_cache()
    meta_db.bootstrap_meta_db()
    factory = meta_db.get_meta_session_factory()
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
def scoped_env(v2_env, monkeypatch):
    """v2_env + scoping enabled + two engagements seeded in the meta DB."""
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    reset_settings_cache()
    reset_engine_cache()
    _seed_two_engagements()
    yield v2_env
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


async def test_middleware_passthrough_when_disabled(v2_env, monkeypatch):
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
