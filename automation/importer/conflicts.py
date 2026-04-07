"""Conflict detection for the Import Processor.

Implements L2 PRD Section 11.5 — five conflict types:
1. Identifier uniqueness
2. Type mismatches
3. Referential integrity
4. Duplicate detection
5. Orphaned updates
"""

from __future__ import annotations

import sqlite3

from automation.importer.identifiers import check_uniqueness, validate_format
from automation.importer.proposed import Conflict, ProposedBatch, ProposedRecord

# Tables that have a foreign key we should check, mapped to the FK column
# and the target table.
FK_CHECKS: dict[str, list[tuple[str, str]]] = {
    "Field": [("entity_id", "Entity")],
    "FieldOption": [("field_id", "Field")],
    "Relationship": [
        ("entity_id", "Entity"),
        ("entity_foreign_id", "Entity"),
    ],
    "Process": [("domain_id", "Domain")],
    "ProcessStep": [
        ("process_id", "Process"),
        ("performer_persona_id", "Persona"),
    ],
    "Requirement": [("process_id", "Process")],
    "ProcessEntity": [
        ("process_id", "Process"),
        ("entity_id", "Entity"),
    ],
    "ProcessField": [
        ("process_id", "Process"),
        ("field_id", "Field"),
    ],
    "ProcessPersona": [
        ("process_id", "Process"),
        ("persona_id", "Persona"),
    ],
    "LayoutPanel": [("entity_id", "Entity")],
    "LayoutRow": [("panel_id", "LayoutPanel")],
    "LayoutTab": [("panel_id", "LayoutPanel")],
    "ListColumn": [
        ("entity_id", "Entity"),
        ("field_id", "Field"),
    ],
    "Decision": [
        ("domain_id", "Domain"),
        ("entity_id", "Entity"),
        ("process_id", "Process"),
    ],
    "OpenIssue": [
        ("domain_id", "Domain"),
        ("entity_id", "Entity"),
        ("process_id", "Process"),
    ],
    "BusinessObject": [
        ("resolved_to_entity_id", "Entity"),
        ("resolved_to_process_id", "Process"),
        ("resolved_to_persona_id", "Persona"),
    ],
    "Domain": [("parent_domain_id", "Domain")],
}


def detect_conflicts(
    conn: sqlite3.Connection,
    batch: ProposedBatch,
) -> ProposedBatch:
    """Run all conflict detection on a proposed batch.

    Attaches Conflict objects to each ProposedRecord.conflicts.
    Does not halt on conflicts — all are collected for review.

    :param conn: Open database connection.
    :param batch: The ProposedBatch to analyze.
    :returns: The same batch with conflicts populated.
    """
    for record in batch.records:
        # 1. Identifier uniqueness
        record.conflicts.extend(check_uniqueness(conn, record, batch))

        # 2. Format validation (warnings)
        record.conflicts.extend(validate_format(record))

        # 3. Type mismatches
        record.conflicts.extend(_check_type_mismatches(conn, record, batch))

        # 4. Referential integrity
        record.conflicts.extend(_check_referential_integrity(conn, record, batch))

        # 5. Duplicate detection
        record.conflicts.extend(_check_duplicates(conn, record))

        # 6. Orphaned updates
        record.conflicts.extend(_check_orphaned_updates(conn, record))

    return batch


def _check_type_mismatches(
    conn: sqlite3.Connection,
    record: ProposedRecord,
    batch: ProposedBatch,
) -> list[Conflict]:
    """Check for field type mismatches per Section 11.5.2."""
    conflicts: list[Conflict] = []

    if record.table_name != "Field":
        return conflicts

    proposed_type = record.values.get("field_type")
    if proposed_type is None:
        return conflicts

    if record.action == "update" and record.target_id is not None:
        # Updating an existing field — check if type is changing
        row = conn.execute(
            "SELECT field_type FROM Field WHERE id = ?", (record.target_id,)
        ).fetchone()
        if row and row[0] != proposed_type:
            conflicts.append(Conflict(
                severity="info",
                conflict_type="type_mismatch",
                message=(
                    f"Field type change from '{row[0]}' to '{proposed_type}'"
                ),
                field_name="field_type",
            ))

    elif record.action == "create":
        # New field — check if same name exists on same entity with different type
        entity_id = record.values.get("entity_id")
        field_name = record.values.get("name")
        if entity_id is not None and field_name is not None:
            row = conn.execute(
                "SELECT field_type FROM Field WHERE entity_id = ? AND name = ?",
                (entity_id, field_name),
            ).fetchone()
            if row and row[0] != proposed_type:
                conflicts.append(Conflict(
                    severity="error",
                    conflict_type="type_mismatch",
                    message=(
                        f"Field '{field_name}' already exists on entity {entity_id} "
                        f"with type '{row[0]}', proposed type is '{proposed_type}'"
                    ),
                    field_name="field_type",
                ))

    return conflicts


