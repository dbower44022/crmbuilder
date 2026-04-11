"""Pure-Python logic for the Data Browser (Section 14.8).

Record detail mapping, edit state management, FK resolution, and
schema introspection. No PySide6 imports.
"""

from __future__ import annotations

import dataclasses
import sqlite3
from datetime import UTC, datetime

from automation.db.connection import transaction

# Read-only fields that cannot be edited even in edit mode
READ_ONLY_FIELDS = {"id", "created_at", "updated_at", "created_by_session_id"}

# Tables in the client database that can be browsed
BROWSABLE_TABLES = [
    "Domain", "Entity", "Field", "FieldOption", "Relationship",
    "Persona", "BusinessObject", "Process", "ProcessStep", "Requirement",
    "ProcessEntity", "ProcessField", "ProcessPersona",
    "Decision", "OpenIssue",
    "LayoutPanel", "LayoutRow", "LayoutTab", "ListColumn",
]

# FK definitions: table -> list of (column_name, referenced_table)
FK_DEFINITIONS: dict[str, list[tuple[str, str]]] = {
    "Domain": [("parent_domain_id", "Domain"), ("created_by_session_id", "AISession")],
    "Entity": [("primary_domain_id", "Domain"), ("created_by_session_id", "AISession")],
    "Field": [("entity_id", "Entity"), ("created_by_session_id", "AISession")],
    "FieldOption": [("field_id", "Field"), ("created_by_session_id", "AISession")],
    "Relationship": [
        ("entity_id", "Entity"), ("entity_foreign_id", "Entity"),
        ("created_by_session_id", "AISession"),
    ],
    "Persona": [
        ("persona_entity_id", "Entity"), ("persona_field_id", "Field"),
        ("created_by_session_id", "AISession"),
    ],
    "BusinessObject": [
        ("resolved_to_entity_id", "Entity"), ("resolved_to_process_id", "Process"),
        ("resolved_to_persona_id", "Persona"), ("created_by_session_id", "AISession"),
    ],
    "Process": [("domain_id", "Domain"), ("created_by_session_id", "AISession")],
    "ProcessStep": [
        ("process_id", "Process"), ("performer_persona_id", "Persona"),
        ("created_by_session_id", "AISession"),
    ],
    "Requirement": [("process_id", "Process"), ("created_by_session_id", "AISession")],
    "ProcessEntity": [
        ("process_id", "Process"), ("entity_id", "Entity"),
        ("process_step_id", "ProcessStep"),
    ],
    "ProcessField": [
        ("process_id", "Process"), ("field_id", "Field"),
        ("process_step_id", "ProcessStep"),
    ],
    "ProcessPersona": [("process_id", "Process"), ("persona_id", "Persona")],
    "Decision": [
        ("domain_id", "Domain"), ("entity_id", "Entity"),
        ("process_id", "Process"), ("field_id", "Field"),
        ("requirement_id", "Requirement"), ("business_object_id", "BusinessObject"),
        ("superseded_by_id", "Decision"), ("created_by_session_id", "AISession"),
        ("locked_by_session_id", "AISession"),
    ],
    "OpenIssue": [
        ("domain_id", "Domain"), ("entity_id", "Entity"),
        ("process_id", "Process"), ("field_id", "Field"),
        ("requirement_id", "Requirement"), ("business_object_id", "BusinessObject"),
        ("resolved_by_decision_id", "Decision"),
        ("created_by_session_id", "AISession"), ("resolved_by_session_id", "AISession"),
    ],
    "LayoutPanel": [("entity_id", "Entity"), ("created_by_session_id", "AISession")],
    "LayoutRow": [
        ("panel_id", "LayoutPanel"), ("cell_1_field_id", "Field"),
        ("cell_2_field_id", "Field"),
    ],
    "LayoutTab": [("panel_id", "LayoutPanel")],
    "ListColumn": [("entity_id", "Entity"), ("field_id", "Field")],
}


@dataclasses.dataclass
class ColumnInfo:
    """Metadata about a single table column."""

    name: str
    col_type: str  # 'TEXT', 'INTEGER', 'BOOLEAN', 'REAL', 'TIMESTAMP', etc.
    is_fk: bool = False
    fk_table: str | None = None
    is_read_only: bool = False
    check_values: list[str] | None = None  # Enum values from CHECK constraint


