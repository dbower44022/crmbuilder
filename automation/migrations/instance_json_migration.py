"""One-time migration: legacy data/instances/*.json → per-client Instance table.

Reads existing JSON instance profiles, resolves each to a client by
matching ``project_folder``, and inserts into the client's Instance table.

This module is Qt-free and unit-testable.  It exposes a single public
entry point: ``run_migration(master_db_path, instances_dir)``.

ISS-017 — L2 PRD v1.16 §16.17.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Environment substrings that override the default "production" assignment.
_ENV_KEYWORDS: dict[str, str] = {
    "test": "test",
    "dev": "test",       # dev maps to test (closest valid value)
    "staging": "staging",
    "stage": "staging",
}


@dataclasses.dataclass
class MigrationWarning:
    """A single warning from the migration."""

    file: str
    reason: str


@dataclasses.dataclass
class MigrationReport:
    """Summary of a migration run."""

    files_scanned: int = 0
    rows_inserted: int = 0
    already_migrated: int = 0
    skipped: int = 0
    skip_reasons: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    warnings: list[MigrationWarning] = dataclasses.field(default_factory=list)
    nothing_to_migrate: bool = False


def _derive_code(name: str, existing_codes: set[str]) -> str:
    """Derive an Instance code from a legacy name/filename.

    Strips non-alphanumeric characters, uppercases, truncates to 10 chars,
    and appends a numeric suffix on collision.

    :param name: Legacy instance name or filename stem.
    :param existing_codes: Codes already used in this client's Instance table.
    :returns: A valid code string.
    """
    # Strip non-alphanumeric, uppercase, truncate
    raw = re.sub(r"[^A-Za-z0-9]", "", name).upper()
    if not raw or not raw[0].isalpha():
        raw = "X" + raw
    # Ensure minimum length 2
    if len(raw) < 2:
        raw = raw + "X" * (2 - len(raw))
    base = raw[:10]

    candidate = base
    suffix = 2
    while candidate in existing_codes:
        suffix_str = str(suffix)
        # Truncate base to leave room for suffix
        max_base = 10 - len(suffix_str)
        candidate = base[:max_base] + suffix_str
        suffix += 1

    return candidate


def _infer_environment(name: str) -> str:
    """Infer the environment from a legacy instance name.

    :param name: Legacy instance name.
    :returns: One of 'test', 'staging', 'production'.
    """
    lower = name.lower()
    for keyword, env in _ENV_KEYWORDS.items():
        if keyword in lower:
            return env
    return "production"


def _load_clients(master_db_path: str) -> list[dict]:
    """Load all clients from the master database.

    :param master_db_path: Path to master.db.
    :returns: List of dicts with id, code, project_folder, database_path.
    """
    conn = sqlite3.connect(master_db_path)
    try:
        rows = conn.execute(
            "SELECT id, code, project_folder, database_path FROM Client"
        ).fetchall()
    finally:
        conn.close()
    return [
        {"id": r[0], "code": r[1], "project_folder": r[2], "database_path": r[3]}
        for r in rows
    ]


def _resolve_client(
    project_folder: str | None, clients: list[dict]
) -> dict | None:
    """Match a legacy instance to a client by project_folder.

    :param project_folder: The project_folder from the legacy JSON.
    :param clients: All clients from the master database.
    :returns: The matching client dict, or None.
    """
    if not project_folder:
        return None
    # Normalize paths for comparison
    pf = str(Path(project_folder).resolve())
    matches = [
        c for c in clients
        if c["project_folder"]
        and str(Path(c["project_folder"]).resolve()) == pf
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _get_existing_codes(conn: sqlite3.Connection) -> set[str]:
    """Get all Instance codes already in the client database.

    :param conn: Per-client database connection.
    :returns: Set of code strings.
    """
    rows = conn.execute("SELECT code FROM Instance").fetchall()
    return {r[0] for r in rows}


def _instance_exists(conn: sqlite3.Connection, code: str) -> bool:
    """Check if an instance with the given code already exists.

    :param conn: Per-client database connection.
    :param code: The instance code.
    :returns: True if it exists.
    """
    row = conn.execute(
        "SELECT 1 FROM Instance WHERE code = ?", (code,)
    ).fetchone()
    return row is not None


def _has_default(conn: sqlite3.Connection) -> bool:
    """Check if any instance is marked as default.

    :param conn: Per-client database connection.
    :returns: True if a default instance exists.
    """
    row = conn.execute(
        "SELECT 1 FROM Instance WHERE is_default = 1"
    ).fetchone()
    return row is not None


def run_migration(
    master_db_path: str,
    instances_dir: str | Path,
) -> MigrationReport:
    """Run the legacy JSON instance migration.

    Scans ``instances_dir`` for ``*.json`` files (excluding ``*_deploy.json``),
    resolves each to a client, and inserts into the per-client Instance table.
    Successfully migrated files are renamed to ``*.json.migrated``.

    Safe to re-run: skips files that cannot be resolved, skips codes that
    already exist, and skips files already renamed to ``.migrated``.

    :param master_db_path: Path to the master database.
    :param instances_dir: Path to ``data/instances/``.
    :returns: MigrationReport summarizing the run.
    """
    report = MigrationReport()
    instances_path = Path(instances_dir)

    if not instances_path.is_dir():
        report.nothing_to_migrate = True
        return report

    json_files = sorted(
        p for p in instances_path.glob("*.json")
        if not p.stem.endswith("_deploy")
    )

    if not json_files:
        report.nothing_to_migrate = True
        return report

    report.files_scanned = len(json_files)

    # Load clients once
    try:
        clients = _load_clients(master_db_path)
    except Exception as exc:
        report.warnings.append(MigrationWarning(
            file="(master database)",
            reason=f"Could not load clients: {exc}",
        ))
        report.skipped = len(json_files)
        for f in json_files:
            report.skip_reasons.append((f.name, "master database unreadable"))
        return report

    if not clients:
        report.nothing_to_migrate = True
        return report

    # Cache of open client database connections: client_id → conn
    client_conns: dict[int, sqlite3.Connection] = {}
    # Track is_default assignment per client to set first migrated as default
    default_set: dict[int, bool] = {}

    try:
        for json_path in json_files:
            _migrate_one_file(
                json_path, clients, client_conns, default_set, report
            )
    finally:
        for conn in client_conns.values():
            try:
                conn.close()
            except Exception:
                pass

    return report


def _migrate_one_file(
    json_path: Path,
    clients: list[dict],
    client_conns: dict[int, sqlite3.Connection],
    default_set: dict[int, bool],
    report: MigrationReport,
) -> None:
    """Migrate a single JSON file.

    :param json_path: Path to the JSON file.
    :param clients: All clients from master database.
    :param client_conns: Cache of open client database connections.
    :param default_set: Tracks whether a default has been set per client.
    :param report: The migration report to update.
    """
    # Parse JSON
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        report.skipped += 1
        report.skip_reasons.append((json_path.name, f"parse error: {exc}"))
        return

    # Resolve client
    project_folder = data.get("project_folder")
    client = _resolve_client(project_folder, clients)
    if client is None:
        report.skipped += 1
        reason = (
            "no matching client"
            if project_folder
            else "no project_folder in JSON"
        )
        report.skip_reasons.append((json_path.name, reason))
        report.warnings.append(MigrationWarning(
            file=json_path.name, reason=reason,
        ))
        return

    # Open client database (cached)
    client_id = client["id"]
    if client_id not in client_conns:
        db_path = client["database_path"]
        if not db_path:
            report.skipped += 1
            report.skip_reasons.append(
                (json_path.name, f"client {client['code']} has no database_path")
            )
            return
        try:
            conn = sqlite3.connect(db_path)
            # Ensure Instance table exists (should from migrations)
            conn.execute("SELECT 1 FROM Instance LIMIT 0")
            client_conns[client_id] = conn
        except Exception as exc:
            report.skipped += 1
            report.skip_reasons.append(
                (json_path.name, f"cannot open client database: {exc}")
            )
            return
    conn = client_conns[client_id]

    # Derive code
    name = data.get("name", json_path.stem)
    existing_codes = _get_existing_codes(conn)
    code = _derive_code(name, existing_codes)

    # Check idempotency — if code already exists, skip
    if _instance_exists(conn, code):
        report.already_migrated += 1
        # Still rename if not yet renamed
        _rename_migrated(json_path)
        return

    # Infer environment
    environment = _infer_environment(name)

    # Map fields — auth_method "basic" means api_key=username, secret_key=password
    url = data.get("url")
    auth_method = data.get("auth_method", "api_key")
    if auth_method == "basic":
        username = data.get("api_key")
        password = data.get("secret_key")
    else:
        username = None
        password = data.get("api_key")

    # Determine is_default — first instance per client gets it
    is_default = False
    if not default_set.get(client_id, False):
        if not _has_default(conn):
            is_default = True
            default_set[client_id] = True

    # Insert
    now = datetime.now(UTC).isoformat()
    try:
        conn.execute(
            "INSERT INTO Instance "
            "(name, code, environment, url, username, password, description, "
            "is_default, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (name, code, environment, url, username, password, None,
             1 if is_default else 0, now, now),
        )
        conn.commit()
        report.rows_inserted += 1
    except sqlite3.Error as exc:
        report.skipped += 1
        report.skip_reasons.append(
            (json_path.name, f"insert failed: {exc}")
        )
        report.warnings.append(MigrationWarning(
            file=json_path.name, reason=f"insert failed: {exc}",
        ))
        return

    # Rename to .migrated
    _rename_migrated(json_path)


def _rename_migrated(json_path: Path) -> None:
    """Rename a JSON file to .migrated if not already renamed.

    :param json_path: Path to the JSON file.
    """
    migrated_path = json_path.with_suffix(".json.migrated")
    if json_path.exists() and not migrated_path.exists():
        try:
            json_path.rename(migrated_path)
        except OSError as exc:
            logger.warning(
                "Could not rename %s to .migrated: %s", json_path, exc
            )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point for ``crmbuilder-migrate-instances``."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    base = Path(__file__).resolve().parent.parent.parent
    master_db = base / "automation" / "data" / "master.db"
    instances_dir = base / "data" / "instances"

    if not master_db.exists():
        logger.info("Master database not found at %s — nothing to migrate.", master_db)
        return

    report = run_migration(str(master_db), instances_dir)
    _log_report(report)


def _log_report(report: MigrationReport) -> None:
    """Log the migration report summary.

    :param report: The migration report.
    """
    if report.nothing_to_migrate:
        logger.info("Instance migration: nothing to migrate.")
        return

    logger.info(
        "Instance migration complete: scanned=%d, inserted=%d, "
        "already_migrated=%d, skipped=%d",
        report.files_scanned,
        report.rows_inserted,
        report.already_migrated,
        report.skipped,
    )
    for filename, reason in report.skip_reasons:
        logger.info("  Skipped %s: %s", filename, reason)
    for warning in report.warnings:
        logger.warning("  Warning [%s]: %s", warning.file, warning.reason)
