"""Bootstrap-content migration driver.

Imports the four governance markdown files in
``PRDs/product/crmbuilder-v2/`` (charter, decisions, sessions, status)
into the v0.1 database. Idempotent: re-running against an already-
migrated database produces the same state, with no duplicate rows.

Usage:

.. code-block:: shell

    crmbuilder-v2-bootstrap-db   # ensure schema is created
    crmbuilder-v2-bootstrap      # run the content migration
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from crmbuilder_v2.access.change_log import set_actor
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    charter,
    decisions,
    references,
    sessions,
)
from crmbuilder_v2.access.repositories import (
    status as status_repo,
)
from crmbuilder_v2.bootstrap.parsers.charter import parse_charter
from crmbuilder_v2.bootstrap.parsers.decisions import parse_decisions
from crmbuilder_v2.bootstrap.parsers.sessions import parse_sessions
from crmbuilder_v2.bootstrap.parsers.status import parse_status
from crmbuilder_v2.config import get_settings


@dataclass
class MigrationSummary:
    decisions: int = 0
    sessions: int = 0
    charter_versions: int = 0
    status_versions: int = 0
    references: int = 0
    source_dir: str = ""

    def __str__(self) -> str:
        return (
            f"Migrated from {self.source_dir}: "
            f"{self.decisions} decisions, {self.sessions} sessions, "
            f"{self.charter_versions} charter versions, "
            f"{self.status_versions} status versions, "
            f"{self.references} references."
        )


def default_source_dir() -> Path:
    """Return the canonical source directory for the bootstrap content."""
    settings = get_settings()
    # config.py guarantees ``export_dir`` resolves to
    # ``<repo>/PRDs/product/crmbuilder-v2/db-export``; the bootstrap source
    # is the parent (``<repo>/PRDs/product/crmbuilder-v2``).
    return settings.export_dir.parent


def migrate(source_dir: Path) -> MigrationSummary:
    summary = MigrationSummary(source_dir=str(source_dir))
    set_actor("migration")
    try:
        # All four imports plus reference materialisation in one transaction.
        with session_scope() as s:
            # Decisions first: sessions reference them.
            for d in parse_decisions(source_dir / "decisions.md"):
                decisions.upsert(s, **d)
                summary.decisions += 1

            session_to_decisions: dict[str, list[str]] = {}
            for ses in parse_sessions(source_dir / "sessions.md"):
                refs = ses.pop("decisions_made", [])
                session_to_decisions[ses["identifier"]] = refs
                sessions.upsert(s, **ses)
                summary.sessions += 1

            # Materialise the implicit "session decided X decision" cross-refs.
            for ses_id, dec_ids in session_to_decisions.items():
                for dec_id in dec_ids:
                    references.upsert(
                        s,
                        source_type="session",
                        source_id=ses_id,
                        target_type="decision",
                        target_id=dec_id,
                        relationship="decided_in",
                    )
                    summary.references += 1

            for ch in parse_charter(source_dir / "charter.md"):
                charter.upsert_seed(s, **ch)
                summary.charter_versions += 1

            for st in parse_status(source_dir / "status.md"):
                status_repo.upsert_seed(s, **st)
                summary.status_versions += 1
    finally:
        set_actor("claude_session")
    return summary


def migrate_default() -> MigrationSummary:
    """Migrate from the canonical source directory."""
    return migrate(default_source_dir())


__all__ = ["migrate", "migrate_default", "MigrationSummary", "default_source_dir"]
