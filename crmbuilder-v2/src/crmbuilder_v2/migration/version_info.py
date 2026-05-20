"""Schema-version introspection for the v2 databases.

The migration system *is* the database version system: each Alembic
revision (``0001_…`` … ``0010_…``) is a schema version, and the chain
head is the latest. This module reports, for a DB, the revision it is
currently stamped at (read from its ``alembic_version`` table) versus the
head its migration chain defines, plus whether the two agree.

Two chains exist (``multi-engagement-architecture.md`` §3.6):

* the per-engagement chain at ``crmbuilder-v2/migrations/`` — one DB per
  engagement; :func:`engagement_schema_version` reports the *active*
  engagement's DB (whatever ``Settings.db_path`` currently points at).
* the meta chain at ``crmbuilder-v2/migrations/meta/`` — the engagement
  registry; :func:`meta_schema_version`.
"""

from __future__ import annotations

from dataclasses import dataclass

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.migration.lazy_migration import make_engagement_alembic_config
from crmbuilder_v2.migration.meta_alembic import make_meta_alembic_config


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


def engagement_schema_version() -> SchemaVersion:
    """Schema version of the engagement DB ``Settings`` currently points at.

    The head is read from the per-engagement migration chain (independent
    of which engagement is active); the current revision is read from the
    actual bound DB at ``Settings.db_url``.
    """
    settings = get_settings()
    # The engagement code only sets the (here-unused) URL option on the
    # config; head resolution depends solely on the script location. The
    # current revision is read from the authoritative bound DB URL.
    cfg = make_engagement_alembic_config(settings.db_path.stem)
    return SchemaVersion(
        current=_current_revision(settings.db_url),
        head=_head_revision(cfg),
    )


def meta_schema_version() -> SchemaVersion:
    """Schema version of the engagement-registry meta DB."""
    cfg = make_meta_alembic_config()
    url = cfg.get_main_option("sqlalchemy.url")
    return SchemaVersion(
        current=_current_revision(url),
        head=_head_revision(cfg),
    )
