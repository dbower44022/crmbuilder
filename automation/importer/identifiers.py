"""Identifier validation for the Import Processor.

Implements L2 PRD Section 11.12:
- 11.12.1 Preservation: AI-assigned identifiers used as-is
- 11.12.2 Uniqueness validation: per-table scoped checks
- 11.12.3 Format validation: pattern checks (warnings, not errors)
- 11.12.4 Sequential gaps: not enforced
"""

from __future__ import annotations

import re
import sqlite3

from automation.importer.proposed import Conflict, ProposedBatch, ProposedRecord

# Format patterns per Section 11.12.3
# Domain codes: uppercase alphabetic, 2-4 chars
DOMAIN_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}$")

# Entity codes: uppercase alphabetic
ENTITY_CODE_PATTERN = re.compile(r"^[A-Z]+$")

# Persona codes: uppercase alphabetic
PERSONA_CODE_PATTERN = re.compile(r"^[A-Z]+$")

# Process codes: domain_code-UPPERCASE_NAME
PROCESS_CODE_PATTERN = re.compile(r"^[A-Z]{2,4}-[A-Z][A-Z_]*$")

# Requirement identifiers: PROCESS_CODE-REQ-NNN
REQUIREMENT_ID_PATTERN = re.compile(r"^[A-Z]{2,4}-[A-Z][A-Z_]*-REQ-\d+$")

# Decision identifiers: SCOPE_CODE-DEC-NNN
DECISION_ID_PATTERN = re.compile(r"^[A-Z][\w]*-DEC-\d+$")

# Open issue identifiers: SCOPE_CODE-ISS-NNN (or OI-NNN)
OPEN_ISSUE_ID_PATTERN = re.compile(r"^[A-Z][\w]*-(?:ISS|OI)-\d+$")

# Table → column name for the unique identifier
TABLE_ID_COLUMNS: dict[str, str] = {
    "Domain": "code",
    "Entity": "code",
    "Persona": "code",
    "Process": "code",
    "Requirement": "identifier",
    "Decision": "identifier",
    "OpenIssue": "identifier",
}

# Table → format pattern
TABLE_FORMAT_PATTERNS: dict[str, re.Pattern] = {
    "Domain": DOMAIN_CODE_PATTERN,
    "Entity": ENTITY_CODE_PATTERN,
    "Persona": PERSONA_CODE_PATTERN,
    "Process": PROCESS_CODE_PATTERN,
    "Requirement": REQUIREMENT_ID_PATTERN,
    "Decision": DECISION_ID_PATTERN,
    "OpenIssue": OPEN_ISSUE_ID_PATTERN,
}


def validate_format(record: ProposedRecord) -> list[Conflict]:
    """Validate identifier format for a proposed record.

    Format violations are warnings per the L2 PRD.

    :param record: A ProposedRecord with values containing the identifier.
    :returns: List of format-related Conflict objects (warnings).
    """
    conflicts: list[Conflict] = []
    table = record.table_name
    id_col = TABLE_ID_COLUMNS.get(table)
    if id_col is None:
        return conflicts

    value = record.values.get(id_col)
    if value is None:
        return conflicts

    pattern = TABLE_FORMAT_PATTERNS.get(table)
    if pattern and not pattern.match(str(value)):
        conflicts.append(Conflict(
            severity="warning",
            conflict_type="format_violation",
            message=(
                f"{table}.{id_col} '{value}' does not match expected format "
                f"(pattern: {pattern.pattern})"
            ),
            field_name=id_col,
        ))

    return conflicts


def validate_process_code_prefix(
    record: ProposedRecord,
    domain_code: str | None,
) -> list[Conflict]:
    """Validate that a Process code's prefix matches its parent Domain code.

    Per Finding 5 from v1.6 in the L2 PRD, the Master PRD mapper checks
    that each process code starts with the domain code.

    :param record: A ProposedRecord for the Process table.
    :param domain_code: The code of the parent Domain.
    :returns: List of Conflict objects (warnings).
    """
    conflicts: list[Conflict] = []
    if record.table_name != "Process":
        return conflicts
    if domain_code is None:
        return conflicts

    code = record.values.get("code")
    if code is None:
        return conflicts

    if not str(code).startswith(domain_code + "-"):
        conflicts.append(Conflict(
            severity="warning",
            conflict_type="format_violation",
            message=(
                f"Process code '{code}' does not start with domain code "
                f"'{domain_code}-'"
            ),
            field_name="code",
        ))

    return conflicts


def check_uniqueness(
    conn: sqlite3.Connection,
    record: ProposedRecord,
    batch: ProposedBatch,
) -> list[Conflict]:
    """Check identifier uniqueness against database and batch.

    Per Section 11.12.2: per-table uniqueness, scoped correctly.
    For updates, excludes the record being updated.

    :param conn: Open database connection.
    :param record: The ProposedRecord to check.
    :param batch: The full batch (for intra-batch checks).
    :returns: List of Conflict objects (errors for duplicates).
    """
    conflicts: list[Conflict] = []
    table = record.table_name
    id_col = TABLE_ID_COLUMNS.get(table)
    if id_col is None:
        return conflicts

    value = record.values.get(id_col)
    if value is None:
        return conflicts

    # Check against existing database records
    if record.action == "update":
        # Exclude the record being updated
        row = conn.execute(
            f"SELECT id FROM {table} WHERE {id_col} = ? AND id != ?",
            (value, record.target_id),
        ).fetchone()
    else:
        row = conn.execute(
            f"SELECT id FROM {table} WHERE {id_col} = ?",
            (value,),
        ).fetchone()

    if row is not None:
        conflicts.append(Conflict(
            severity="error",
            conflict_type="identifier_uniqueness",
            message=(
                f"Duplicate {id_col} '{value}' in {table}: "
                f"already exists (record id={row[0]})"
            ),
            field_name=id_col,
        ))

    # Check against other records in the same batch
    for other in batch.records:
        if other is record:
            continue
        if other.table_name != table:
            continue
        other_val = other.values.get(id_col)
        if other_val is not None and other_val == value:
            # For updates, don't flag if both are updating the same record
            if (record.action == "update" and other.action == "update"
                    and record.target_id == other.target_id):
                continue
            conflicts.append(Conflict(
                severity="error",
                conflict_type="identifier_uniqueness",
                message=(
                    f"Duplicate {id_col} '{value}' in {table}: "
                    f"also proposed at {other.source_payload_path}"
                ),
                field_name=id_col,
            ))
            break  # One conflict is enough

    return conflicts
