"""Data query for CRM Evaluation Report generation.

Implements L2 PRD Section 13.3.8 — queries Client, Decision, OpenIssue,
Requirement, Entity, Field, and Relationship tables.

This is the only document type permitted to include product names.
"""

from __future__ import annotations

import sqlite3

from automation.docgen.queries import get_client_row


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for a CRM Evaluation Report.

    :param conn: Client database connection.
    :param work_item_id: The crm_selection WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the CRM Evaluation Report template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "crm_platform": None,
        "decisions": [],
        "open_issues": [],
        "requirements_summary": {
            "total": 0, "must": 0, "should": 0, "may": 0,
        },
        "scale_summary": {
            "entity_count": 0, "field_count": 0, "relationship_count": 0,
        },
    }

    if master_conn:
        row = get_client_row(master_conn, conn, columns="name, code, crm_platform")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]
            data["crm_platform"] = row[2]

    # Platform evaluation decisions (unscoped or CRM-related)
    decisions = conn.execute(
        "SELECT identifier, title, description, status "
        "FROM Decision ORDER BY identifier"
    ).fetchall()
    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "status": r[3]}
        for r in decisions
    ]

    # Open issues
    issues = conn.execute(
        "SELECT identifier, title, description, status, priority "
        "FROM OpenIssue ORDER BY identifier"
    ).fetchall()
    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2],
         "status": r[3], "priority": r[4]}
        for r in issues
    ]

    # Requirements coverage assessment
    req_rows = conn.execute(
        "SELECT priority, COUNT(*) FROM Requirement GROUP BY priority"
    ).fetchall()
    total = 0
    for priority, count in req_rows:
        total += count
        if priority in ("must", "should", "may"):
            data["requirements_summary"][priority] = count
    data["requirements_summary"]["total"] = total

    # Scale summary
    data["scale_summary"]["entity_count"] = conn.execute(
        "SELECT COUNT(*) FROM Entity"
    ).fetchone()[0]
    data["scale_summary"]["field_count"] = conn.execute(
        "SELECT COUNT(*) FROM Field"
    ).fetchone()[0]
    data["scale_summary"]["relationship_count"] = conn.execute(
        "SELECT COUNT(*) FROM Relationship"
    ).fetchone()[0]

    return data
