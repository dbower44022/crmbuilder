"""Shared pytest fixtures for crmbuilder_v2.

Each test gets a fresh SQLite database file and an isolated JSON-export
directory. Settings and engine caches are reset so that environment
variables set by the fixture propagate.

**PI-123 Stage 2 — active engagement scoping.** The unified multi-engagement
DB makes ``engagement_id`` ``NOT NULL`` on every scoped row, so the test
fixtures run with row-level scoping *enabled* and an active engagement set:

* ``CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED=true`` installs the central
  read-filter / write-stamp on the session factory (``access/db.py``).
* a single default engagement (``ENG-001``) is seeded in **both** the unified
  ``engagements`` table (the FK target every stamped row points at) and the
  legacy meta DB (the registry the request-scope middleware still resolves
  against until the cutover), plus a ``current_engagement.json`` marker so the
  API middleware resolves it with no per-request header.
* the active engagement is set on the ``engagement_scope`` ContextVar and
  enforcement is turned on, so a scoped read/write with no active engagement
  fails loud. The write-stamp fills ``engagement_id=ENG-001`` on every insert,
  so the vast majority of tests construct governance/methodology rows exactly
  as before — the discriminator is supplied centrally.

Tests that need *multiple* engagements (cross-engagement isolation, the
collision-coexistence proof, the consolidation harness) override the active
engagement themselves with ``engagement_scope.active_engagement(...)``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access import engagement_scope
from crmbuilder_v2.access.db import (
    bootstrap_database,
    force_export,
    get_session_factory,
    reset_engine_cache,
)
from crmbuilder_v2.access.models import EngagementRow
from crmbuilder_v2.config import get_settings, reset_settings_cache

# The default engagement every test runs under unless it overrides the
# active-engagement context itself.
DEFAULT_ENGAGEMENT_ID = "ENG-001"
DEFAULT_ENGAGEMENT_CODE = "TESTENG"
DEFAULT_ENGAGEMENT_NAME = "Test Engagement"


def _seed_default_engagement(export_dir: Path) -> None:
    """Seed ``ENG-001`` into the unified ``engagements`` table.

    This is the FK target every scoped row's ``engagement_id`` points at. The
    row is inserted directly (never ``engagement_repo`` — whose snapshot
    refresh writes the git-tracked ``db-export/meta/`` file at the hardcoded
    repo path; see ``test_engagement_scope_middleware``).

    Also writes the ``current_engagement.json`` marker so the request-scope
    middleware's no-header fallback resolves this engagement (the scope resolver
    reads the unified ``engagements`` table seeded here). This makes every
    API-backed test — including the UI panels' ``StorageClient``-over-TestClient
    fixtures, which send no ``X-Engagement`` header — resolve the default
    engagement, mirroring how the desktop app's marker drives it in production.
    """
    now = datetime.now(UTC)
    factory = get_session_factory()
    session = factory()
    session.add(
        EngagementRow(
            engagement_identifier=DEFAULT_ENGAGEMENT_ID,
            engagement_code=DEFAULT_ENGAGEMENT_CODE,
            engagement_name=DEFAULT_ENGAGEMENT_NAME,
            engagement_purpose="test",
            engagement_status="active",
            engagement_export_dir=str(export_dir),
            engagement_created_at=now,
            engagement_updated_at=now,
        )
    )
    session.commit()
    session.close()

    # Marker: data_dir() resolves to db_path.parent in tests; the resolver reads
    # ``<data_dir>/current_engagement.json`` as the no-header fallback.
    marker = get_settings().db_path.parent / "current_engagement.json"
    marker.write_text(
        json.dumps(
            {
                "engagement_code": DEFAULT_ENGAGEMENT_CODE,
                "engagement_identifier": DEFAULT_ENGAGEMENT_ID,
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def v2_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "v2.db"
    export = tmp_path / "db-export"
    # The export-write gate (DEC-114) requires the configured root to
    # exist on disk; create it before any export runs.
    export.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(db))
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(export))
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    reset_settings_cache()
    reset_engine_cache()
    bootstrap_database()
    _seed_default_engagement(export)
    # Activate scoping for the test body: the write-stamp fills engagement_id
    # on every insert; enforcement fails loud on an unscoped scoped op.
    token = engagement_scope.set_active_engagement(DEFAULT_ENGAGEMENT_ID)
    prev_enforce = engagement_scope.set_enforcement(True)
    force_export()
    try:
        yield tmp_path
    finally:
        engagement_scope.set_enforcement(prev_enforce)
        engagement_scope.reset_active_engagement(token)
        reset_engine_cache()
        reset_settings_cache()


@pytest.fixture
def settings(v2_env):
    return get_settings()


@pytest.fixture
def export_dir(v2_env: Path) -> Path:
    return v2_env / "db-export"
