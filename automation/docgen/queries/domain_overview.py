"""Data query for Domain Overview generation.

Implements L2 PRD Section 13.3.4 — queries Domain, Process, ProcessPersona,
ProcessEntity, ProcessField, Entity, and Field tables.
"""

from __future__ import annotations

import sqlite3


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for a Domain Overview.

    :param conn: Client database connection.
    :param work_item_id: The domain_overview WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Domain Overview template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "domain": None,
        "parent_domain": None,
        "domain_overview_text": None,
        "processes": [],
        "personas": [],
        "data_reference": [],
    }

    if master_conn:
        row = master_conn.execute(
            "SELECT name, code FROM Client ORDER BY id LIMIT 1"
        ).fetchone()
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
        "SELECT id, name, code, description, domain_overview_text, parent_domain_id "
        "FROM Domain WHERE id = ?",
        (domain_id,),
    ).fetchone()
    if not row:
        return data

    data["domain"] = {
        "id": row[0], "name": row[1], "code": row[2], "description": row[3],
    }
    data["domain_overview_text"] = row[4]

    if row[5]:
        parent = conn.execute(
            "SELECT name, code FROM Domain WHERE id = ?", (row[5],)
        ).fetchone()
        if parent:
            data["parent_domain"] = {"name": parent[0], "code": parent[1]}

    # Processes in this domain
    processes = conn.execute(
        "SELECT id, name, code, description, triggers, completion_criteria, sort_order "
        "FROM Process WHERE domain_id = ? ORDER BY sort_order",
        (domain_id,),
    ).fetchall()
    data["processes"] = [
        {
            "id": r[0], "name": r[1], "code": r[2], "description": r[3],
            "triggers": r[4], "completion_criteria": r[5], "sort_order": r[6],
        }
        for r in processes
    ]

    # Personas with domain-specific roles
    process_ids = [p["id"] for p in data["processes"]]
    if process_ids:
        ph = ",".join("?" * len(process_ids))
        persona_rows = conn.execute(
            f"SELECT DISTINCT per.id, per.name, per.code, per.description, "  # noqa: S608
            f"pp.role, p.name AS process_name "
            f"FROM ProcessPersona pp "
            f"JOIN Persona per ON pp.persona_id = per.id "
            f"JOIN Process p ON pp.process_id = p.id "
            f"WHERE pp.process_id IN ({ph}) "
            f"ORDER BY per.code, p.name",
            process_ids,
        ).fetchall()

        # Group by persona
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

        # Data reference: entities and fields used by domain processes
        entity_rows = conn.execute(
            f"SELECT DISTINCT e.id, e.name, e.code, pe.role "  # noqa: S608
            f"FROM ProcessEntity pe "
            f"JOIN Entity e ON pe.entity_id = e.id "
            f"WHERE pe.process_id IN ({ph}) "
            f"ORDER BY e.name",
            process_ids,
        ).fetchall()

        entity_map: dict[int, dict] = {}
        for r in entity_rows:
            eid = r[0]
            if eid not in entity_map:
                entity_map[eid] = {
                    "id": eid, "name": r[1], "code": r[2],
                    "roles": [], "fields": [],
                }
            entity_map[eid]["roles"].append(r[3])

        # Fields per entity used by domain processes
        field_rows = conn.execute(
            f"SELECT DISTINCT f.id, f.name, f.label, f.field_type, "  # noqa: S608
            f"f.entity_id, pf.usage "
            f"FROM ProcessField pf "
            f"JOIN Field f ON pf.field_id = f.id "
            f"WHERE pf.process_id IN ({ph}) "
            f"ORDER BY f.entity_id, f.name",
            process_ids,
        ).fetchall()

        for r in field_rows:
            eid = r[4]
            if eid in entity_map:
                entity_map[eid]["fields"].append({
                    "id": r[0], "name": r[1], "label": r[2],
                    "field_type": r[3], "usage": r[5],
                })

        data["data_reference"] = list(entity_map.values())

    return data
