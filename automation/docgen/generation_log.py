"""GenerationLog recording for the Document Generator.

Implements L2 PRD Section 13.11 — records each final generation event in the
GenerationLog table. Draft generation skips recording per Section 13.11.2.

The generated_at timestamp is set to the moment the file is written.
The git_commit_hash is populated after the local commit succeeds.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime

from automation.db.connection import transaction


@dataclasses.dataclass
class GenerationLogEntry:
    """A single GenerationLog record."""

    id: int
    work_item_id: int
    document_type: str
    file_path: str
    generated_at: str
    generation_mode: str
    git_commit_hash: str | None


def record(
    conn: sqlite3.Connection,
    work_item_id: int,
    document_type: str,
    file_path: str,
    generation_mode: str,
    git_commit_hash: str | None = None,
) -> int:
    """Write a GenerationLog row for a final generation.

    :param conn: Client database connection.
    :param work_item_id: The WorkItem.id that was generated.
    :param document_type: One of the eight document type strings.
    :param file_path: Output file path (relative to project folder).
    :param generation_mode: 'final' or 'draft'.
    :param git_commit_hash: Commit hash if git commit succeeded.
    :returns: The new GenerationLog.id.
    """
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO GenerationLog "
            "(work_item_id, document_type, file_path, generated_at, "
            "generation_mode, git_commit_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (work_item_id, document_type, file_path, now,
             generation_mode, git_commit_hash),
        )
        return cursor.lastrowid


def get_latest_for_work_item(
    conn: sqlite3.Connection,
    work_item_id: int,
    mode: str = "final",
) -> GenerationLogEntry | None:
    """Return the most recent GenerationLog entry for a work item.

    :param conn: Client database connection.
    :param work_item_id: The WorkItem.id to query.
    :param mode: Generation mode filter ('final' or 'draft').
    :returns: The most recent entry, or None if no entries exist.
    """
    row = conn.execute(
        "SELECT id, work_item_id, document_type, file_path, generated_at, "
        "generation_mode, git_commit_hash "
        "FROM GenerationLog "
        "WHERE work_item_id = ? AND generation_mode = ? "
        "ORDER BY generated_at DESC, id DESC LIMIT 1",
        (work_item_id, mode),
    ).fetchone()

    if not row:
        return None

    return GenerationLogEntry(
        id=row[0],
        work_item_id=row[1],
        document_type=row[2],
        file_path=row[3],
        generated_at=row[4],
        generation_mode=row[5],
        git_commit_hash=row[6],
    )
