"""PI-308 / REQ-343 — migration-drift detection + honest schema-apply.

Covers the honest ``bootstrap_database`` (un-stamped DB -> create_all+stamp;
stamped DB -> upgrade), the ``assert_schema_current`` drift gate, and
``run_api``'s refuse-to-serve-on-drift behaviour — against Postgres, the one
migration chain since PI-503 (REQ-593 / DEC-1082). The SQLite-facing parts
now assert the refusal: bootstrap and the API start path turn a SQLite URL
away with a message naming the local dev container.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.script import ScriptDirectory
from crmbuilder_v2.access.db import (
    bootstrap_database,
    reset_engine_cache,
)
from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.version_info import (
    LOCAL_POSTGRES_CONTAINER,
    SchemaDriftError,
    SqliteRefusedError,
    assert_schema_current,
    make_alembic_config,
    refuse_sqlite,
    schema_version,
)
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    plain_url,
    requires_postgres,
)


def _point_settings(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    """Force the configured unified DB at ``url`` for this test."""
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", url)
    reset_settings_cache()
    reset_engine_cache()


@pytest.fixture
def pg_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A wiped migrations database, configured as the unified DB."""
    url = plain_url(fresh_db())
    _point_settings(monkeypatch, url)
    try:
        yield url
    finally:
        reset_engine_cache()
        reset_settings_cache()


# --------------------------------------------------------------------------
# Part 0 — one chain, and the SQLite refusal
# --------------------------------------------------------------------------


def test_make_alembic_config_points_at_the_postgres_tree() -> None:
    # Whatever the URL, the environment is the Postgres tree: there is no
    # other chain to resolve a head from (the PI-308 dialect switch is gone).
    for url in ("sqlite:////tmp/x.db", "postgresql+psycopg://u@h/d"):
        cfg = make_alembic_config(url)
        assert cfg.get_main_option("script_location").endswith("migrations/pg")


def test_refuse_sqlite_names_the_dev_container() -> None:
    with pytest.raises(SqliteRefusedError) as ei:
        refuse_sqlite("sqlite:////tmp/x.db", "probe")
    message = str(ei.value)
    assert "probe" in message
    assert LOCAL_POSTGRES_CONTAINER in message
    assert "docker compose -f crmbuilder-v2/docker-compose.dev.yml up -d" in message
    refuse_sqlite("postgresql+psycopg://u@h/d", "probe")  # no raise


def test_bootstrap_refuses_a_sqlite_url(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", "")
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    reset_settings_cache()
    reset_engine_cache()
    try:
        with pytest.raises(SqliteRefusedError):
            bootstrap_database()
        assert not (tmp_path / "v2.db").exists()
    finally:
        reset_engine_cache()
        reset_settings_cache()


def test_run_api_refuses_a_sqlite_url(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("CRMBUILDER_V2_DATABASE_URL", "")
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2.db"))
    reset_settings_cache()
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-api", "--check-only"])
    from crmbuilder_v2 import cli

    try:
        with pytest.raises(SystemExit) as ei:
            cli.run_api()
    finally:
        reset_settings_cache()
    assert ei.value.code == 2  # _fail_loud exits 2 before any uvicorn start
    assert LOCAL_POSTGRES_CONTAINER in capsys.readouterr().err


# --------------------------------------------------------------------------
# Part 1 — honest bootstrap_database (Postgres)
# --------------------------------------------------------------------------


@requires_postgres
def test_bootstrap_fresh_db_creates_and_stamps_head(pg_db) -> None:
    bootstrap_database()
    sv = schema_version()
    assert sv.is_up_to_date, (sv.current, sv.head)
    # A head-only table materialised (not just stamped).
    tabs = set(inspect(create_engine(pg_db)).get_table_names())
    assert "field_permission_rules" in tabs  # from migration 0043 on this chain
    assert "alembic_version" in tabs


@requires_postgres
def test_bootstrap_at_head_is_idempotent_noop(pg_db) -> None:
    bootstrap_database()
    assert schema_version().is_up_to_date
    # Second call is a no-op upgrade (stamped DB -> upgrade head), still at head.
    bootstrap_database()
    assert schema_version().is_up_to_date


@requires_postgres
def test_bootstrap_stamped_behind_upgrades_to_head(pg_db) -> None:
    # create_all gives the head schema; stamp it one revision behind head so
    # bootstrap takes the upgrade branch and applies the trailing migration.
    engine = create_engine(pg_db)
    Base.metadata.create_all(engine)
    engine.dispose()
    cfg = make_alembic_config(pg_db)
    head = ScriptDirectory.from_config(cfg)
    down = head.get_revision(head.get_current_head()).down_revision
    command.stamp(cfg, down)
    assert schema_version().current != schema_version().head
    bootstrap_database()
    assert schema_version().is_up_to_date


# --------------------------------------------------------------------------
# Part 2 — the assert_schema_current gate
# --------------------------------------------------------------------------


@requires_postgres
def test_assert_schema_current_passes_at_head(pg_db) -> None:
    bootstrap_database()
    assert_schema_current()  # no raise


@requires_postgres
def test_assert_schema_current_raises_when_unstamped(pg_db) -> None:
    # fresh_db leaves an empty version table: no row, no revision.
    with pytest.raises(SchemaDriftError) as ei:
        assert_schema_current()
    assert ei.value.current is None and ei.value.head is not None


@requires_postgres
def test_assert_schema_current_raises_when_behind(pg_db) -> None:
    bootstrap_database()
    # Re-stamp to a value that merely differs from head (drift = current != head).
    engine = create_engine(pg_db)
    with engine.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num='0001_pg_baseline'"))
    engine.dispose()
    with pytest.raises(SchemaDriftError):
        assert_schema_current()


# --------------------------------------------------------------------------
# run_api refuse-to-serve on drift (acceptance #1)
# --------------------------------------------------------------------------


@requires_postgres
def test_run_api_refuses_to_start_on_drift(pg_db, monkeypatch) -> None:
    # un-stamped -> drift; the SQLite refusal does not fire on a Postgres URL.
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-api", "--check-only"])
    from crmbuilder_v2 import cli

    with pytest.raises(SystemExit) as ei:
        cli.run_api()
    assert ei.value.code == 2  # _fail_loud exits 2 before any uvicorn start
