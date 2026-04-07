"""Commit module for the Import Processor.

Implements Stage 6 (Section 11.1) and audit trail (Section 11.9).
Wraps all writes in a single transaction. Creates ChangeLog entries for
every committed record.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime
from typing import Any

from automation.db.connection import transaction
from automation.importer.proposed import ProposedBatch, ProposedRecord


@dataclasses.dataclass
class CommitResult:
    """Result of a commit operation."""

    created_count: int
    updated_count: int
    rejected_count: int
    total_proposed: int
    created_ids: dict[str, list[int]]  # table_name -> list of new ids
    import_status: str  # 'imported', 'partial', 'rejected'
    has_updates: bool  # True if any update operations were committed
    master_write_errors: list[str] = dataclasses.field(default_factory=list)


def commit_batch(
    conn: sqlite3.Connection,
    ai_session_id: int,
    batch: ProposedBatch,
    accepted_paths: set[str] | None = None,
    master_conn: sqlite3.Connection | None = None,
) -> CommitResult:
    """Commit accepted records in a single atomic transaction.

    :param conn: Open client database connection.
    :param ai_session_id: The AISession.id.
    :param batch: The ProposedBatch to commit.
    :param accepted_paths: Set of source_payload_path strings for accepted
        records. None means accept all.
    :param master_conn: Optional master database connection for Client updates.
    :returns: CommitResult with counts and new ids.
    :raises: Any exception from the transaction rolls back all writes.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    created_count = 0
    updated_count = 0
    rejected_count = 0
    created_ids: dict[str, list[int]] = {}
    has_updates = False

    # Build accepted list
    accepted_records: list[ProposedRecord] = []
    for rec in batch.records:
        if accepted_paths is None or rec.source_payload_path in accepted_paths:
            accepted_records.append(rec)
        else:
            rejected_count += 1

    total_proposed = len(batch.records)

    # Determine import status
    if len(accepted_records) == 0:
        import_status = "rejected"
    elif rejected_count == 0:
        import_status = "imported"
    else:
        import_status = "partial"

    # Separate Client records (master db) from other records (client db).
    # Per ISS-010, master writes must happen AFTER the client transaction
    # succeeds to prevent cross-database inconsistency on rollback.
    client_table_records: list[ProposedRecord] = []
    other_records: list[ProposedRecord] = []
    for rec in accepted_records:
        if rec.table_name == "Client":
            client_table_records.append(rec)
        else:
            other_records.append(rec)

    # Phase 1 — Client transaction (atomic, all-or-nothing)
    batch_id_to_real_id: dict[str, int] = {}

    with transaction(conn):
        for rec in other_records:
            # Resolve intra-batch references
            resolved_values = dict(rec.values)
            for fk_col, batch_ref in rec.intra_batch_refs.items():
                if batch_ref in batch_id_to_real_id:
                    resolved_values[fk_col] = batch_id_to_real_id[batch_ref]

            if rec.action == "create":
                new_id = _insert_record(conn, rec.table_name, resolved_values, now)
                created_count += 1
                created_ids.setdefault(rec.table_name, []).append(new_id)

                # Register for intra-batch reference resolution
                if rec.batch_id:
                    batch_id_to_real_id[rec.batch_id] = new_id

                # ChangeLog: one entry for the insert
                _write_changelog_insert(
                    conn, ai_session_id, rec.table_name, new_id, now,
                )

            elif rec.action == "update":
                old_values = _get_current_values(
                    conn, rec.table_name, rec.target_id, resolved_values.keys(),
                )
                _update_record(conn, rec.table_name, rec.target_id, resolved_values, now)
                updated_count += 1
                has_updates = True

                # ChangeLog: one entry per changed field
                _write_changelog_updates(
                    conn, ai_session_id, rec.table_name, rec.target_id,
                    old_values, resolved_values, now,
                )

        # Update AISession inside the same transaction
        conn.execute(
            "UPDATE AISession SET import_status = ?, completed_at = ?, "
            "updated_at = ? WHERE id = ?",
            (import_status, now, now, ai_session_id),
        )

    # Phase 2 — Master writes (after client transaction succeeds)
    master_write_errors: list[str] = []
    if master_conn is not None:
        for rec in client_table_records:
            try:
                _commit_client_update(master_conn, rec, ai_session_id, now)
                updated_count += 1
                has_updates = True
            except Exception as exc:
                master_write_errors.append(
                    f"Failed to update Client id={rec.target_id}: {exc}"
                )

    return CommitResult(
        created_count=created_count,
        updated_count=updated_count,
        rejected_count=rejected_count,
        total_proposed=total_proposed,
        created_ids=created_ids,
        import_status=import_status,
        has_updates=has_updates,
        master_write_errors=master_write_errors,
    )


