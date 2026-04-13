# automation.docgen.queries — Data query layer for document generation.

"""Shared helpers for document generation query modules."""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)


def get_client_row(
    master_conn: sqlite3.Connection,
    client_conn: sqlite3.Connection | None = None,
    columns: str = "name, code",
) -> tuple | None:
    """Look up the correct Client row from the master database.

    Derives the client code from the client database filename
    (e.g. ``ABCO.db`` -> code ``'ABCO'``).  Falls back to
    ``ORDER BY id LIMIT 1`` when the code cannot be determined.

    :param master_conn: Master database connection.
    :param client_conn: Client database connection (used to detect code).
    :param columns: Comma-separated column names to SELECT.
    :returns: Row tuple, or None if not found.
    """
    client_code = _detect_client_code(client_conn) if client_conn else None
    if client_code:
        row = master_conn.execute(
            f"SELECT {columns} FROM Client WHERE code = ? LIMIT 1",
            (client_code,),
        ).fetchone()
        if row:
            return row

    # Fallback: first client
    return master_conn.execute(
        f"SELECT {columns} FROM Client ORDER BY id LIMIT 1"
    ).fetchone()


def _detect_client_code(conn: sqlite3.Connection | None) -> str | None:
    """Derive the client code from the database file path.

    Client databases are stored as ``{project_folder}/.crmbuilder/{CODE}.db``.

    :param conn: Client database connection.
    :returns: Client code string, or None.
    """
    if conn is None:
        return None
    try:
        row = conn.execute("PRAGMA database_list").fetchone()
        if row and row[2]:
            from pathlib import Path
            code = Path(row[2]).stem
            if code and code.upper() == code and len(code) >= 2:
                return code
    except Exception:
        pass
    return None
