"""Meta DB Alembic helper (v0.5 slice A).

Wraps the Alembic ``upgrade head`` invocation against the meta DB's
chain at ``crmbuilder-v2/migrations/meta/``. Called by the engine
launcher at desktop / API startup so the meta DB schema is current
before the registry is read or written.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from crmbuilder_v2.access.meta_db import meta_db_url


def _meta_alembic_dir() -> Path:
    # meta_alembic.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/migration/meta_alembic.py
    return Path(__file__).resolve().parents[3] / "migrations" / "meta"


def make_meta_alembic_config() -> Config:
    """Build an Alembic Config pointed at the meta DB chain."""
    meta_dir = _meta_alembic_dir()
    cfg = Config(str(meta_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(meta_dir))
    cfg.set_main_option("sqlalchemy.url", meta_db_url())
    return cfg


def run_meta_migrations() -> None:
    """Apply the meta DB Alembic chain to head (idempotent)."""
    cfg = make_meta_alembic_config()
    command.upgrade(cfg, "head")
