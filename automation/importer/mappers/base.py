"""Shared helpers for all payload mappers.

Common logic for decision/issue mapping, scope resolution, and
revision matching used across all nine mappers.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.proposed import ProposedRecord


def resolve_by_code(
    conn: sqlite3.Connection,
    table: str,
    code_column: str,
    code_value: str,
) -> int | None:
    """Resolve a code/identifier to a record id.

    :returns: The record id, or None if not found.
    """
    row = conn.execute(
        f"SELECT id FROM {table} WHERE {code_column} = ?",
        (code_value,),
    ).fetchone()
    return row[0] if row else None


def resolve_by_name(
    conn: sqlite3.Connection,
    table: str,
    name: str,
) -> int | None:
    """Resolve a name to a record id.

    :returns: The record id, or None if not found.
    """
    row = conn.execute(
        f"SELECT id FROM {table} WHERE name = ?",
        (name,),
    ).fetchone()
    return row[0] if row else None


def resolve_field_by_name(
    conn: sqlite3.Connection,
    entity_id: int,
    field_name: str,
) -> int | None:
    """Resolve a field name within an entity to a Field id."""
    row = conn.execute(
        "SELECT id FROM Field WHERE entity_id = ? AND name = ?",
        (entity_id, field_name),
    ).fetchone()
    return row[0] if row else None


def find_existing_for_revision(
    conn: sqlite3.Connection,
    table: str,
    id_column: str,
    id_value: str,
) -> int | None:
    """For revision sessions, find an existing record by identifier.

    :returns: The existing record id, or None.
    """
    return resolve_by_code(conn, table, id_column, id_value)


def find_field_for_revision(
    conn: sqlite3.Connection,
    entity_id: int,
    field_name: str,
) -> int | None:
    """For revision sessions, find an existing Field by name within entity."""
    return resolve_field_by_name(conn, entity_id, field_name)


def map_decisions(
    payload_decisions: list[dict],
    conn: sqlite3.Connection,
    session_type: str,
    ai_session_id: int,
    base_path: str = "decisions",
) -> list[ProposedRecord]:
    """Map envelope-level decisions to proposed Decision records.

    Per Section 11.8.1.
    """
    records: list[ProposedRecord] = []
    for i, dec in enumerate(payload_decisions):
        identifier = dec.get("identifier", "")
        path = f"{base_path}[{i}]"

        values: dict[str, Any] = {
            "identifier": identifier,
            "title": dec.get("title", ""),
            "description": dec.get("description", ""),
            "status": dec.get("status", "proposed"),
        }

        # Resolve scope references
        scope = dec.get("scope", {})
        intra_refs: dict[str, str] = {}
        for scope_key in ("domain_id", "entity_id", "process_id",
                          "field_id", "requirement_id", "business_object_id"):
            scope_val = scope.get(scope_key)
            if scope_val is not None:
                values[scope_key] = scope_val

        # Handle locked status
        if values.get("status") == "locked":
            values["locked_by_session_id"] = ai_session_id

        values["created_by_session_id"] = ai_session_id

        # Revision matching
        action = "create"
        target_id = None
        if session_type in ("revision", "clarification") and identifier:
            existing_id = find_existing_for_revision(
                conn, "Decision", "identifier", identifier
            )
            if existing_id is not None:
                action = "update"
                target_id = existing_id
                values.pop("created_by_session_id", None)

        records.append(ProposedRecord(
            table_name="Decision",
            action=action,
            target_id=target_id,
            values=values,
            source_payload_path=path,
            intra_batch_refs=intra_refs,
            batch_id=f"batch:decision:{identifier}" if identifier else None,
        ))

    return records


def map_open_issues(
    payload_issues: list[dict],
    conn: sqlite3.Connection,
    session_type: str,
    ai_session_id: int,
    base_path: str = "open_issues",
) -> list[ProposedRecord]:
    """Map envelope-level open issues to proposed OpenIssue records.

    Per Section 11.8.2.
    """
    records: list[ProposedRecord] = []
    for i, iss in enumerate(payload_issues):
        identifier = iss.get("identifier", "")
        path = f"{base_path}[{i}]"

        values: dict[str, Any] = {
            "identifier": identifier,
            "title": iss.get("title", ""),
            "description": iss.get("description", ""),
            "status": iss.get("status", "open"),
            "priority": iss.get("priority"),
        }

        # Resolve scope references
        scope = iss.get("scope", {})
        for scope_key in ("domain_id", "entity_id", "process_id",
                          "field_id", "requirement_id", "business_object_id"):
            scope_val = scope.get(scope_key)
            if scope_val is not None:
                values[scope_key] = scope_val

        # Handle resolved status
        if values.get("status") == "resolved":
            values["resolved_by_session_id"] = ai_session_id
            if iss.get("resolution"):
                values["resolution"] = iss["resolution"]

        values["created_by_session_id"] = ai_session_id

        # Revision matching
        action = "create"
        target_id = None
        if session_type in ("revision", "clarification") and identifier:
            existing_id = find_existing_for_revision(
                conn, "OpenIssue", "identifier", identifier
            )
            if existing_id is not None:
                action = "update"
                target_id = existing_id
                values.pop("created_by_session_id", None)

        records.append(ProposedRecord(
            table_name="OpenIssue",
            action=action,
            target_id=target_id,
            values=values,
            source_payload_path=path,
            batch_id=f"batch:openissue:{identifier}" if identifier else None,
        ))

    return records
