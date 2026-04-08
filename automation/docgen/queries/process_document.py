"""Data query for Process Document generation.

Implements L2 PRD Section 13.3.5 — queries Process, ProcessPersona,
ProcessStep, Requirement, ProcessEntity, ProcessField, Decision, and
OpenIssue tables.
"""

from __future__ import annotations

import sqlite3


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for a Process Document.

    :param conn: Client database connection.
    :param work_item_id: The process_definition WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Process Document template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "process": None,
        "domain": None,
        "personas": [],
        "steps": [],
        "requirements": [],
        "data_reference": [],
        "decisions": [],
        "open_issues": [],
    }

    if master_conn:
        row = master_conn.execute(
            "SELECT name, code FROM Client ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]

    # Get process_id from work item
    wi = conn.execute(
        "SELECT process_id FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if not wi or not wi[0]:
        return data
    process_id = wi[0]

    # Process record
    row = conn.execute(
        "SELECT id, name, code, description, triggers, completion_criteria, "
        "domain_id, sort_order "
        "FROM Process WHERE id = ?",
        (process_id,),
    ).fetchone()
    if not row:
        return data

    data["process"] = {
        "id": row[0], "name": row[1], "code": row[2], "description": row[3],
        "triggers": row[4], "completion_criteria": row[5],
        "domain_id": row[6], "sort_order": row[7],
    }

    # Domain for this process
    domain_row = conn.execute(
        "SELECT id, name, code FROM Domain WHERE id = ?", (row[6],)
    ).fetchone()
    if domain_row:
        data["domain"] = {
            "id": domain_row[0], "name": domain_row[1], "code": domain_row[2],
        }

    # Personas with roles
    persona_rows = conn.execute(
        "SELECT per.id, per.name, per.code, per.description, pp.role "
        "FROM ProcessPersona pp "
        "JOIN Persona per ON pp.persona_id = per.id "
        "WHERE pp.process_id = ? ORDER BY per.code",
        (process_id,),
    ).fetchall()
    data["personas"] = [
        {"id": r[0], "name": r[1], "code": r[2], "description": r[3], "role": r[4]}
        for r in persona_rows
    ]

    # Workflow steps
    steps = conn.execute(
        "SELECT ps.id, ps.name, ps.description, ps.step_type, "
        "ps.sort_order, per.name AS performer_name, per.code AS performer_code "
        "FROM ProcessStep ps "
        "LEFT JOIN Persona per ON ps.performer_persona_id = per.id "
        "WHERE ps.process_id = ? ORDER BY ps.sort_order",
        (process_id,),
    ).fetchall()
    data["steps"] = [
        {
            "id": r[0], "name": r[1], "description": r[2],
            "step_type": r[3], "sort_order": r[4],
            "performer_name": r[5], "performer_code": r[6],
        }
        for r in steps
    ]

    # Requirements
    reqs = conn.execute(
        "SELECT identifier, description, priority, status "
        "FROM Requirement WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["requirements"] = [
        {"identifier": r[0], "description": r[1], "priority": r[2], "status": r[3]}
        for r in reqs
    ]

    # Data references grouped by entity
    entity_rows = conn.execute(
        "SELECT DISTINCT e.id, e.name, e.code "
        "FROM ProcessEntity pe "
        "JOIN Entity e ON pe.entity_id = e.id "
        "WHERE pe.process_id = ? ORDER BY e.name",
        (process_id,),
    ).fetchall()

    for er in entity_rows:
        entity_id = er[0]
        field_rows = conn.execute(
            "SELECT f.name, f.label, f.field_type, pf.usage, pf.description "
            "FROM ProcessField pf "
            "JOIN Field f ON pf.field_id = f.id "
            "WHERE pf.process_id = ? AND f.entity_id = ? "
            "ORDER BY f.name",
            (process_id, entity_id),
        ).fetchall()

        data["data_reference"].append({
            "entity_name": er[1], "entity_code": er[2],
            "fields": [
                {"name": fr[0], "label": fr[1], "field_type": fr[2],
                 "usage": fr[3], "description": fr[4]}
                for fr in field_rows
            ],
        })

    # Decisions
    decisions = conn.execute(
        "SELECT identifier, title, description, status "
        "FROM Decision WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "status": r[3]}
        for r in decisions
    ]

    # Open issues
    issues = conn.execute(
        "SELECT identifier, title, description, status, priority "
        "FROM OpenIssue WHERE process_id = ? ORDER BY identifier",
        (process_id,),
    ).fetchall()
    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2],
         "status": r[3], "priority": r[4]}
        for r in issues
    ]

    return data
