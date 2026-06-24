"""PI-308 / REQ-343 — migration-drift detection + honest schema-apply.

Covers: dialect-aware head resolution (the SQLite vs PG chain), the honest
``bootstrap_database`` (un-stamped DB -> create_all+stamp; stamped DB ->
upgrade), the ``assert_schema_current`` drift gate, and ``run_api``'s
refuse-to-serve-on-drift behaviour.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from crmbuilder_v2.access.db import bootstrap_database
from crmbuilder_v2.access.models import Base
from crmbuilder_v2.migration.version_info import (
    SchemaDriftError,
    _head_revision,
    assert_schema_current,
    make_alembic_config,
    schema_version,
)
from sqlalchemy import create_engine


def _point_settings(monkeypatch, db: Path) -> None:
    """Force the configured unified DB at ``db`` for this test."""
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(db))
    from crmbuilder_v2 import config

    config.get_settings.cache_clear()


# --------------------------------------------------------------------------
# Part 0 — dialect-aware head resolution
# --------------------------------------------------------------------------


def test_make_alembic_config_dialect_aware_script_location() -> None:
    sq = make_alembic_config("sqlite:////tmp/x.db")
    pg = make_alembic_config("postgresql+psycopg://u@h/d")
    assert sq.get_main_option("script_location").endswith("migrations")
    assert pg.get_main_option("script_location").endswith("migrations/pg")


def test_sqlite_and_pg_heads_are_distinct() -> None:
    # The two chains stamp the same alembic_version table; resolving head from
    # the wrong chain was the latent bug PI-308 §3 fixes.
    sq_head = _head_revision(make_alembic_config("sqlite:////tmp/x.db"))
    pg_head = _head_revision(make_alembic_config("postgresql+psycopg://u@h/d"))
    assert sq_head and pg_head and sq_head != pg_head


# --------------------------------------------------------------------------
# Part 1 — honest bootstrap_database
# --------------------------------------------------------------------------


def test_bootstrap_fresh_db_creates_and_stamps_head(tmp_path, monkeypatch) -> None:
    db = tmp_path / "fresh.db"
    _point_settings(monkeypatch, db)
    bootstrap_database()
    sv = schema_version()
    assert sv.is_up_to_date, (sv.current, sv.head)
    # A head-only table materialised (not just stamped).
    c = sqlite3.connect(db)
    tabs = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    c.close()
    assert "field_permission_rules" in tabs  # from migration 0086
    assert "alembic_version" in tabs


def test_bootstrap_at_head_is_idempotent_noop(tmp_path, monkeypatch) -> None:
    db = tmp_path / "athead.db"
    _point_settings(monkeypatch, db)
    bootstrap_database()
    assert schema_version().is_up_to_date
    # Second call is a no-op upgrade (stamped DB -> upgrade head), still at head.
    bootstrap_database()
    assert schema_version().is_up_to_date


def test_bootstrap_stamped_behind_upgrades_to_head(tmp_path, monkeypatch) -> None:
    # create_all gives the head schema; stamp it one revision behind head so
    # bootstrap takes the upgrade branch and applies the trailing migration.
    db = tmp_path / "behind.db"
    _point_settings(monkeypatch, db)
    engine = create_engine(f"sqlite:///{db}")
    Base.metadata.create_all(engine)
    engine.dispose()
    cfg = make_alembic_config(f"sqlite:///{db}")
    from alembic.script import ScriptDirectory

    head = ScriptDirectory.from_config(cfg)
    down = head.get_revision(head.get_current_head()).down_revision
    command.stamp(cfg, down)
    assert schema_version().current != schema_version().head
    bootstrap_database()
    assert schema_version().is_up_to_date


# --------------------------------------------------------------------------
# Part 2 — the assert_schema_current gate
# --------------------------------------------------------------------------


def test_assert_schema_current_passes_at_head(tmp_path, monkeypatch) -> None:
    db = tmp_path / "head.db"
    _point_settings(monkeypatch, db)
    bootstrap_database()
    assert_schema_current()  # no raise


def test_assert_schema_current_raises_when_unstamped(tmp_path, monkeypatch) -> None:
    db = tmp_path / "unstamped.db"
    _point_settings(monkeypatch, db)
    create_engine(f"sqlite:///{db}").connect().close()  # empty, no alembic_version
    with pytest.raises(SchemaDriftError) as ei:
        assert_schema_current()
    assert ei.value.current is None and ei.value.head is not None


def test_assert_schema_current_raises_when_behind(tmp_path, monkeypatch) -> None:
    db = tmp_path / "behind2.db"
    _point_settings(monkeypatch, db)
    bootstrap_database()
    # Re-stamp to a value that merely differs from head (drift = current != head).
    c = sqlite3.connect(db)
    c.execute("UPDATE alembic_version SET version_num='0001_initial'")
    c.commit()
    c.close()
    with pytest.raises(SchemaDriftError):
        assert_schema_current()


# --------------------------------------------------------------------------
# run_api refuse-to-serve on drift (acceptance #1)
# --------------------------------------------------------------------------


def test_run_api_refuses_to_start_on_drift(tmp_path, monkeypatch) -> None:
    db = tmp_path / "drift.db"
    _point_settings(monkeypatch, db)
    create_engine(f"sqlite:///{db}").connect().close()  # un-stamped -> drift
    monkeypatch.setattr("sys.argv", ["crmbuilder-v2-api", "--check-only"])
    from crmbuilder_v2 import cli

    with pytest.raises(SystemExit) as ei:
        cli.run_api()
    assert ei.value.code == 2  # _fail_loud exits 2 before any uvicorn start
