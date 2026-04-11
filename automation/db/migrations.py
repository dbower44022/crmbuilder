"""Versioned schema migration runner for CRM Builder Automation databases.

Each database (master and client) has a schema_version table that tracks
which migrations have been applied. The migration runner applies versioned
migrations in order and is idempotent.

Migration sources:
  - _master_v1: Initial Client table (L2 PRD §3.1 original)
  - _master_v2: L2 PRD v1.16 §3.1 — add project_folder, deployment_model,
    last_opened_at to Client; backfill project_folder from database_path
  - _master_v3: Rebuild Client table — relax NOT NULL on database_path
  - _client_v1: Initial 25-table client schema (L2 PRD §4–§8)
  - _client_v2: Add action_required to ChangeImpact (ISS-012)
  - _client_v3: L2 PRD v1.16 §6.5 Instance table, §6.6 DeploymentRun table
"""

import logging
import re
import shutil
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from automation.db.client_schema import (
    DEPLOYMENT_RUN_TABLE,
    INSTANCE_DEFAULT_INDEX,
    INSTANCE_TABLE,
    get_client_schema_sql,
)
from automation.db.client_schema import (
    SCHEMA_VERSION_TABLE as CLIENT_VERSION_TABLE,
)
from automation.db.connection import open_connection
from automation.db.master_schema import (
    CLIENT_TABLE,
    get_master_schema_sql,
)
from automation.db.master_schema import (
    SCHEMA_VERSION_TABLE as MASTER_VERSION_TABLE,
)

logger = logging.getLogger(__name__)

# Type alias for a migration function
Migration = Callable[[sqlite3.Connection], None]


