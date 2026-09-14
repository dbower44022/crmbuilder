"""Schema-version introspection for the unified v2 database.

The migration system *is* the database version system: each Alembic
revision is a schema version, and the chain head is the latest. This
module reports, for the unified DB, the revision it is currently stamped
at (read from its ``alembic_version`` table) versus the head its
migration chain defines, plus whether the two agree.

PI-β collapsed the per-engagement + meta two-chain world into one unified
DB at ``Settings.db_url``. PI-503 (REQ-593 / DEC-1082) then retired the SQLite
Alembic chain, so there is exactly one migration chain — the Postgres tree at
``crmbuilder-v2/migrations/pg/`` — and it is the only chain this module knows.
:func:`schema_version` reports the unified DB against that head.

The everyday test suite still builds per-test SQLite files straight from the
ORM models (``Base.metadata.create_all``) and never runs a migration; that is
a test-isolation device, not a served store. Anything that *serves* or
*migrates* a store is Postgres-only — see :func:`refuse_sqlite`.
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

#: Where the local development Postgres lives (``crmbuilder-v2/docker-compose.dev.yml``).
LOCAL_POSTGRES_CONTAINER = "crmb_pg_dev"
LOCAL_POSTGRES_URL = "postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2"


class SqliteRefusedError(RuntimeError):
    """A Postgres-only entry point was pointed at a SQLite URL.

    Raised by :func:`refuse_sqlite` from the two entry points that serve or
    migrate a store (``crmbuilder-v2-api`` and ``crmbuilder-v2-bootstrap-db``).
    The SQLite store was retired as a source of truth by the 2026-07-01 cloud
    cutover and its migration chain was removed (PI-503); the message names the
    local Postgres container to use instead.
    """

    def __init__(self, url: str, what: str) -> None:
        self.url = url
        self.what = what
        super().__init__(
            f"{what} targets Postgres only; refusing the SQLite URL {url!r}.\n"
            "  The SQLite store was retired on 2026-07-01 and its migration chain "
            "removed (PI-503).\n"
            "  For local work start the dev Postgres container "
            f"({LOCAL_POSTGRES_CONTAINER}):\n"
            "    docker compose -f crmbuilder-v2/docker-compose.dev.yml up -d\n"
            f"  then set CRMBUILDER_V2_DATABASE_URL='{LOCAL_POSTGRES_URL}'."
        )


def refuse_sqlite(url: str, what: str) -> None:
    """Raise :class:`SqliteRefusedError` if ``url`` is a SQLite URL.

    ``what`` names the caller for the message (e.g. ``"crmbuilder-v2-api"``).
    """
    if make_url(url).get_backend_name() == "sqlite":
        raise SqliteRefusedError(url, what)


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
    """The one migration chain: the Postgres tree at ``crmbuilder-v2/migrations/pg``."""
    # version_info.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/migration/
    return Path(__file__).resolve().parents[3] / "migrations" / "pg"


def make_alembic_config(url: str | None = None) -> Config:
    """Build an Alembic Config for the (single, Postgres) migration chain.

    Until PI-503 the SQLite and Postgres chains were two Alembic environments
    stamping the same ``alembic_version`` table, and the head had to be resolved
    from the chain matching the DB's dialect (PI-308). There is one chain now,
    so the head is the same whatever ``url`` is; ``url`` defaults to the
    configured unified DB and is only used to point the environment at it.
    This function does not refuse a SQLite URL — reading ``alembic_version``
    off a SQLite test file is harmless — the two entry points that serve or
    migrate a store refuse it themselves via :func:`refuse_sqlite`.
    """
    url = url or get_settings().db_url
    script = _migrations_dir()
    cfg = Config(str(script / "alembic.ini"))
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
