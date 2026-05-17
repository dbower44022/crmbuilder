"""Lazy per-engagement Alembic migration (v0.5 slice A).

When an engagement is activated, the engine launcher runs the existing
per-engagement Alembic chain against the engagement's DB before the
API subprocess opens it. Per
``multi-engagement-architecture.md`` §3.6 / DEC-083.

Slice A includes the helper because slice D's activation flow consumes
it; the dogfood migration in ``dogfood_v0_5.py`` also calls it so the
post-copy ``CRMBUILDER.db`` has its ``alembic_version`` table tracked
properly.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from crmbuilder_v2.config import get_settings


class MigrationError(RuntimeError):
    """A per-engagement Alembic migration failed."""


def _engagement_alembic_dir() -> Path:
    # lazy_migration.py is at <repo>/crmbuilder-v2/src/crmbuilder_v2/migration/
    return Path(__file__).resolve().parents[3] / "migrations"


def engagement_db_path(engagement_code: str) -> Path:
    """Return the absolute path to ``engagements/{code}.db``."""
    s = get_settings()
    return s.db_path.parent / "engagements" / f"{engagement_code}.db"


def make_engagement_alembic_config(engagement_code: str) -> Config:
    """Build an Alembic Config pointed at one engagement's DB."""
    alembic_dir = _engagement_alembic_dir()
    cfg = Config(str(alembic_dir.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(alembic_dir))
    cfg.set_main_option(
        "sqlalchemy.url",
        f"sqlite:///{engagement_db_path(engagement_code)}",
    )
    return cfg


def run_engagement_migrations(engagement_code: str) -> None:
    """Apply the per-engagement Alembic chain to head against the
    named engagement's DB file.

    Opens the DB directly (bypasses the API). Raises
    :class:`MigrationError` if Alembic fails or the DB file is missing.
    """
    db_path = engagement_db_path(engagement_code)
    if not db_path.exists():
        raise MigrationError(
            f"engagement DB not found at {db_path}"
        )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cfg = make_engagement_alembic_config(engagement_code)
    try:
        command.upgrade(cfg, "head")
    except Exception as exc:
        raise MigrationError(
            f"alembic upgrade failed for engagement {engagement_code!r}: {exc}"
        ) from exc
