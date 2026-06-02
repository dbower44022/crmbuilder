"""SQLAlchemy engine and session factory.

The engine is constructed lazily so tests can switch ``CRMBUILDER_V2_DB_PATH``
before importing repositories. ``bootstrap_database`` materialises the schema
on a fresh database file.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, make_url
from sqlalchemy.orm import Session, sessionmaker

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import Settings, get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None
_engine_url: str | None = None
# Serialises engine/factory (re)builds so a concurrent reader never sees a
# factory published before its engagement-scope listeners are installed.
_engine_lock = threading.RLock()


def _enable_sqlite_pragmas(dbapi_conn, _conn_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # Wait (up to 5s) for a contended write lock rather than failing fast
    # with SQLITE_BUSY. Required now that we control transactions explicitly
    # and serialise writers via BEGIN IMMEDIATE (see ``_sqlite_emit_begin``);
    # the concurrent-POST identifier-assignment tests spin up several writers
    # at once.
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()
    # Disable pysqlite's legacy autocommit-emulation: by default the driver
    # opens transactions lazily and runs DDL / SAVEPOINT statements in
    # autocommit mode, so ``RELEASE SAVEPOINT`` durably commits and a later
    # ``session.rollback()`` cannot undo it. Setting ``isolation_level=None``
    # hands transaction control to SQLAlchemy, which emits BEGIN via the
    # handler below. Without this, the autoassign SAVEPOINT pattern combined
    # with post-insert edge-rule validation (the v0.7 governance entities)
    # would leave orphaned partial rows on a validation failure.
    dbapi_conn.isolation_level = None


def _sqlite_emit_begin(conn) -> None:
    # BEGIN IMMEDIATE acquires the RESERVED (write-intent) lock at transaction
    # start, so concurrent writers queue cleanly (with busy_timeout) instead of
    # both taking a read lock and deadlocking on the upgrade to write.
    conn.exec_driver_sql("BEGIN IMMEDIATE")


def _is_sqlite(url: str) -> bool:
    return make_url(url).get_backend_name() == "sqlite"


def _pool_kwargs(url: str) -> dict:
    """Engine pool args, dialect-conditional (PI-alpha D10).

    SQLite keeps SQLAlchemy's default (no explicit pool) — single local file,
    serialized writers. Postgres gets a real ``QueuePool`` with ``pre_ping``
    (defends against managed-PG idle-connection drops) and ``recycle``
    (defends against server-side connection timeouts). Sizes are
    env-overridable via ``CRMBUILDER_V2_*``; the defaults are conservative and
    pinned against the prod topology + PI-100 scale testing at the Deployment
    phase.
    """
    if _is_sqlite(url):
        return {}
    s = get_settings()
    return {
        "pool_size": s.db_pool_size,
        "max_overflow": s.db_max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": s.db_pool_recycle,
    }


def _build_engine(url: str) -> Engine:
    engine = create_engine(url, future=True, **_pool_kwargs(url))
    # The SQLite transaction hacks (foreign-keys/busy-timeout pragmas,
    # isolation_level=None, BEGIN IMMEDIATE) exist solely to make SQLite behave
    # under concurrent writers and to fix pysqlite's autocommit-emulation
    # SAVEPOINT bug. None apply to Postgres — PG has MVCC, real transactions,
    # and correct SAVEPOINT semantics out of the box — so install them only on
    # SQLite. The engagement-scope ORM event listeners (installed in
    # ``get_engine``) are dialect-agnostic and apply on both.
    if _is_sqlite(url):
        event.listen(engine, "connect", _enable_sqlite_pragmas)
        event.listen(engine, "begin", _sqlite_emit_begin)
    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine, _SessionFactory, _engine_url
    s = settings or get_settings()
    if _engine is None or _engine_url != s.db_url:
        with _engine_lock:
            # Double-checked: another thread may have built it while we waited.
            if _engine is None or _engine_url != s.db_url:
                from crmbuilder_v2.access.engagement_scope import (
                    install_engagement_scope,
                )

                _ensure_db_dir(s.db_path)
                engine = _build_engine(s.db_url)
                factory = sessionmaker(
                    bind=engine, expire_on_commit=False, future=True
                )
                # PI-123: install the row-level engagement-scope filter/stamp
                # BEFORE publishing the factory to the module globals. The
                # handlers are dormant until a caller sets an active engagement
                # (scope middleware / CLI / test fixture), so this is harmless on
                # the default runtime — but installing *before* publish (and
                # under the lock) closes the race where a concurrent reader (a
                # TestClient portal thread, the 8-thread concurrent-POST tests, a
                # lingering request thread) could grab a published-but-not-yet-
                # installed factory and write un-stamped (NULL engagement_id)
                # rows under the strict schema. Always-install (not gated on
                # engagement_scoping_enabled) also avoids a factory built while
                # scoping was disabled lacking the stamp permanently; the flag
                # still gates the request middleware and enforcement.
                install_engagement_scope(factory)
                _engine = engine
                _SessionFactory = factory
                _engine_url = s.db_url
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    get_engine(settings)
    assert _SessionFactory is not None
    return _SessionFactory


def reset_engine_cache() -> None:
    """Reset the cached engine + session factory (useful in tests)."""
    global _engine, _SessionFactory, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
    _engine_url = None


@contextmanager
def session_scope(
    settings: Settings | None = None, *, export: bool = True
) -> Iterator[Session]:
    """Yield a SQLAlchemy session inside an atomic DB+JSON transaction.

    Order of operations:

    1. Caller modifies the session.
    2. ``session.flush()`` persists changes to the SQLite transaction.
    3. The exporter snapshots the post-flush state and writes ``.tmp`` files.
    4. ``session.commit()`` makes the database changes durable.
    5. The exporter promotes ``.tmp`` files into final position.

    A failure in 2–3 rolls back; staging tempfiles are cleaned up.
    A failure in 4 also rolls back and cleans staging.
    A failure in 5 (extremely unlikely on same-filesystem rename) leaves
    the export stale; the next write self-heals because the export is
    a full rewrite of all tables.

    ``export=False`` skips the JSON export hook. Used by the bootstrap
    migration when running a multi-step import inside a single transaction.
    """
    from crmbuilder_v2.access.exporter import (
        build_snapshot,
        promote_staging,
        write_staging,
    )
    from crmbuilder_v2.runtime.engagement_routing import assert_export_dir_ready

    s = settings or get_settings()
    factory = get_session_factory(s)
    session = factory()
    staging: list = []
    try:
        yield session
        session.flush()
        if export:
            assert_export_dir_ready(s)
            snapshot = build_snapshot(session)
            staging = write_staging(snapshot, s.export_dir)
        session.commit()
        if export and staging:
            promote_staging(staging)
            staging = []
    except Exception:
        session.rollback()
        if staging:
            for tmp in staging:
                try:
                    tmp.unlink()
                except FileNotFoundError:
                    pass
        raise
    finally:
        session.close()


def force_export(settings: Settings | None = None) -> None:
    """Rewrite the JSON export from current database state, no DB writes.

    Useful after ``bootstrap_database`` on a fresh DB to materialise the
    empty-export tree, and as a recovery if exports got out of sync.
    """
    from crmbuilder_v2.access.exporter import (
        build_snapshot,
        promote_staging,
        write_staging,
    )
    from crmbuilder_v2.runtime.engagement_routing import assert_export_dir_ready

    s = settings or get_settings()
    assert_export_dir_ready(s)
    factory = get_session_factory(s)
    session = factory()
    try:
        snapshot = build_snapshot(session)
        staging = write_staging(snapshot, s.export_dir)
        promote_staging(staging)
    finally:
        session.close()


def _ensure_db_dir(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)


def bootstrap_database(settings: Settings | None = None) -> None:
    """Materialise the schema on a fresh database file.

    For v0.1 we use ``Base.metadata.create_all`` rather than running Alembic
    explicitly — Alembic is set up for forward migrations after v0.1, but
    the v0.1 baseline migration is itself ``create_all`` against
    ``Base.metadata``. The Alembic environment imports the same metadata so
    ``alembic upgrade head`` produces the same result.
    """
    s = settings or get_settings()
    engine = get_engine(s)
    Base.metadata.create_all(engine)
