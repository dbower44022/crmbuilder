"""Schema-version introspection for the unified v2 database.

The migration system *is* the database version system: each Alembic
revision is a schema version, and the chain head is the latest. This
module reports, for the unified DB, the revision it is currently stamped
at (read from its ``alembic_version`` table) versus the head its
migration chain defines, plus whether the two agree.

PI-β collapsed the per-engagement + meta two-chain world into one: there
is a single unified DB at ``Settings.db_url`` migrated by the chain at
``crmbuilder-v2/migrations/``. :func:`schema_version` reports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from crmbuilder_v2.config import get_settings


class SchemaDriftError(RuntimeError):
    """The unified DB is stamped behind (or un-stamped relative to) its chain head.

    Raised by :func:`assert_schema_current` so the API can refuse to serve a DB
    whose schema is behind the code (PI-308 / REQ-343). ``current`` is the
    stamped revision (``None`` for an un-stamped / empty DB); ``head`` is the
    revision the migration chain defines.
    """

    def __init__(self, current: str | None, head: str | None) -> None:
        self.current = current
        self.head = head
        super().__init__(
            f"database schema is behind the code: applied={current!r} head={head!r}"
        )


@dataclass(frozen=True)
class SchemaVersion:
    """A DB's stamped revision versus its chain head."""

    current: str | None
    head: str | None

    @property
    def is_up_to_date(self) -> bool:
        return self.current is not None and self.current == self.head

    def to_dict(self) -> dict:
        return {
            "current": self.current,
            "head": self.head,
            "up_to_date": self.is_up_to_date,
        }


def _migrations_dir() -> Path:
    # version_info.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/migration/
    return Path(__file__).resolve().parents[3] / "migrations"


def make_alembic_config(url: str | None = None) -> Config:
    """Build an Alembic Config pointed at the unified DB, dialect-aware.

    The SQLite and Postgres chains are two separate Alembic environments that
    stamp the same ``alembic_version`` table (PI-α dual-head). The head must be
    resolved from the chain that matches the DB's dialect, or a Postgres DB
    would be compared against the SQLite head (PI-308). ``url`` defaults to the
    configured unified DB.
    """
    url = url or get_settings().db_url
    is_pg = make_url(url).get_backend_name().startswith("postgresql")
    base = _migrations_dir()
    script = base / "pg" if is_pg else base
    ini = (base / "pg" / "alembic.ini") if is_pg else (base.parent / "alembic.ini")
    cfg = Config(str(ini))
    cfg.set_main_option("script_location", str(script))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _head_revision(cfg: Config) -> str | None:
    return ScriptDirectory.from_config(cfg).get_current_head()


def _current_revision(url: str) -> str | None:
    """Read the revision stamped in a DB's ``alembic_version`` table.

    Returns ``None`` for an un-stamped DB (no ``alembic_version`` row /
    table) — the same signal Alembic itself uses for "base".
    """
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


def schema_version() -> SchemaVersion:
    """Schema version of the unified DB ``Settings`` currently points at."""
    settings = get_settings()
    cfg = make_alembic_config(settings.db_url)
    return SchemaVersion(
        current=_current_revision(settings.db_url),
        head=_head_revision(cfg),
    )


def assert_schema_current() -> None:
    """Raise :class:`SchemaDriftError` if the unified DB is behind / un-stamped.

    The active startup gate (PI-308 / REQ-343): an empty or un-stamped DB
    (``current is None``) and a DB stamped behind head both count as drift —
    serving either silently risks 500s on the first query that hits a
    not-yet-migrated table or column.
    """
    sv = schema_version()
    if not sv.is_up_to_date:
        raise SchemaDriftError(sv.current, sv.head)
