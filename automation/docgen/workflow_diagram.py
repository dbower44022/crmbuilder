"""Workflow diagram integration for the Document Generator.

Implements L2 PRD Section 13.12 — checks for a PNG diagram at the expected
path convention and returns the path if it exists.

Convention: PRDs/{domain_code}/{PROCESS-CODE}-workflow.png
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


def get_diagram_path(
    conn: sqlite3.Connection,
    process_id: int,
    project_folder: str | Path,
) -> Path | None:
    """Return the workflow diagram path if the PNG exists.

    :param conn: Client database connection.
    :param process_id: The Process.id to look up.
    :param project_folder: Root of the client's project repository.
    :returns: Path to the PNG if it exists, None otherwise.
    """
    row = conn.execute(
        "SELECT p.code, p.domain_id FROM Process p WHERE p.id = ?",
        (process_id,),
    ).fetchone()
    if not row:
        return None

    process_code, domain_id = row

    # Build domain path parts (handles sub-domains)
    domain_parts = _get_domain_path_parts(conn, domain_id)
    if not domain_parts:
        return None

    root = Path(project_folder)
    png_path = root / "PRDs" / Path(*domain_parts) / f"{process_code}-workflow.png"

    if png_path.exists():
        return png_path
    return None


def _get_domain_path_parts(
    conn: sqlite3.Connection, domain_id: int
) -> list[str]:
    """Return path segments for a domain, handling sub-domain nesting."""
    row = conn.execute(
        "SELECT code, parent_domain_id FROM Domain WHERE id = ?",
        (domain_id,),
    ).fetchone()
    if not row:
        return []
    code, parent_id = row
    if parent_id is not None:
        parent_row = conn.execute(
            "SELECT code FROM Domain WHERE id = ?", (parent_id,)
        ).fetchone()
        if parent_row:
            return [parent_row[0], code]
    return [code]
