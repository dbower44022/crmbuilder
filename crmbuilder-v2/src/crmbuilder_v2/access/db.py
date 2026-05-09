"""SQLAlchemy engine and session factory.

The engine is constructed lazily so tests can switch ``CRMBUILDER_V2_DB_PATH``
before importing repositories. ``bootstrap_database`` materialises the schema
on a fresh database file.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from crmbuilder_v2.access.models import Base
from crmbuilder_v2.config import Settings, get_settings

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None
_engine_url: str | None = None


def _enable_sqlite_pragmas(dbapi_conn, _conn_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _build_engine(url: str) -> Engine:
    engine = create_engine(url, future=True)
    event.listen(engine, "connect", _enable_sqlite_pragmas)
    return engine


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine, _SessionFactory, _engine_url
    s = settings or get_settings()
    if _engine is None or _engine_url != s.db_url:
        _ensure_db_dir(s.db_path)
        _engine = _build_engine(s.db_url)
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
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

    s = settings or get_settings()
    factory = get_session_factory(s)
    session = factory()
    staging: list = []
    try:
        yield session
        session.flush()
        if export:
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

    s = settings or get_settings()
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
