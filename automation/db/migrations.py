"""Versioned schema migration runner for CRM Builder Automation databases.

Each database (master and client) has a schema_version table that tracks
which migrations have been applied. The migration runner applies versioned
migrations in order and is idempotent.
"""

import sqlite3
from collections.abc import Callable

from automation.db.client_schema import (
    SCHEMA_VERSION_TABLE as CLIENT_VERSION_TABLE,
)
from automation.db.client_schema import (
    get_client_schema_sql,
)
from automation.db.connection import open_connection
from automation.db.master_schema import (
    SCHEMA_VERSION_TABLE as MASTER_VERSION_TABLE,
)
from automation.db.master_schema import (
    get_master_schema_sql,
)

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


MASTER_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _master_v1),
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


CLIENT_MIGRATIONS: list[tuple[int, Migration]] = [
    (1, _client_v1),
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
