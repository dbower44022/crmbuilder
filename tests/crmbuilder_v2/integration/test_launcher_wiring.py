"""Regression tests for the v0.5 slice A launcher wiring.

Slice A landed the meta DB Alembic chain, the ``bootstrap_meta_db()``
helper, the ``needs_migration()`` detector, and the
``run_dogfood_migration()`` module — but the launcher integration that
invokes them at app startup was never wired. The result on Doug's
machine after slice A was a half-migrated state: the API restarted but
``engagements.db`` was never created (no startup call to
``bootstrap_meta_db()``); the desktop launched but the dogfood
migration was never triggered (no startup call to
``run_dogfood_migration()``).

This module pins the wiring so a future regression cannot reintroduce
that gap:

* :func:`test_api_startup_creates_meta_db` — constructing the FastAPI
  app via :func:`create_app` must leave ``engagements.db`` on disk with
  the meta schema applied.
* :func:`test_desktop_launcher_runs_migration_when_needed` — the
  ``_run_dogfood_migration_if_needed`` helper invoked from
  :func:`crmbuilder_v2.ui.app.main` must detect the v0.4 state and run
  the dogfood migration before the rest of the launcher proceeds.
* :func:`test_desktop_launcher_is_noop_when_already_migrated` — the
  helper must short-circuit on an already-migrated state.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

import pytest
from crmbuilder_v2.access.db import reset_engine_cache
from crmbuilder_v2.access.engagement import list_engagements_in_meta
from crmbuilder_v2.access.meta_db import (
    meta_db_path,
    reset_meta_engine_cache,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.app import (
    _route_api_at_active_engagement,
    _run_dogfood_migration_if_needed,
)


@pytest.fixture
def v0_4_state_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Construct a workspace mirroring a v0.4 install before launching v0.5.

    Sets ``CRMBUILDER_V2_DB_PATH`` to a freshly-seeded ``v2.db`` that
    carries the minimum row shapes the dogfood migration's row-count
    verifier checks. The meta DB is intentionally absent so
    ``needs_migration()`` reports True.
    """
    data = tmp_path / "crmbuilder-v2" / "data"
    data.mkdir(parents=True)
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(data / "v2.db"))
    monkeypatch.setenv(
        "CRMBUILDER_V2_EXPORT_DIR", str(tmp_path / "exports")
    )

    from crmbuilder_v2.access import meta_exporter

    monkeypatch.setattr(
        meta_exporter,
        "meta_export_dir",
        lambda: tmp_path / "test-meta-export",
    )

    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()

    db = data / "v2.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(
            """
            CREATE TABLE sessions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE decisions (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE planning_items (id INTEGER PRIMARY KEY, identifier TEXT);
            CREATE TABLE change_log (id INTEGER PRIMARY KEY);
            CREATE TABLE charter (id INTEGER PRIMARY KEY);
            CREATE TABLE status (id INTEGER PRIMARY KEY);
            CREATE TABLE risks (id INTEGER PRIMARY KEY);
            CREATE TABLE topics (id INTEGER PRIMARY KEY);
            CREATE TABLE refs (id INTEGER PRIMARY KEY);
            CREATE TABLE domains (domain_identifier TEXT PRIMARY KEY);
            CREATE TABLE entities (entity_identifier TEXT PRIMARY KEY);
            CREATE TABLE processes (process_identifier TEXT PRIMARY KEY);
            CREATE TABLE crm_candidates (crm_candidate_identifier TEXT PRIMARY KEY);
            INSERT INTO sessions(identifier) VALUES ('SES-001');
            INSERT INTO decisions(identifier) VALUES ('DEC-001'), ('DEC-002');
            """
        )
        conn.commit()
    finally:
        conn.close()

    yield data
    reset_meta_engine_cache()
    reset_engine_cache()
    reset_settings_cache()


def test_api_startup_creates_meta_db(v0_4_state_workspace: Path) -> None:
    """Constructing the FastAPI app must materialise ``engagements.db``.

    Regression for the slice A defect where ``bootstrap_meta_db()`` was
    never called at API startup, leaving ``engagements.db`` absent and
    causing ``/engagements`` to 404.
    """
    data = v0_4_state_workspace
    assert not (data / "engagements.db").exists(), (
        "pre-state: meta DB must be absent so the test exercises the "
        "startup-hook code path"
    )

    create_app()

    assert (data / "engagements.db").exists(), (
        "bootstrap_meta_db() must have created the meta DB during "
        "create_app() startup"
    )
    assert meta_db_path() == data / "engagements.db"


