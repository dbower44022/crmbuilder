"""SQLAlchemy engine and session factory.

The engine is constructed lazily so tests can switch ``CRMBUILDER_V2_DB_PATH``
before importing repositories. ``bootstrap_database`` materialises the schema
on a fresh database file.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

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
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    """Yield a SQLAlchemy session inside a transaction.

    Commits on success; rolls back on exception. Pair with the JSON export
    hook (see ``access.exporter``) so DB writes and file writes are atomic.
    """
    factory = get_session_factory(settings)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
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
