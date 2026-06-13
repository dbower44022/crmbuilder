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

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access import engagement_scope
from crmbuilder_v2.access.db import (
    bootstrap_database,
    get_engine,
    get_session_factory,
    reset_engine_cache,
)
from crmbuilder_v2.access.models import Base, EngagementRow
from crmbuilder_v2.config import get_settings, reset_settings_cache
from sqlalchemy import text

# Run the PySide6 UI tests headless by default. This conftest is imported before
# any test module imports Qt, so setting the platform here (if the environment
# has not already chosen one) reaches QApplication before it initializes — without
# it the UI tests SIGABRT (rc 134) on a machine with no display. Makes the suite
# self-sufficient instead of depending on the caller's ambient env (the gap that
# spuriously failed the ADO's PI-147 test-gate when run in a headless worktree).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The default engagement every test runs under unless it overrides the
# active-engagement context itself.
DEFAULT_ENGAGEMENT_ID = "ENG-001"
DEFAULT_ENGAGEMENT_CODE = "TESTENG"
DEFAULT_ENGAGEMENT_NAME = "Test Engagement"


# Tests that are intrinsically SQLite-specific and skipped when the suite runs
# on Postgres (D-level CI). They assert SQLite type *affinities* via reflection
# (``DATETIME``/``VARCHAR`` strings that Postgres reflects as ``TIMESTAMP`` etc.)
# — schema-shape facts the SQLite run already covers; the app *behaviour* they
# touch is exercised by the rest of the suite on Postgres. Matched by substring
# against the test function name.
_SQLITE_ONLY_NAME_SUBSTRINGS: tuple[str, ...] = (
    "_columns_with_correct_types",  # reflection asserts SQLite type affinities
)
_SQLITE_ONLY_NAMES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(config, items) -> None:  # noqa: ARG001
    """In Postgres mode, skip the intrinsically-SQLite-specific tests."""
    if not _pg_test_url():
        return
    skip = pytest.mark.skip(
        reason="SQLite-specific (schema affinity / meta-DB file); covered by the "
        "SQLite run"
    )
    for item in items:
        name = item.name.split("[")[0]
        if name in _SQLITE_ONLY_NAMES or any(
            sub in name for sub in _SQLITE_ONLY_NAME_SUBSTRINGS
        ):
            item.add_marker(skip)


def _pg_test_url() -> str | None:
    """PI-alpha: when set, run the suite against Postgres instead of SQLite.

    CI exports ``CRMBUILDER_V2_TEST_PG_URL`` pointing at a throwaway Postgres;
    unset (the default) keeps every test on a per-test SQLite file exactly as
    before. The unified row-level schema is identical across dialects, so the
    same fixtures drive both — only the per-test reset differs (a fresh SQLite
    file vs a TRUNCATE on the shared PG).
    """
    return os.environ.get("CRMBUILDER_V2_TEST_PG_URL")


# In PG mode the schema is built once per session and the engine/pool is reused
# across tests (the URL never changes) — per-test isolation is a fast per-table
# DELETE, not a fresh database. Rebuilding the pool + reflecting 41 tables every
# test would dominate runtime.
_PG_SCHEMA_READY = False


def _reset_tables_pg() -> None:
    """Clear every table + reset every sequence on the shared Postgres test DB.

    ``DELETE`` in reverse-FK order, **not** ``TRUNCATE`` — on empty/tiny tables
    DELETE is ~5 ms whereas ``TRUNCATE ... CASCADE RESTART IDENTITY`` across the
    41 FK-linked tables takes ~2.8 s (ACCESS EXCLUSIVE locks + cascade walk),
    which would dominate the whole suite. Sequences are then reset in one
    PL/pgSQL pass so surrogate ids restart at 1 each test, matching the
    fresh-SQLite-file baseline (a few tests assert exact id-derived identifiers,
    e.g. ``REF-0001``/``next == 2``).
    """
    engine = get_engine()
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.execute(
            text(
                "DO $$ DECLARE r RECORD; BEGIN "
                "FOR r IN SELECT sequence_name FROM information_schema.sequences "
                "WHERE sequence_schema = 'public' LOOP "
                "EXECUTE format('SELECT setval(%L, 1, false)', r.sequence_name); "
                "END LOOP; END $$;"
            )
        )


def _seed_default_engagement() -> None:
    """Seed ``ENG-001`` into the unified ``engagements`` table.

    This is the FK target every scoped row's ``engagement_id`` points at. The
    row is inserted directly via raw ORM.

    PI-β removed the ``current_engagement.json`` marker: API-backed tests
    resolve the engagement from the ``X-Engagement`` header (the ``client``
    fixture sends ``ENG-001``); the test body sets the scope ContextVar
    directly via ``v2_env``.
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
            engagement_created_at=now,
            engagement_updated_at=now,
        )
    )
    session.commit()
    session.close()


@pytest.fixture
def v2_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    db = tmp_path / "v2.db"
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(db))
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    # Hermetic coverage baseline: a deployment may set a durable
    # CRMBUILDER_V2_PROVENANCE_BASELINE in data/crmbuilder.env; force it empty
    # for tests (a real env var overrides the file) so the coverage report's
    # default-cutoff behavior is deterministic regardless of the local machine.
    monkeypatch.setenv("CRMBUILDER_V2_PROVENANCE_BASELINE", "")
    # PI-alpha: when a test Postgres is configured, route the engine at it
    # (``database_url`` takes precedence over ``db_path`` in ``Settings``). The
    # schema is created once and each test starts from a per-table DELETE rather
    # than a fresh file.
    pg_url = _pg_test_url()
    if pg_url:
        global _PG_SCHEMA_READY
        monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", pg_url)
        reset_settings_cache()
        # Keep the cached engine/pool across tests (URL is constant); only
        # build the schema once, then DELETE-reset between tests.
        if not _PG_SCHEMA_READY:
            reset_engine_cache()
            bootstrap_database()
            _PG_SCHEMA_READY = True
        # SQLite mode rebuilds the engine every test, so get_engine re-installs
        # the scope listeners each time — which masks any test that uninstalls
        # them (e.g. test_engagement_scope's fixture teardown). PG mode reuses
        # the engine and skips that rebuild, so re-install explicitly here
        # (idempotent) to guarantee the write-stamp/read-filter are present
        # regardless of what a prior test did to the base Session class.
        engagement_scope.install_engagement_scope()
        _reset_tables_pg()
    else:
        reset_settings_cache()
        reset_engine_cache()
        bootstrap_database()
    _seed_default_engagement()
    # Activate scoping for the test body: the write-stamp fills engagement_id
    # on every insert; enforcement fails loud on an unscoped scoped op.
    token = engagement_scope.set_active_engagement(DEFAULT_ENGAGEMENT_ID)
    prev_enforce = engagement_scope.set_enforcement(True)
    try:
        yield tmp_path
    finally:
        engagement_scope.set_enforcement(prev_enforce)
        engagement_scope.reset_active_engagement(token)
        # In PG mode keep the engine/pool alive across tests (URL is constant);
        # disposing + rebuilding it per test would dominate runtime.
        if not pg_url:
            reset_engine_cache()
        reset_settings_cache()


@pytest.fixture
def settings(v2_env):
    return get_settings()


@pytest.fixture
def export_dir(v2_env: Path) -> Path:
    # PI-β slice 4 removed the JSON-snapshot exporter; this is now just an
    # empty per-test directory retained for tests that take it as a scratch
    # path. (Tests that asserted exported snapshot files were removed.)
    d = v2_env / "db-export"
    d.mkdir(parents=True, exist_ok=True)
    return d
