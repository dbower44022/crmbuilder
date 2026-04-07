"""Connection management for CRM Builder Automation databases.

Provides open/close functions, context manager support, and transaction
helpers for both master and client databases. Every connection enables
foreign key enforcement via PRAGMA foreign_keys = ON.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


def open_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled.

    :param db_path: Path to the SQLite database file.
    :returns: An open sqlite3.Connection with foreign_keys ON.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    """Close a SQLite connection.

    :param conn: The connection to close.
    """
    conn.close()


@contextmanager
def connect(db_path: str | Path):
    """Context manager that opens a connection and closes it on exit.

    Foreign keys are enabled on the connection. The connection is closed
    even if an exception occurs.

    :param db_path: Path to the SQLite database file.
    :yields: An open sqlite3.Connection.
    """
    conn = open_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager for an explicit transaction.

    Begins a transaction, yields, and commits on success. On exception
    the transaction is rolled back and the exception re-raised.

    :param conn: An open sqlite3.Connection.
    """
    conn.execute("BEGIN")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
