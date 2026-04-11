"""Client reachability check (pure Python, no Qt).

Verifies that a client's project folder and database file are
accessible and the database can be opened.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ReachabilityResult:
    """Result of a client reachability check.

    :param is_reachable: True if the client's database is accessible.
    :param error: Human-readable explanation when not reachable.
    """

    is_reachable: bool
    error: str | None = None


def check_reachability(
    project_folder: str | None,
    code: str,
) -> ReachabilityResult:
    """Check whether a client's project folder and database are reachable.

    Verifies three conditions in order:

    1. ``project_folder`` is not None and exists on disk as a directory.
    2. ``{project_folder}/.crmbuilder/{code}.db`` exists as a file.
    3. The database opens and a trivial ``SELECT 1`` succeeds.

    The probe connection is closed before returning.

    :param project_folder: Absolute path to the client's project folder.
    :param code: Client code (used to derive database filename).
    :returns: A :class:`ReachabilityResult`.
    """
    if not project_folder:
        return ReachabilityResult(
            is_reachable=False,
            error="Project folder is not set.",
        )

    folder = Path(project_folder)
    if not folder.is_dir():
        return ReachabilityResult(
            is_reachable=False,
            error=f"Project folder does not exist: {project_folder}",
        )

    db_path = folder / ".crmbuilder" / f"{code}.db"
    if not db_path.is_file():
        return ReachabilityResult(
            is_reachable=False,
            error=f"Database file not found: {db_path}",
        )

    try:
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return ReachabilityResult(
            is_reachable=False,
            error=f"Database failed to open: {exc}",
        )

    return ReachabilityResult(is_reachable=True)