@dataclasses.dataclass
class RecordDetail:
    """A loaded record with column metadata and values."""

    table_name: str
    record_id: int
    columns: list[ColumnInfo]
    values: dict[str, object]


@dataclasses.dataclass
class RelatedGroup:
    """A group of records that reference the current record via FK."""

    table_name: str
    fk_column: str
    records: list[dict[str, object]]
    display_column: str  # Column to use for display label


@dataclasses.dataclass
class ChangeLogEntry:
    """A ChangeLog row for the audit trail."""

    id: int
    session_id: int | None
    change_type: str
    field_name: str | None
    old_value: str | None
    new_value: str | None
    rationale: str | None
    changed_at: str
    source_label: str  # "AISession: <name>" or "Direct Edit"


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[ColumnInfo]:
    """Get column metadata for a table.

    :param conn: Database connection.
    :param table_name: Table to introspect.
    :returns: List of ColumnInfo.
    """
    pragma_rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()  # noqa: S608
    fk_map = dict(FK_DEFINITIONS.get(table_name, []))

    columns: list[ColumnInfo] = []
    for row in pragma_rows:
        col_name = row[1]
        col_type = row[2] or "TEXT"

        # Determine CHECK constraint values (for enums)
        check_values = _extract_check_values(conn, table_name, col_name)

        columns.append(ColumnInfo(
            name=col_name,
            col_type=col_type.upper(),
            is_fk=col_name in fk_map,
            fk_table=fk_map.get(col_name),
            is_read_only=col_name in READ_ONLY_FIELDS,
            check_values=check_values,
        ))
    return columns


def load_record(
    conn: sqlite3.Connection, table_name: str, record_id: int
) -> RecordDetail | None:
    """Load a single record with column metadata.

    :param conn: Database connection.
    :param table_name: Table to read from.
    :param record_id: Record ID.
    :returns: RecordDetail, or None if not found.
    """
    if table_name not in BROWSABLE_TABLES:
        return None

    columns = get_table_columns(conn, table_name)
    col_names = [c.name for c in columns]

    row = conn.execute(
        f"SELECT {', '.join(col_names)} FROM {table_name} WHERE id = ?",  # noqa: S608
        (record_id,),
    ).fetchone()
    if not row:
        return None

    values = dict(zip(col_names, row, strict=False))
    return RecordDetail(
        table_name=table_name,
        record_id=record_id,
        columns=columns,
        values=values,
    )


def load_related_records(
    conn: sqlite3.Connection, table_name: str, record_id: int
) -> list[RelatedGroup]:
    """Load records that reference this record via FK (back-references).

    :param conn: Database connection.
    :param table_name: Table of the current record.
    :param record_id: ID of the current record.
    :returns: List of RelatedGroup.
    """
    groups: list[RelatedGroup] = []

    for ref_table, fk_defs in FK_DEFINITIONS.items():
        for fk_col, ref_target in fk_defs:
            if ref_target != table_name:
                continue

            # Find records in ref_table where fk_col = record_id
            display_col = _get_display_column(conn, ref_table)
            rows = conn.execute(
                f"SELECT * FROM {ref_table} WHERE {fk_col} = ?",  # noqa: S608
                (record_id,),
            ).fetchall()
            if not rows:
                continue

            # Get column names
            pragma = conn.execute(f"PRAGMA table_info({ref_table})").fetchall()  # noqa: S608
            col_names = [p[1] for p in pragma]

            records = [dict(zip(col_names, r, strict=False)) for r in rows]
            groups.append(RelatedGroup(
                table_name=ref_table,
                fk_column=fk_col,
                records=records,
                display_column=display_col,
            ))

    return groups


