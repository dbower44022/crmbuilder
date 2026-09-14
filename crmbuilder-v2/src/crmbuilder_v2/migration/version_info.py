"""Schema-version introspection for the unified v2 database.

The migration system *is* the database version system: each Alembic
revision is a schema version, and the chain's heads are the latest. This
module reports, for the unified DB, the set of revisions it is currently
stamped at (read from its ``alembic_version`` table) versus the set of heads
its migration tree defines, plus whether the two agree.

Since PI-507 (REQ-592 / DEC-1079) the tree has **one head per owner**: the
trunk ``0001`` .. ``0097`` is shared history, and each of the seven owners of
the record-type-to-segment map (``client_management``, ``discovery``,
``solution_design``, ``build``, ``operate``, ``delivery``, ``shared_core``)
continues on its own labelled branch. A database is current when its stamped
set equals the head set — every branch head present, nothing else — which is
what ``alembic upgrade heads`` produces. A lane adding a migration appends to
its owner's branch, so two lanes never take the same next identifier
(lesson LSN-075 is closed by construction).

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
from sqlalchemy import create_engine, text
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
    """The unified DB's stamped set differs from the tree's head set.

    Raised by :func:`assert_schema_current` so the API can refuse to serve a DB
    whose schema is behind the code (PI-308 / REQ-343). ``applied`` is the set
    of stamped revisions (empty for an un-stamped / empty DB); ``heads`` is the
    set of heads the migration tree defines, one per branch; ``missing`` is the
    heads the DB lacks and ``stale`` the stamped revisions that are not heads.
    ``current`` and ``head`` are the same two sets rendered as one string each,
    for messages that show a single line.
    """

    def __init__(
        self,
        applied: tuple[str, ...],
        heads: tuple[str, ...],
    ) -> None:
        self.applied = applied
        self.heads = heads
        self.missing = tuple(h for h in heads if h not in applied)
        self.stale = tuple(a for a in applied if a not in heads)
        self.current = _render(applied)
        self.head = _render(heads)
        super().__init__(
            "database schema is behind the code: "
            f"applied={self.current!r} heads={self.head!r} "
            f"missing={list(self.missing)!r}"
        )


def _render(revisions: tuple[str, ...]) -> str | None:
    """One line for a set of revisions; ``None`` when the set is empty."""
    return ", ".join(revisions) or None


@dataclass(frozen=True)
class SchemaVersion:
    """A DB's stamped revision set versus its tree's head set.

    ``applied`` and ``heads`` are sorted tuples. ``current`` / ``head`` render
    each as one string (``None`` when empty) so a display that shows one line
    per side keeps working; ``missing`` lists the heads the DB lacks.
    """

    applied: tuple[str, ...]
    heads: tuple[str, ...]

    @property
    def current(self) -> str | None:
        return _render(self.applied)

    @property
    def head(self) -> str | None:
        return _render(self.heads)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(h for h in self.heads if h not in self.applied)

    @property
    def stale(self) -> tuple[str, ...]:
        return tuple(a for a in self.applied if a not in self.heads)

    @property
    def is_up_to_date(self) -> bool:
        return bool(self.heads) and set(self.applied) == set(self.heads)

    def to_dict(self) -> dict:
        return {
            "current": self.current,
            "head": self.head,
            "applied": list(self.applied),
            "heads": list(self.heads),
            "missing": list(self.missing),
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


#: The owners of the record-type-to-segment map, each with its own migration
#: branch (PI-507). A revision on a branch touches only its owner's tables.
BRANCH_LABELS: tuple[str, ...] = (
    "client_management",
    "discovery",
    "solution_design",
    "build",
    "operate",
    "delivery",
    "shared_core",
)

#: Width of ``alembic_version.version_num``. Alembic creates the table with
#: ``VARCHAR(32)`` when absent, and forty of the trunk's revision identifiers
#: are longer than that (``0096_pi_488_session_opening_fields`` is 34); the
#: live store carries 255 and a fresh bootstrap must match it.
VERSION_NUM_WIDTH = 255


def _head_revisions(cfg: Config) -> tuple[str, ...]:
    """Every head the tree defines, one per branch, sorted."""
    return tuple(sorted(ScriptDirectory.from_config(cfg).get_heads()))


def _current_revisions(url: str) -> tuple[str, ...]:
    """The revisions stamped in a DB's ``alembic_version`` table, sorted.

    Empty for an un-stamped DB (no ``alembic_version`` row / table) — the
    same signal Alembic itself uses for "base".
    """
    engine = create_engine(url, future=True)
    try:
        with engine.connect() as conn:
            return tuple(sorted(MigrationContext.configure(conn).get_current_heads()))
    finally:
        engine.dispose()


def ensure_version_table_wide(url: str) -> None:
    """Make ``alembic_version.version_num`` :data:`VERSION_NUM_WIDTH` wide.

    Creates the table wide when it is absent (so Alembic's ``checkfirst`` leaves
    it alone instead of creating the 32-character default) and widens it when
    an earlier bootstrap left it narrow. A no-op on the live store, which is
    already 255. Postgres only; the everyday SQLite test files never come here.
    """
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as conn:
            width = conn.execute(
                text(
                    "SELECT character_maximum_length FROM information_schema.columns "
                    "WHERE table_name = 'alembic_version' AND column_name = 'version_num'"
                )
            ).scalar()
            if width is None:
                conn.execute(
                    text(
                        "CREATE TABLE IF NOT EXISTS alembic_version ("
                        f"version_num VARCHAR({VERSION_NUM_WIDTH}) NOT NULL, "
                        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
                    )
                )
            elif width < VERSION_NUM_WIDTH:
                conn.execute(
                    text(
                        "ALTER TABLE alembic_version ALTER COLUMN version_num "
                        f"TYPE VARCHAR({VERSION_NUM_WIDTH})"
                    )
                )
    finally:
        engine.dispose()


def schema_version() -> SchemaVersion:
    """Schema version of the unified DB ``Settings`` currently points at."""
    settings = get_settings()
    cfg = make_alembic_config(settings.db_url)
    return SchemaVersion(
        applied=_current_revisions(settings.db_url),
        heads=_head_revisions(cfg),
    )


def assert_schema_current() -> None:
    """Raise :class:`SchemaDriftError` unless the stamped set equals the head set.

    The active startup gate (PI-308 / REQ-343, per-branch since PI-507): an
    empty or un-stamped DB, a DB missing any branch head, and a DB stamped at
    a revision that is not a head all count as drift — serving any of them
    silently risks 500s on the first query that hits a not-yet-migrated table
    or column.
    """
    sv = schema_version()
    if not sv.is_up_to_date:
        raise SchemaDriftError(sv.applied, sv.heads)
