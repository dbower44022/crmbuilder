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

from crmbuilder_v2.config import get_settings


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


def make_alembic_config() -> Config:
    """Build an Alembic Config pointed at the unified DB."""
    alembic_dir = _migrations_dir()
    cfg = Config(str(alembic_dir.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option("sqlalchemy.url", get_settings().db_url)
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
    cfg = make_alembic_config()
    return SchemaVersion(
        current=_current_revision(settings.db_url),
        head=_head_revision(cfg),
    )