def load_change_log(
    conn: sqlite3.Connection, table_name: str, record_id: int
) -> list[ChangeLogEntry]:
    """Load ChangeLog entries for a specific record.

    :param conn: Database connection.
    :param table_name: Table of the record.
    :param record_id: Record ID.
    :returns: ChangeLog entries, ordered by timestamp descending.
    """
    rows = conn.execute(
        "SELECT cl.id, cl.session_id, cl.change_type, cl.field_name, "
        "  cl.old_value, cl.new_value, cl.rationale, cl.changed_at, "
        "  s.session_type "
        "FROM ChangeLog cl "
        "LEFT JOIN AISession s ON cl.session_id = s.id "
        "WHERE cl.table_name = ? AND cl.record_id = ? "
        "ORDER BY cl.changed_at DESC, cl.id DESC",
        (table_name, record_id),
    ).fetchall()

    entries: list[ChangeLogEntry] = []
    for r in rows:
        if r[1] is not None and r[8] is not None:
            source_label = f"AISession ({r[8]})"
        else:
            source_label = "Direct Edit"
        entries.append(ChangeLogEntry(
            id=r[0], session_id=r[1], change_type=r[2],
            field_name=r[3], old_value=r[4], new_value=r[5],
            rationale=r[6], changed_at=r[7], source_label=source_label,
        ))
    return entries


def resolve_fk_label(
    conn: sqlite3.Connection, fk_table: str, fk_id: int | None
) -> str:
    """Resolve a foreign key ID to a display label.

    :param conn: Database connection.
    :param fk_table: Referenced table.
    :param fk_id: Foreign key value.
    :returns: Display label or "—" if not found.
    """
    if fk_id is None:
        return "—"

    display_col = _get_display_column(conn, fk_table)
    row = conn.execute(
        f"SELECT {display_col} FROM {fk_table} WHERE id = ?",  # noqa: S608
        (fk_id,),
    ).fetchone()
    if row:
        return f"{row[0]} (#{fk_id})"
    return f"#{fk_id} (not found)"


def get_fk_options(
    conn: sqlite3.Connection, fk_table: str
) -> list[tuple[int, str]]:
    """Get all records in a FK target table for dropdown population.

    :param conn: Database connection.
    :param fk_table: Referenced table.
    :returns: List of (id, display_label) tuples.
    """
    display_col = _get_display_column(conn, fk_table)
    rows = conn.execute(
        f"SELECT id, {display_col} FROM {fk_table} ORDER BY {display_col}",  # noqa: S608
    ).fetchall()
    return [(r[0], f"{r[1]} (#{r[0]})") for r in rows]


def save_record(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    changes: dict[str, object],
    rationale: str | None = None,
) -> None:
    """Save changes to a record with ChangeLog entries.

    :param conn: Database connection.
    :param table_name: Table of the record.
    :param record_id: Record ID.
    :param changes: Dict of field_name -> new_value.
    :param rationale: Implementor's rationale.
    """
    if not changes:
        return

    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    with transaction(conn):
        # Read old values
        col_names = list(changes.keys())
        placeholders = ", ".join(col_names)
        old_row = conn.execute(
            f"SELECT {placeholders} FROM {table_name} WHERE id = ?",  # noqa: S608
            (record_id,),
        ).fetchone()
        old_values = dict(zip(col_names, old_row, strict=False)) if old_row else {}

        # Update
        set_clause = ", ".join(f"{col} = ?" for col in changes)
        conn.execute(
            f"UPDATE {table_name} SET {set_clause}, updated_at = ? WHERE id = ?",  # noqa: S608
            [*changes.values(), now, record_id],
        )

        # Write ChangeLog entries (one per changed field)
        for field_name, new_value in changes.items():
            old_value = old_values.get(field_name)
            if str(old_value) != str(new_value):
                conn.execute(
                    "INSERT INTO ChangeLog "
                    "(session_id, table_name, record_id, change_type, "
                    "field_name, old_value, new_value, rationale, changed_at) "
                    "VALUES (NULL, ?, ?, 'update', ?, ?, ?, ?, ?)",
                    (table_name, record_id, field_name,
                     str(old_value) if old_value is not None else None,
                     str(new_value) if new_value is not None else None,
                     rationale, now),
                )


def delete_record(
    conn: sqlite3.Connection,
    table_name: str,
    record_id: int,
    rationale: str | None = None,
) -> None:
    """Delete a record with ChangeLog entries.

    :param conn: Database connection.
    :param table_name: Table of the record.
    :param record_id: Record ID.
    :param rationale: Implementor's rationale.
    """
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    with transaction(conn):
        conn.execute(
            f"DELETE FROM {table_name} WHERE id = ?",  # noqa: S608
            (record_id,),
        )
        conn.execute(
            "INSERT INTO ChangeLog "
            "(session_id, table_name, record_id, change_type, "
            "rationale, changed_at) "
            "VALUES (NULL, ?, ?, 'delete', ?, ?)",
            (table_name, record_id, rationale, now),
        )


