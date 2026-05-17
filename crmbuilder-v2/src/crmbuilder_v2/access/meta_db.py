"""Meta DB connection management (v0.5 slice A).

Separate connection pool from the per-engagement DB at
``access/db.py``. The meta DB at ``crmbuilder-v2/data/engagements.db``
hosts the ``engagements`` registry table and is wired into the API
server via a parallel FastAPI dependency (``api/deps.py.meta_session``).

Per ``multi-engagement-architecture.md`` §3.1 and §3.10.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from crmbuilder_v2.access.db import _build_engine
from crmbuilder_v2.access.meta_models import MetaBase
from crmbuilder_v2.config import get_settings

_meta_engine: Engine | None = None
_meta_session_factory: sessionmaker[Session] | None = None
_meta_engine_url: str | None = None


def meta_db_path() -> Path:
    """Return the absolute path to the meta DB file.

    Fixed relative to the engine repo root, derived from the existing
    per-engagement ``Settings.db_path`` so test overrides apply: the
    meta DB always lives in the same ``data/`` directory as the
    per-engagement DB. Tests that override ``CRMBUILDER_V2_DB_PATH``
    transparently relocate the meta DB too.
    """
    s = get_settings()
    return s.db_path.parent / "engagements.db"


def meta_db_url() -> str:
    """Return the SQLAlchemy URL for the meta DB."""
    return f"sqlite:///{meta_db_path()}"


def get_meta_engine() -> Engine:
    """Return the meta DB engine, building it on first access."""
    global _meta_engine, _meta_session_factory, _meta_engine_url
    url = meta_db_url()
    if _meta_engine is None or _meta_engine_url != url:
        _ensure_meta_dir()
        _meta_engine = _build_engine(url)
        _meta_session_factory = sessionmaker(
            bind=_meta_engine, expire_on_commit=False, future=True
        )
        _meta_engine_url = url
    return _meta_engine


def get_meta_session_factory() -> sessionmaker[Session]:
    """Return the meta DB session factory."""
    get_meta_engine()
    assert _meta_session_factory is not None
    return _meta_session_factory


def reset_meta_engine_cache() -> None:
    """Reset the cached meta DB engine + session factory (tests)."""
    global _meta_engine, _meta_session_factory, _meta_engine_url
    if _meta_engine is not None:
        _meta_engine.dispose()
    _meta_engine = None
    _meta_session_factory = None
    _meta_engine_url = None


@contextmanager
def meta_session_scope() -> Iterator[Session]:
    """Yield a meta DB session inside an atomic transaction.

    No JSON export hook in slice A — slice B's repository adds the
    ``db-export/meta/engagements.json`` regeneration. Slice A only
    wires the connection pool and the dependency for routing.
    """
    factory = get_meta_session_factory()
    session = factory()
    try:
        yield session
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_meta_db_pool() -> None:
    """Initialise the meta DB connection pool.

    Idempotent. Called at API subprocess startup so the engine is
    available for the first request. Tests may also call this after
    overriding ``CRMBUILDER_V2_DB_PATH`` to materialise the pool
    against the test path.
    """
    get_meta_engine()


def bootstrap_meta_db() -> None:
    """Materialise the meta DB schema on a fresh file.

    Slice A's launcher integration calls this so the meta DB exists
    before the API serves any request. Equivalent to
    ``alembic upgrade head`` for the meta chain via metadata
    ``create_all``; for forward migrations after slice A the launcher
    invokes Alembic explicitly via ``run_meta_migrations()``.
    """
    engine = get_meta_engine()
    MetaBase.metadata.create_all(engine)


def _ensure_meta_dir() -> None:
    meta_db_path().parent.mkdir(parents=True, exist_ok=True)