def test_desktop_launcher_runs_migration_when_needed(
    qapp, v0_4_state_workspace: Path
) -> None:
    """``_run_dogfood_migration_if_needed`` must run the migration on a
    v0.4 state and leave the install in the v0.5 post-migration shape.
    """
    data = v0_4_state_workspace

    ok = _run_dogfood_migration_if_needed(
        logging.getLogger("test.launcher_wiring")
    )

    assert ok, "migration helper reported failure on a clean v0.4 state"
    assert not (data / "v2.db").exists(), (
        "v2.db must be removed after a successful migration"
    )
    assert (data / "v2.db.pre-v0.5-backup").exists(), (
        "the .pre-v0.5-backup file is the recovery point and must persist"
    )
    assert (data / "engagements.db").exists()
    assert engagement_db_path("CRMBUILDER").exists()

    current = json.loads((data / "current_engagement.json").read_text())
    assert current["engagement_code"] == "CRMBUILDER"
    assert current["engagement_identifier"] == "ENG-001"

    engagements = list_engagements_in_meta()
    assert len(engagements) == 1
    assert engagements[0].engagement_code == "CRMBUILDER"


def test_desktop_launcher_is_noop_when_already_migrated(
    qapp, v0_4_state_workspace: Path
) -> None:
    """A second invocation of the launcher helper must be a no-op.

    Guards against double-runs writing duplicate engagement rows or
    re-copying ``v2.db`` after the migration has already completed.
    """
    log = logging.getLogger("test.launcher_wiring")

    assert _run_dogfood_migration_if_needed(log) is True
    snapshot_size = engagement_db_path("CRMBUILDER").stat().st_size

    assert _run_dogfood_migration_if_needed(log) is True

    engagements = list_engagements_in_meta()
    assert len(engagements) == 1, (
        "re-running the launcher helper must not insert a second row"
    )
    assert engagement_db_path("CRMBUILDER").stat().st_size == snapshot_size


def test_route_api_at_active_engagement_sets_env(
    qapp, v0_4_state_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_route_api_at_active_engagement`` must point CRMBUILDER_V2_DB_PATH
    at the active engagement's per-engagement DB so a fresh API spawn
    inherits the correct path.

    Regression for the slice D gap where an externally-running API (or
    a UI-spawned API at first launch with no prior activation) reads
    from the default ``data/v2.db`` and 500s every per-engagement query
    because that file is either absent or lazy-created empty.
    """
    data = v0_4_state_workspace
    log = logging.getLogger("test.launcher_wiring.route")

    assert _run_dogfood_migration_if_needed(log) is True

    active = ActiveEngagementContext()
    active.load_from_disk()
    assert active.engagement_code() == "CRMBUILDER"

    _route_api_at_active_engagement(active, log)

    expected = data / "engagements" / "CRMBUILDER.db"
    assert os.environ["CRMBUILDER_V2_DB_PATH"] == str(expected)

    # Settings cache reset means subsequent get_settings sees the new
    # value, and the canonical data dir still resolves correctly.
    from crmbuilder_v2.access.meta_db import data_dir, meta_db_path
    from crmbuilder_v2.config import get_settings

    assert get_settings().db_path == expected
    assert data_dir() == data
    assert meta_db_path() == data / "engagements.db"


def test_route_api_at_active_engagement_noop_without_active(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No-op when ``current_engagement.json`` resolves to no engagement.

    Fresh-install case: no active engagement yet, the env var must be
    left alone so the empty meta DB stays canonically resolvable.
    """
    monkeypatch.delenv("CRMBUILDER_V2_DB_PATH", raising=False)
    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()

    active = ActiveEngagementContext()
    # No load_from_disk; engagement stays None.

    _route_api_at_active_engagement(
        active, logging.getLogger("test.launcher_wiring.route.noop")
    )

    assert "CRMBUILDER_V2_DB_PATH" not in os.environ