def create_record(
    conn: sqlite3.Connection,
    table_name: str,
    values: dict[str, object],
) -> int:
    """Create a new record with ChangeLog entry.

    Inserts are exempt from pre-commit impact analysis per Section 12.2.

    :param conn: Database connection.
    :param table_name: Table to insert into.
    :param values: Dict of field_name -> value.
    :returns: New record ID.
    """
    now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M:%S")

    with transaction(conn):
        col_names = list(values.keys())
        placeholders = ", ".join("?" for _ in col_names)
        cols = ", ".join(col_names)
        cursor = conn.execute(
            f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})",  # noqa: S608
            list(values.values()),
        )
        new_id = cursor.lastrowid

        conn.execute(
            "INSERT INTO ChangeLog "
            "(session_id, table_name, record_id, change_type, changed_at) "
            "VALUES (NULL, ?, ?, 'insert', ?)",
            (table_name, new_id, now),
        )
        return new_id


def write_impact_rows(
    conn: sqlite3.Connection,
    change_log_ids: list[int],
    proposed_impacts: list,
) -> None:
    """Write ChangeImpact rows for direct edits (post-confirmation).

    :param conn: Database connection.
    :param change_log_ids: ChangeLog IDs from the write.
    :param proposed_impacts: ProposedImpact objects from analyze_proposed_change.
    """
    if not change_log_ids or not proposed_impacts:
        return

    # Use the first change_log_id as the reference
    cl_id = change_log_ids[0]
    for impact in proposed_impacts:
        conn.execute(
            "INSERT INTO ChangeImpact "
            "(change_log_id, affected_table, affected_record_id, "
            "impact_description, requires_review, reviewed, action_required) "
            "VALUES (?, ?, ?, ?, ?, FALSE, FALSE)",
            (cl_id, impact.affected_table, impact.affected_record_id,
             impact.impact_description, impact.requires_review),
        )


def infer_fk_from_context(
    table_name: str, context_table: str | None, context_id: int | None
) -> dict[str, int]:
    """Infer FK values for a new record from tree context.

    :param table_name: Table being created.
    :param context_table: Currently selected table in the tree.
    :param context_id: Currently selected record ID.
    :returns: Dict of fk_column -> value to pre-populate.
    """
    if not context_table or not context_id:
        return {}

    result: dict[str, int] = {}
    for fk_col, ref_table in FK_DEFINITIONS.get(table_name, []):
        if ref_table == context_table:
            result[fk_col] = context_id
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_display_column(conn: sqlite3.Connection, table_name: str) -> str:
    """Determine the best column for display in a given table."""
    # Preference order: name, label, title, identifier, then fallback to id
    pragma = conn.execute(f"PRAGMA table_info({table_name})").fetchall()  # noqa: S608
    col_names = {p[1] for p in pragma}

    for candidate in ("name", "label", "title", "identifier", "description"):
        if candidate in col_names:
            return candidate
    return "id"


def _extract_check_values(
    conn: sqlite3.Connection, table_name: str, col_name: str
) -> list[str] | None:
    """Extract CHECK constraint enum values for a column.

    Parses the CREATE TABLE SQL to find CHECK constraints on the column.
    Returns None if no CHECK constraint exists.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    ).fetchone()
    if not row or not row[0]:
        return None

    sql = row[0]

    # Look for CHECK (col_name IN ('value1', 'value2', ...))
    import re
    pattern = rf"{re.escape(col_name)}\s+\w+.*?CHECK\s*\(\s*{re.escape(col_name)}\s+IN\s*\(([^)]+)\)"
    match = re.search(pattern, sql, re.IGNORECASE | re.DOTALL)
    if match:
        values_str = match.group(1)
        return [v.strip().strip("'\"") for v in values_str.split(",")]

    # Also look for standalone CHECK constraints
    pattern2 = rf"CHECK\s*\(\s*{re.escape(col_name)}\s+IN\s*\(([^)]+)\)"
    match2 = re.search(pattern2, sql, re.IGNORECASE | re.DOTALL)
    if match2:
        values_str = match2.group(1)
        return [v.strip().strip("'\"") for v in values_str.split(",")]

    return None
