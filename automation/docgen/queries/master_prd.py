"""Data query for Master PRD generation.

Implements L2 PRD Section 13.3.1 — queries Client, Persona, Domain, and
Process tables to assemble the Master PRD data dictionary.
"""

from __future__ import annotations

import sqlite3


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for a Master PRD.

    :param conn: Client database connection.
    :param work_item_id: The master_prd WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Master PRD template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "organization_overview": None,
        "personas": [],
        "domains": [],
        "services": [],
    }

    # Client info from master database
    if master_conn:
        row = master_conn.execute(
            "SELECT name, code, organization_overview FROM Client ORDER BY id LIMIT 1"
        ).fetchone()
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]
            data["organization_overview"] = row[2]

    # Personas sorted by code
    personas = conn.execute(
        "SELECT id, name, code, description FROM Persona ORDER BY code"
    ).fetchall()
    data["personas"] = [
        {"id": r[0], "name": r[1], "code": r[2], "description": r[3]}
        for r in personas
    ]

    # Domains with hierarchy, split into domains vs services
    all_domains = conn.execute(
        "SELECT id, name, code, description, sort_order, parent_domain_id, is_service "
        "FROM Domain ORDER BY sort_order, name"
    ).fetchall()

    domain_map: dict[int, dict] = {}
    for r in all_domains:
        d = {
            "id": r[0], "name": r[1], "code": r[2], "description": r[3],
            "sort_order": r[4], "parent_domain_id": r[5], "is_service": r[6],
            "sub_domains": [], "processes": [],
        }
        domain_map[r[0]] = d

    # Processes grouped by domain, sorted by sort_order
    processes = conn.execute(
        "SELECT id, domain_id, name, code, description, sort_order "
        "FROM Process ORDER BY sort_order"
    ).fetchall()
    for r in processes:
        proc = {
            "id": r[0], "name": r[2], "code": r[3],
            "description": r[4], "sort_order": r[5],
        }
        if r[1] in domain_map:
            domain_map[r[1]]["processes"].append(proc)

    # Build hierarchy: nest sub-domains under parents
    for d in domain_map.values():
        pid = d["parent_domain_id"]
        if pid and pid in domain_map:
            domain_map[pid]["sub_domains"].append(d)

    # Split into domains (non-service) and services
    for d in domain_map.values():
        if d["parent_domain_id"] is not None:
            continue  # Skip sub-domains (already nested)
        if d["is_service"]:
            data["services"].append(d)
        else:
            data["domains"].append(d)

    return data