def _check_referential_integrity(
    conn: sqlite3.Connection,
    record: ProposedRecord,
    batch: ProposedBatch,
) -> list[Conflict]:
    """Check FK references exist in DB or in batch per Section 11.5.2."""
    conflicts: list[Conflict] = []

    fk_specs = FK_CHECKS.get(record.table_name, [])
    for fk_col, target_table in fk_specs:
        # Check if it's an intra-batch reference first
        if fk_col in record.intra_batch_refs:
            batch_ref = record.intra_batch_refs[fk_col]
            found = batch.find_by_batch_id(batch_ref)
            if found:
                conflicts.append(Conflict(
                    severity="info",
                    conflict_type="referential_integrity",
                    message=(
                        f"{fk_col} references intra-batch record "
                        f"at {found.source_payload_path}"
                    ),
                    field_name=fk_col,
                ))
            else:
                conflicts.append(Conflict(
                    severity="error",
                    conflict_type="referential_integrity",
                    message=(
                        f"{fk_col} references batch record '{batch_ref}' "
                        f"which was not found in this batch"
                    ),
                    field_name=fk_col,
                ))
            continue

        fk_value = record.values.get(fk_col)
        if fk_value is None:
            continue

        # Check if it exists in the database
        if isinstance(fk_value, int):
            row = conn.execute(
                f"SELECT id FROM {target_table} WHERE id = ?",
                (fk_value,),
            ).fetchone()
            if row is None:
                # Check if it's being created in this batch
                found_in_batch = False
                for other in batch.records:
                    if (other.table_name == target_table
                            and other.action == "create"
                            and other.batch_id):
                        # Can't match by id since it doesn't exist yet
                        pass
                if not found_in_batch:
                    conflicts.append(Conflict(
                        severity="error",
                        conflict_type="referential_integrity",
                        message=(
                            f"{fk_col} = {fk_value} does not exist in {target_table}"
                        ),
                        field_name=fk_col,
                    ))

    return conflicts


def _check_duplicates(
    conn: sqlite3.Connection,
    record: ProposedRecord,
) -> list[Conflict]:
    """Check for semantic duplicates per Section 11.5.2."""
    conflicts: list[Conflict] = []

    if record.action != "create":
        return conflicts

    name = record.values.get("name")
    if not name or not isinstance(name, str):
        return conflicts

    # Only check tables with name column
    tables_with_names = {
        "Domain", "Entity", "Persona", "Process", "BusinessObject",
    }
    if record.table_name not in tables_with_names:
        return conflicts

    # Find existing records with similar names
    rows = conn.execute(
        f"SELECT id, name FROM {record.table_name}"
    ).fetchall()

    for row_id, existing_name in rows:
        if _names_similar(name, existing_name):
            conflicts.append(Conflict(
                severity="warning",
                conflict_type="duplicate_detection",
                message=(
                    f"Proposed {record.table_name} '{name}' is similar to "
                    f"existing '{existing_name}' (id={row_id})"
                ),
                field_name="name",
            ))
            break  # One warning is sufficient

    return conflicts


def _names_similar(a: str, b: str) -> bool:
    """Check if two names are similar enough to flag as potential duplicates.

    Uses containment and case-insensitive comparison.
    """
    a_lower = a.lower().strip()
    b_lower = b.lower().strip()

    if a_lower == b_lower:
        return True

    # One contains the other
    if a_lower in b_lower or b_lower in a_lower:
        return True

    return False


def _check_orphaned_updates(
    conn: sqlite3.Connection,
    record: ProposedRecord,
) -> list[Conflict]:
    """Check that update targets still exist per Section 11.5.2."""
    conflicts: list[Conflict] = []

    if record.action != "update":
        return conflicts

    if record.target_id is None:
        return conflicts

    # Special case: Client table lives in master db, skip the check here
    if record.table_name == "Client":
        return conflicts

    row = conn.execute(
        f"SELECT id FROM {record.table_name} WHERE id = ?",
        (record.target_id,),
    ).fetchone()

    if row is None:
        conflicts.append(Conflict(
            severity="error",
            conflict_type="orphaned_update",
            message=(
                f"Update target {record.table_name} id={record.target_id} "
                f"no longer exists"
            ),
        ))

    return conflicts
