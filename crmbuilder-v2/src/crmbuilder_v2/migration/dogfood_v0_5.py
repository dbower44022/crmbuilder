"""One-shot dogfood migration: v0.4 ``v2.db`` → v0.5 multi-engagement.

Runs at first launch when the engine detects an existing
``crmbuilder-v2/data/v2.db`` and a missing or empty meta DB. The
eight-step sequence per ``multi-engagement-architecture.md`` §3.7 and
``ui-PRD-v0.5.md`` §5.4:

1. Backup ``v2.db`` to ``v2.db.pre-v0.5-backup``.
2. Create meta DB and apply Alembic to head.
3. INSERT the CRMBUILDER engagement row.
4. Copy ``v2.db`` to ``engagements/CRMBUILDER.db``.
5. Verify row counts across all tracked tables match source.
6. Delete the original ``v2.db``.
7. Refresh JSON snapshots (best-effort).
8. Write ``current_engagement.json``.

Idempotent on rerun. Failure recovery: the ``.pre-v0.5-backup`` is
preserved by every code path; deletion of ``v2.db`` only happens after
the destination row-count verification passes.

See DEC-084.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import insert

from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    get_meta_session_factory,
    meta_db_path,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from crmbuilder_v2.migration.meta_alembic import run_meta_migrations

_log = logging.getLogger("crmbuilder_v2.migration.dogfood")

# Tables present in v0.4 ``v2.db`` that must round-trip cleanly to the
# new ``CRMBUILDER.db``. The verification step (Step 5) asserts that
# every entry in this list has matching row counts on both sides.
_TRACKED_TABLES: tuple[str, ...] = (
    # Governance entities (v0.3 and earlier).
    "sessions",
    "decisions",
    "planning_items",
    "risks",
    "topics",
    "refs",
    "charter",
    "status",
    "change_log",
    # Methodology entities (v0.4).
    "domains",
    "entities",
    "processes",
    "crm_candidates",
    # Catalog tables (catalog ingestion).
    "catalog_entity",
    "catalog_attribute",
    "catalog_source",
)

_CRMBUILDER_CODE = "CRMBUILDER"
_CRMBUILDER_IDENTIFIER = "ENG-001"
_CRMBUILDER_NAME = "CRMBuilder v2"
_CRMBUILDER_PURPOSE = (
    "Dogfood instance hosting the v2 build's own governance content "
    "(sessions, decisions, planning items, methodology catalog)."
)


@dataclass
class MigrationResult:
    """Structured outcome of a dogfood-migration run."""

    success: bool
    steps_completed: list[str] = field(default_factory=list)
    error: str | None = None
    row_count_verifications: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )


def _v2_db_path() -> Path:
    """Legacy v0.4 path: ``crmbuilder-v2/data/v2.db``."""
    return get_settings().db_path


def _backup_path() -> Path:
    return _v2_db_path().with_suffix(".db.pre-v0.5-backup")


def _current_engagement_path() -> Path:
    return _v2_db_path().parent / "current_engagement.json"


def _dogfood_export_dir() -> Path:
    """Absolute path of ``PRDs/product/crmbuilder-v2/db-export/`` for
    the CRMBUILDER engagement's exports.

    Computed from the engine repo root via this file's location:
    ``<repo>/crmbuilder-v2/src/crmbuilder_v2/migration/dogfood_v0_5.py``
    → ``<repo>/PRDs/product/crmbuilder-v2/db-export``.
    """
    return (
        Path(__file__).resolve().parents[4]
        / "PRDs"
        / "product"
        / "crmbuilder-v2"
        / "db-export"
    )


def needs_migration() -> bool:
    """True iff the v0.4 ``v2.db`` exists and we have not yet migrated.

    "Already migrated" is detected by the destination DB file at
    ``engagements/CRMBUILDER.db`` being present and the legacy
    ``v2.db`` being absent. The meta DB and ``current_engagement.json``
    are not checked here — those are inputs to the migration's
    idempotency contract and live under the same control flow.
    """
    legacy = _v2_db_path()
    destination = engagement_db_path(_CRMBUILDER_CODE)
    return legacy.exists() and not destination.exists()


def _table_row_count(conn: sqlite3.Connection, table: str) -> int | None:
    """Return ``COUNT(*)`` for ``table``, or None if the table is absent."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    if cur.fetchone() is None:
        return None
    cur = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cur.fetchone()[0])


