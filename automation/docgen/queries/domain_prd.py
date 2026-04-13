"""Data query for Domain PRD generation.

Implements L2 PRD Section 13.3.6 — queries Domain, Process (with full
ProcessStep, Requirement, cross-reference data), Persona, Entity, Field,
Decision, and OpenIssue tables.

Decisions and OpenIssues are included where domain_id matches OR where
process_id matches any process in the domain.
"""

from __future__ import annotations

import sqlite3

from automation.docgen.queries import get_client_row


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for a Domain PRD.

    :param conn: Client database connection.
    :param work_item_id: The domain_reconciliation WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Domain PRD template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "domain": None,
        "reconciliation_text": None,
        "processes": [],
        "personas": [],
        "data_reference": [],
        "decisions": [],
        "open_issues": [],
    }

    if master_conn:
        row = get_client_row(master_conn, conn, columns="name, code")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]

    # Get domain_id from work item
    wi = conn.execute(
        "SELECT domain_id FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if not wi or not wi[0]:
        return data
    domain_id = wi[0]

    # Domain record
    row = conn.execute(
        "SELECT id, name, code, description, domain_reconciliation_text "
        "FROM Domain WHERE id = ?",
        (domain_id,),
    ).fetchone()
    if not row:
        return data

    data["domain"] = {
        "id": row[0], "name": row[1], "code": row[2], "description": row[3],
    }
    data["reconciliation_text"] = row[4]

    # All processes in this domain with full detail
    processes = conn.execute(
        "SELECT id, name, code, description, triggers, completion_criteria, sort_order "
        "FROM Process WHERE domain_id = ? ORDER BY sort_order",
        (domain_id,),
    ).fetchall()

    process_ids: list[int] = []
    for p in processes:
        pid = p[0]
        process_ids.append(pid)

        # Steps for this process
        steps = conn.execute(
            "SELECT ps.name, ps.description, ps.step_type, ps.sort_order, "
            "per.name AS performer_name "
            "FROM ProcessStep ps "
            "LEFT JOIN Persona per ON ps.performer_persona_id = per.id "
            "WHERE ps.process_id = ? ORDER BY ps.sort_order",
            (pid,),
        ).fetchall()

        # Requirements for this process
        reqs = conn.execute(
            "SELECT identifier, description, priority, status "
            "FROM Requirement WHERE process_id = ? ORDER BY identifier",
            (pid,),
        ).fetchall()

        data["processes"].append({
            "id": pid, "name": p[1], "code": p[2], "description": p[3],
            "triggers": p[4], "completion_criteria": p[5], "sort_order": p[6],
            "steps": [
                {"name": s[0], "description": s[1], "step_type": s[2],
                 "sort_order": s[3], "performer_name": s[4]}
                for s in steps
            ],
            "requirements": [
                {"identifier": r[0], "description": r[1],
                 "priority": r[2], "status": r[3]}
                for r in reqs
            ],
        })

    # Consolidated personas across all domain processes
    if process_ids:
        ph = ",".join("?" * len(process_ids))
        persona_rows = conn.execute(
            f"SELECT DISTINCT per.id, per.name, per.code, per.description, "  # noqa: S608
            f"pp.role, p.name AS process_name "
            f"FROM ProcessPersona pp "
            f"JOIN Persona per ON pp.persona_id = per.id "
            f"JOIN Process p ON pp.process_id = p.id "
            f"WHERE pp.process_id IN ({ph}) "
            f"ORDER BY per.code",
            process_ids,
        ).fetchall()

        persona_map: dict[int, dict] = {}
        for r in persona_rows:
            pid = r[0]
            if pid not in persona_map:
                persona_map[pid] = {
                    "id": r[0], "name": r[1], "code": r[2],
                    "description": r[3], "roles": [],
                }
            persona_map[pid]["roles"].append({
                "role": r[4], "process_name": r[5],
            })
        data["personas"] = list(persona_map.values())

        # Consolidated data reference with deduplicated fields
        entity_rows = conn.execute(
            f"SELECT DISTINCT e.id, e.name, e.code "  # noqa: S608
            f"FROM ProcessEntity pe "
            f"JOIN Entity e ON pe.entity_id = e.id "
            f"WHERE pe.process_id IN ({ph}) "
            f"ORDER BY e.name",
            process_ids,
        ).fetchall()

        for er in entity_rows:
            field_rows = conn.execute(
                f"SELECT DISTINCT f.name, f.label, f.field_type, pf.usage "  # noqa: S608
                f"FROM ProcessField pf "
                f"JOIN Field f ON pf.field_id = f.id "
                f"WHERE pf.process_id IN ({ph}) AND f.entity_id = ? "
                f"ORDER BY f.name",
                [*process_ids, er[0]],
            ).fetchall()

            data["data_reference"].append({
                "entity_name": er[1], "entity_code": er[2],
                "fields": [
                    {"name": r[0], "label": r[1], "field_type": r[2], "usage": r[3]}
                    for r in field_rows
                ],
            })

    # Decisions where domain_id matches OR process_id is in domain processes
    if process_ids:
        ph = ",".join("?" * len(process_ids))
        decisions = conn.execute(
            f"SELECT identifier, title, description, status "  # noqa: S608
            f"FROM Decision "
            f"WHERE domain_id = ? OR process_id IN ({ph}) "
            f"ORDER BY identifier",
            [domain_id, *process_ids],
        ).fetchall()
    else:
        decisions = conn.execute(
            "SELECT identifier, title, description, status "
            "FROM Decision WHERE domain_id = ? ORDER BY identifier",
            (domain_id,),
        ).fetchall()

    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "status": r[3]}
        for r in decisions
    ]

    # Open issues where domain_id matches OR process_id is in domain processes
    if process_ids:
        ph = ",".join("?" * len(process_ids))
        issues = conn.execute(
            f"SELECT identifier, title, description, status, priority "  # noqa: S608
            f"FROM OpenIssue "
            f"WHERE domain_id = ? OR process_id IN ({ph}) "
            f"ORDER BY identifier",
            [domain_id, *process_ids],
        ).fetchall()
    else:
        issues = conn.execute(
            "SELECT identifier, title, description, status, priority "
            "FROM OpenIssue WHERE domain_id = ? ORDER BY identifier",
            (domain_id,),
        ).fetchall()

    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2],
         "status": r[3], "priority": r[4]}
        for r in issues
    ]

    return data