def _get_current_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if no migrations applied."""
    row = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()
    return row[0] if row[0] is not None else 0


def _apply_migration(
    conn: sqlite3.Connection,
    version: int,
    migrate_fn: Migration,
) -> None:
    """Apply a single migration and record it in schema_version."""
    migrate_fn(conn)
    conn.execute(
        "INSERT INTO schema_version (version) VALUES (?)", (version,)
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Master database migrations
# ---------------------------------------------------------------------------

def _master_v1(conn: sqlite3.Connection) -> None:
    """Initial master database schema — Client table."""
    for stmt in get_master_schema_sql():
        conn.execute(stmt)


def _master_v2(conn: sqlite3.Connection) -> None:
    """L2 PRD v1.16 §3.1 — add project_folder, deployment_model, last_opened_at.

    Idempotent: checks column existence via PRAGMA table_info before each
    ALTER TABLE ADD COLUMN.

    The project_folder column is NOT NULL in the fresh-table definition
    (master_schema.py). For existing databases, SQLite's ALTER TABLE ADD
    COLUMN with NOT NULL requires a default, so we add it as nullable here
    and backfill from database_path. Existing databases will not have the
    NOT NULL constraint on project_folder; fresh databases get it from the
    rewritten CLIENT_TABLE definition. This tradeoff is acceptable because
    the application enforces the constraint in code.
    """
    cols = conn.execute("PRAGMA table_info(Client)").fetchall()
    col_names = {row[1] for row in cols}

    if "project_folder" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN project_folder TEXT")

    if "deployment_model" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN deployment_model TEXT")

    if "last_opened_at" not in col_names:
        conn.execute("ALTER TABLE Client ADD COLUMN last_opened_at TIMESTAMP")

    # Backfill project_folder from database_path for existing rows.
    # Expected pattern: {project_folder}/.crmbuilder/{code}.db
    # We strip the trailing /.crmbuilder/{code}.db segment.
    rows = conn.execute(
        "SELECT id, code, database_path FROM Client "
        "WHERE project_folder IS NULL AND database_path IS NOT NULL"
    ).fetchall()
    pattern = re.compile(r"^(.+)/\.crmbuilder/[A-Z][A-Z0-9]{1,9}\.db$")
    for row_id, code, db_path in rows:
        match = pattern.match(db_path)
        if match:
            conn.execute(
                "UPDATE Client SET project_folder = ? WHERE id = ?",
                (match.group(1), row_id),
            )
        else:
            logger.warning(
                "Client id=%d code=%s: database_path '%s' does not match "
                "expected pattern; leaving project_folder NULL",
                row_id,
                code,
                db_path,
            )


def _master_v3(conn: sqlite3.Connection) -> None:
    """Rebuild Client table to match current master_schema.py definition.

    Relaxes the NOT NULL constraint on database_path that exists in pre-v1.16
    databases. Uses the SQLite 12-step table redefinition pattern because
    ALTER COLUMN is not supported.

    Pre-check: aborts if any Client rows have NULL project_folder, since the
    new table enforces NOT NULL on that column.
    """
    # Pre-check: ensure no rows have NULL project_folder
    bad_rows = conn.execute(
        "SELECT id, code FROM Client WHERE project_folder IS NULL"
    ).fetchall()
    if bad_rows:
        lines = [
            f"  - Client id={row[0]} code={row[1]}" for row in bad_rows
        ]
        raise RuntimeError(
            "Cannot apply master migration v3: the following Client rows have "
            "NULL project_folder and cannot be migrated to the new schema. "
            "Resolve manually before running the migration.\n"
            + "\n".join(lines)
        )

    # Build CREATE TABLE Client_new from the canonical CLIENT_TABLE constant
    create_new = CLIENT_TABLE.replace(
        "CREATE TABLE Client", "CREATE TABLE Client_new", 1
    )

    # Save and disable Python's automatic transaction handling so we can
    # control BEGIN/COMMIT/ROLLBACK explicitly (required because the rebuild
    # mixes DDL and DML, and Python's implicit commit-before-DDL would break
    # atomicity).
    fk_setting = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    orig_isolation = conn.isolation_level
    conn.isolation_level = None

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN")
        conn.execute(create_new)
        conn.execute(
            "INSERT INTO Client_new "
            "(id, name, code, description, database_path, "
            "organization_overview, project_folder, crm_platform, "
            "deployment_model, last_opened_at, created_at, updated_at) "
            "SELECT id, name, code, description, database_path, "
            "organization_overview, project_folder, crm_platform, "
            "deployment_model, last_opened_at, created_at, updated_at "
            "FROM Client"
        )
        conn.execute("DROP TABLE Client")
        conn.execute("ALTER TABLE Client_new RENAME TO Client")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.execute("DROP TABLE IF EXISTS Client_new")
        raise
    finally:
        conn.execute(f"PRAGMA foreign_keys = {'ON' if fk_setting else 'OFF'}")
        conn.isolation_level = orig_isolation


MASTER_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _master_v1),
    (2, _master_v2),
    (3, _master_v3),
]


def _heal_null_project_folders(
    conn: sqlite3.Connection,
    overrides: dict[str, str] | None,
) -> int:
    """Repair Client rows that have NULL project_folder before v3 runs.

    Applies overrides from the caller (keyed by Client.code), then
    returns the number of rows healed. Rows that cannot be repaired are
    left alone — v3's own pre-check will abort with a clear error.

    :param conn: Open connection to the master database.
    :param overrides: Mapping of client code → project_folder path.
    :returns: Number of rows updated.
    """
    if not overrides:
        return 0

    rows = conn.execute(
        "SELECT id, code FROM Client WHERE project_folder IS NULL"
    ).fetchall()

    healed = 0
    for row_id, code in rows:
        folder = overrides.get(code)
        if folder:
            conn.execute(
                "UPDATE Client SET project_folder = ? WHERE id = ?",
                (folder, row_id),
            )
            healed += 1
            logger.info(
                "Healed Client id=%d code=%s: set project_folder=%s",
                row_id,
                code,
                folder,
            )
        else:
            logger.warning(
                "Client id=%d code=%s has NULL project_folder and no "
                "override supplied; leaving unhealed",
                row_id,
                code,
            )

    # Warn about override keys that don't match any NULL-project_folder row
    null_codes = {code for _, code in rows}
    for code in overrides:
        if code not in null_codes:
            logger.warning(
                "Override for code=%s does not match any Client row with "
                "NULL project_folder; ignoring",
                code,
            )

    if healed:
        conn.commit()
    return healed


def _backup_master_db(db_path: str) -> str | None:
    """Create a timestamped backup of the master database.

    :param db_path: Path to the master database.
    :returns: Path to the backup file, or None if backup failed.
    """
    src = Path(db_path)
    if not src.exists():
        return None
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = src.parent / f"{src.stem}.db.pre-v3-heal-{ts}"
    try:
        shutil.copy2(str(src), str(backup_path))
        logger.info("Master database backed up to %s", backup_path)
        return str(backup_path)
    except OSError as exc:
        logger.error("Failed to back up master database: %s", exc)
        raise


def run_master_migrations(
    db_path: str,
    *,
    project_folder_overrides: dict[str, str] | None = None,
) -> sqlite3.Connection:
    """Open the master database and apply any pending migrations.

    Creates the schema_version table if it does not exist. Returns the
    open connection so callers can use it immediately.

    Before applying migrations, runs a heal step that repairs Client rows
    with NULL project_folder using the provided overrides. A backup of
    the database is created before any heal modifications.

    :param db_path: Path to the master database file.
    :param project_folder_overrides: Optional mapping of client code to
        project folder path for healing NULL project_folder values.
    :returns: An open sqlite3.Connection with all migrations applied.
    """
    conn = open_connection(db_path)
    conn.execute(MASTER_VERSION_TABLE)
    conn.commit()
    current = _get_current_version(conn)

    # Heal step: fix NULL project_folder rows before v3 runs
    if current < 3 and project_folder_overrides:
        # Check if there are rows that need healing
        bad_rows = conn.execute(
            "SELECT 1 FROM Client WHERE project_folder IS NULL"
        ).fetchone()
        if bad_rows:
            _backup_master_db(db_path)
            _heal_null_project_folders(conn, project_folder_overrides)

    for version, migrate_fn in MASTER_MIGRATIONS:
        if version > current:
            _apply_migration(conn, version, migrate_fn)
    return conn


# ---------------------------------------------------------------------------
# Client database migrations
# ---------------------------------------------------------------------------

def _client_v1(conn: sqlite3.Connection) -> None:
    """Initial client database schema — all 25 tables."""
    for stmt in get_client_schema_sql():
        conn.execute(stmt)


def _client_v2(conn: sqlite3.Connection) -> None:
    """Add action_required column to ChangeImpact (ISS-012).

    Deferred from Step 13 because Step 9 schema was locked.
    Step 15 needs this column for implementor review actions
    per L2 PRD Section 14.6.2.

    Idempotent: skips ALTER if the column already exists.
    """
    cols = conn.execute("PRAGMA table_info(ChangeImpact)").fetchall()
    col_names = {row[1] for row in cols}
    if "action_required" not in col_names:
        conn.execute(
            "ALTER TABLE ChangeImpact "
            "ADD COLUMN action_required INTEGER NOT NULL DEFAULT 0"
        )


def _client_v3(conn: sqlite3.Connection) -> None:
    """L2 PRD v1.16 §6.5 Instance table, §6.6 DeploymentRun table.

    Uses CREATE TABLE IF NOT EXISTS / CREATE UNIQUE INDEX IF NOT EXISTS
    for idempotency.
    """
    conn.execute(INSTANCE_TABLE.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS "))
    conn.execute(INSTANCE_DEFAULT_INDEX)
    conn.execute(
        DEPLOYMENT_RUN_TABLE.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ")
    )


CLIENT_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _client_v1),
    (2, _client_v2),
    (3, _client_v3),
]


def run_client_migrations(db_path: str) -> sqlite3.Connection:
    """Open a client database and apply any pending migrations.

    Creates the schema_version table if it does not exist. Returns the
    open connection so callers can use it immediately.

    :param db_path: Path to the client database file.
    :returns: An open sqlite3.Connection with all migrations applied.
    """
    conn = open_connection(db_path)
    conn.execute(CLIENT_VERSION_TABLE)
    conn.commit()
    current = _get_current_version(conn)
    for version, migrate_fn in CLIENT_MIGRATIONS:
        if version > current:
            _apply_migration(conn, version, migrate_fn)
    return conn