def _verify_row_counts(
    source: Path, destination: Path
) -> dict[str, tuple[int, int]]:
    """Return ``{table: (source_count, dest_count)}`` for all tracked
    tables present in either DB. Tables absent from BOTH are silently
    omitted (e.g., catalog tables on a non-catalog dogfood); tables
    present in only ONE side produce a mismatch entry that the caller
    detects."""
    verifications: dict[str, tuple[int, int]] = {}
    with (
        sqlite3.connect(str(source)) as src_conn,
        sqlite3.connect(str(destination)) as dst_conn,
    ):
        for table in _TRACKED_TABLES:
            src_count = _table_row_count(src_conn, table)
            dst_count = _table_row_count(dst_conn, table)
            if src_count is None and dst_count is None:
                continue
            verifications[table] = (
                src_count if src_count is not None else -1,
                dst_count if dst_count is not None else -1,
            )
    return verifications


def _insert_crmbuilder_engagement_row(now: datetime) -> None:
    """INSERT the CRMBUILDER engagement record into the meta DB."""
    factory = get_meta_session_factory()
    session = factory()
    try:
        session.execute(
            insert(EngagementRow).values(
                engagement_identifier=_CRMBUILDER_IDENTIFIER,
                engagement_code=_CRMBUILDER_CODE,
                engagement_name=_CRMBUILDER_NAME,
                engagement_purpose=_CRMBUILDER_PURPOSE,
                engagement_status="active",
                engagement_last_opened_at=None,
                engagement_export_dir=str(_dogfood_export_dir().resolve()),
                engagement_created_at=now,
                engagement_updated_at=now,
                engagement_deleted_at=None,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _atomic_write_json(path: Path, payload: dict | list[dict]) -> None:
    """Write ``payload`` to ``path`` atomically (tempfile + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        suffix=".tmp", prefix=path.name, dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _meta_export_dir() -> Path:
    """Where to land ``engagements.json`` snapshot for the meta DB."""
    return _dogfood_export_dir() / "meta"


def _refresh_meta_snapshot() -> None:
    """Best-effort regeneration of ``db-export/meta/engagements.json``.

    Logs but does not raise on failure — the meta-DB snapshot hook
    proper lands in slice B; slice A just seeds the file so the v0.5
    export tree is complete after migration.
    """
    try:
        out_dir = _meta_export_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        factory = get_meta_session_factory()
        session = factory()
        try:
            rows = (
                session.query(EngagementRow)
                .order_by(EngagementRow.engagement_identifier)
                .all()
            )
            payload = [
                {
                    "engagement_identifier": r.engagement_identifier,
                    "engagement_code": r.engagement_code,
                    "engagement_name": r.engagement_name,
                    "engagement_purpose": r.engagement_purpose,
                    "engagement_status": r.engagement_status,
                    "engagement_last_opened_at": (
                        r.engagement_last_opened_at.isoformat()
                        if r.engagement_last_opened_at
                        else None
                    ),
                    "engagement_export_dir": r.engagement_export_dir,
                    "engagement_created_at": (
                        r.engagement_created_at.isoformat()
                        if r.engagement_created_at
                        else None
                    ),
                    "engagement_updated_at": (
                        r.engagement_updated_at.isoformat()
                        if r.engagement_updated_at
                        else None
                    ),
                    "engagement_deleted_at": (
                        r.engagement_deleted_at.isoformat()
                        if r.engagement_deleted_at
                        else None
                    ),
                }
                for r in rows
            ]
        finally:
            session.close()
        snapshot_path = out_dir / "engagements.json"
        _atomic_write_json(snapshot_path, payload)
    except Exception:
        _log.exception("meta snapshot refresh failed (non-fatal)")


def run_dogfood_migration() -> MigrationResult:
    """Execute the eight-step dogfood migration. Idempotent on rerun.

    Returns a :class:`MigrationResult` capturing per-step progress.
    A successful rerun (already migrated) returns
    ``steps_completed=["already_migrated"]`` immediately.
    """
    result = MigrationResult(success=False)

    if not needs_migration():
        # Either fresh install (no v2.db) or already-migrated.
        if not _v2_db_path().exists():
            _log.debug(
                "dogfood migration skipped: v2.db not present (fresh install)"
            )
        else:
            _log.debug(
                "dogfood migration skipped: already-migrated state detected"
            )
        result.success = True
        result.steps_completed.append("already_migrated")
        return result

    legacy = _v2_db_path()
    backup = _backup_path()
    destination = engagement_db_path(_CRMBUILDER_CODE)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Step 1 — backup.
        shutil.copy2(legacy, backup)
        if backup.stat().st_size != legacy.stat().st_size:
            raise RuntimeError(
                "backup size mismatch — refusing to proceed"
            )
        result.steps_completed.append("backup")
        _log.info("dogfood migration: backup created at %s", backup)

        # Step 2 — create meta DB and run Alembic.
        reset_meta_engine_cache()
        meta_db_path().parent.mkdir(parents=True, exist_ok=True)
        # ``run_meta_migrations`` handles both fresh-create and apply-to-head.
        run_meta_migrations()
        # Force engine to point at the newly created file.
        reset_meta_engine_cache()
        bootstrap_meta_db()
        result.steps_completed.append("meta_db_created")
        _log.info("dogfood migration: meta DB ready at %s", meta_db_path())

        # Step 3 — INSERT CRMBUILDER row.
        now = datetime.now(UTC)
        _insert_crmbuilder_engagement_row(now)
        result.steps_completed.append("crmbuilder_row_inserted")
        _log.info("dogfood migration: CRMBUILDER row inserted")

        # Step 4 — copy v2.db to engagements/CRMBUILDER.db.
        shutil.copy2(legacy, destination)
        result.steps_completed.append("v2_db_copied")
        _log.info(
            "dogfood migration: v2.db copied to %s", destination
        )

        # Step 5 — verify row counts.
        verifications = _verify_row_counts(legacy, destination)
        result.row_count_verifications = verifications
        mismatches = [
            (table, src, dst)
            for table, (src, dst) in verifications.items()
            if src != dst
        ]
        if mismatches:
            details = ", ".join(
                f"{t}: source={s} dest={d}" for t, s, d in mismatches
            )
            raise RuntimeError(
                f"row-count verification failed: {details}"
            )
        result.steps_completed.append("row_counts_verified")
        _log.info(
            "dogfood migration: row counts verified across %d tables",
            len(verifications),
        )

        # Step 6 — delete original v2.db (backup persists).
        legacy.unlink()
        result.steps_completed.append("v2_db_deleted")
        _log.info("dogfood migration: legacy v2.db deleted")

        # Step 7 — refresh JSON snapshots.
        _refresh_meta_snapshot()
        result.steps_completed.append("snapshots_refreshed")

        # Step 8 — write current_engagement.json.
        _atomic_write_json(
            _current_engagement_path(),
            {
                "engagement_identifier": _CRMBUILDER_IDENTIFIER,
                "engagement_code": _CRMBUILDER_CODE,
                "set_at": datetime.now(UTC).isoformat(),
            },
        )
        result.steps_completed.append("current_engagement_written")
        _log.info(
            "dogfood migration: current_engagement.json written at %s",
            _current_engagement_path(),
        )

        result.success = True
        return result

    except Exception as exc:
        _log.exception("dogfood migration failed")
        result.error = str(exc)
        result.success = False
        return result
