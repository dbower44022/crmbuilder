"""Data query for Entity Inventory generation.

Implements L2 PRD Section 13.3.2 — queries Entity, BusinessObject,
ProcessEntity, and Domain tables.
"""

from __future__ import annotations

import sqlite3

from automation.docgen.queries import get_client_row


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for an Entity Inventory.

    :param conn: Client database connection.
    :param work_item_id: The business_object_discovery WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Entity Inventory template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "entities": [],
        "business_objects": [],
    }

    if master_conn:
        row = get_client_row(master_conn, conn, columns="name, code")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]

    # Entities grouped by native/custom, sorted by name
    entities = conn.execute(
        "SELECT e.id, e.name, e.code, e.entity_type, e.is_native, "
        "e.singular_label, e.plural_label, e.description, "
        "e.primary_domain_id, d.name AS domain_name "
        "FROM Entity e "
        "LEFT JOIN Domain d ON e.primary_domain_id = d.id "
        "ORDER BY e.is_native DESC, e.name"
    ).fetchall()

    for r in entities:
        entity_id = r[0]
        # Get processes that reference this entity
        proc_refs = conn.execute(
            "SELECT DISTINCT p.name, p.code FROM ProcessEntity pe "
            "JOIN Process p ON pe.process_id = p.id "
            "WHERE pe.entity_id = ? ORDER BY p.code",
            (entity_id,),
        ).fetchall()

        data["entities"].append({
            "id": entity_id,
            "name": r[1],
            "code": r[2],
            "entity_type": r[3],
            "is_native": bool(r[4]),
            "singular_label": r[5],
            "plural_label": r[6],
            "description": r[7],
            "primary_domain": r[9],
            "process_references": [
                {"name": p[0], "code": p[1]} for p in proc_refs
            ],
        })

    # Business objects with resolution links
    bos = conn.execute(
        "SELECT bo.id, bo.name, bo.description, bo.status, bo.resolution, "
        "bo.resolution_detail, "
        "e.name AS entity_name, p.name AS process_name, per.name AS persona_name "
        "FROM BusinessObject bo "
        "LEFT JOIN Entity e ON bo.resolved_to_entity_id = e.id "
        "LEFT JOIN Process p ON bo.resolved_to_process_id = p.id "
        "LEFT JOIN Persona per ON bo.resolved_to_persona_id = per.id "
        "ORDER BY bo.name"
    ).fetchall()

    data["business_objects"] = [
        {
            "id": r[0], "name": r[1], "description": r[2],
            "status": r[3], "resolution": r[4],
            "resolution_detail": r[5],
            "resolved_entity": r[6],
            "resolved_process": r[7],
            "resolved_persona": r[8],
        }
        for r in bos
    ]

    return data