def _insert_record(
    conn: sqlite3.Connection,
    table_name: str,
    values: dict[str, Any],
    now: str,
) -> int:
    """INSERT a record and return the new id."""
    # Filter out None values for columns that have defaults
    insert_values = {k: v for k, v in values.items() if v is not None}

    columns = list(insert_values.keys())
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join(columns)

    cur = conn.execute(
        f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
        list(insert_values.values()),
    )
    return cur.lastrowid


def _update_record(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    values: dict[str, Any],
    now: str,
) -> None:
    """UPDATE an existing record by id."""
    # Add updated_at if the table has it
    update_values = dict(values)
    tables_with_updated_at = {
        "Domain", "Entity", "Field", "FieldOption", "Relationship",
        "Persona", "BusinessObject", "Process", "ProcessStep",
        "Requirement", "Decision", "OpenIssue", "LayoutPanel",
    }
    if table_name in tables_with_updated_at:
        update_values["updated_at"] = now

    set_clause = ", ".join(f"{col} = ?" for col in update_values.keys())
    conn.execute(
        f"UPDATE {table_name} SET {set_clause} WHERE id = ?",
        [*update_values.values(), record_id],
    )


def _get_current_values(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    columns: Any,
) -> dict[str, Any]:
    """Fetch current values for the given columns from an existing record."""
    col_list = list(columns)
    # Filter to only columns that exist — avoid querying for updated_at etc.
    # that we add ourselves
    col_names = ", ".join(col_list)
    try:
        row = conn.execute(
            f"SELECT {col_names} FROM {table_name} WHERE id = ?",
            (record_id,),
        ).fetchone()
    except Exception:
        return {}

    if row is None:
        return {}

    return dict(zip(col_list, row, strict=False))


def _write_changelog_insert(
    conn: sqlite3.Connection,
    session_id: int,
    table_name: str,
    record_id: int,
    now: str,
) -> None:
    """Write a ChangeLog entry for an INSERT operation."""
    conn.execute(
        "INSERT INTO ChangeLog (session_id, table_name, record_id, "
        "change_type, changed_at) VALUES (?, ?, ?, 'insert', ?)",
        (session_id, table_name, record_id, now),
    )


def _write_changelog_updates(
    conn: sqlite3.Connection,
    session_id: int,
    table_name: str,
    record_id: int,
    old_values: dict[str, Any],
    new_values: dict[str, Any],
    now: str,
) -> None:
    """Write ChangeLog entries for an UPDATE — one per changed field."""
    for col, new_val in new_values.items():
        old_val = old_values.get(col)
        if str(old_val) != str(new_val):
            conn.execute(
                "INSERT INTO ChangeLog (session_id, table_name, record_id, "
                "change_type, field_name, old_value, new_value, changed_at) "
                "VALUES (?, ?, ?, 'update', ?, ?, ?, ?)",
                (session_id, table_name, record_id,
                 col, str(old_val) if old_val is not None else None,
                 str(new_val) if new_val is not None else None, now),
            )


def _commit_client_update(
    master_conn: sqlite3.Connection,
    rec: ProposedRecord,
    ai_session_id: int,
    now: str,
) -> None:
    """Commit a Client table update to the master database."""
    update_values = dict(rec.values)
    update_values["updated_at"] = now
    set_clause = ", ".join(f"{col} = ?" for col in update_values.keys())
    master_conn.execute(
        f"UPDATE Client SET {set_clause} WHERE id = ?",
        [*update_values.values(), rec.target_id],
    )
    master_conn.commit()
