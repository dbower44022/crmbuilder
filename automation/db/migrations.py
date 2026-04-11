"""Versioned schema migration runner for CRM Builder Automation databases.

Each database (master and client) has a schema_version table that tracks
which migrations have been applied. The migration runner applies versioned
migrations in order and is idempotent.

Migration sources:
  - _master_v1: Initial Client table (L2 PRD §3.1 original)
  - _master_v2: L2 PRD v1.16 §3.1 — add project_folder, deployment_model,
    last_opened_at to Client; backfill project_folder from database_path
  - _client_v1: Initial 25-table client schema (L2 PRD §4–§8)
  - _client_v2: Add action_required to ChangeImpact (ISS-012)
  - _client_v3: L2 PRD v1.16 §6.5 Instance table, §6.6 DeploymentRun table
"""

import logging
import re
import sqlite3
from collections.abc import Callable

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
    SCHEMA_VERSION_TABLE as MASTER_VERSION_TABLE,
)
from automation.db.master_schema import (
    get_master_schema_sql,
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


MASTER_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _master_v1),
    (2, _master_v2),
]


def run_master_migrations(db_path: str) -> sqlite3.Connection:
    """Open the master database and apply any pending migrations.

    Creates the schema_version table if it does not exist. Returns the
    open connection so callers can use it immediately.

    :param db_path: Path to the master database file.
    :returns: An open sqlite3.Connection with all migrations applied.
    """
    conn = open_connection(db_path)
    conn.execute(MASTER_VERSION_TABLE)
    conn.commit()
    current = _get_current_version(conn)
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
    Step 15 needs this column for administrator review actions
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
