"""Data query for Master PRD generation.

Implements L2 PRD Section 13.3.1 — queries Client, Persona, Domain, and
Process tables to assemble the Master PRD data dictionary.  Supplements
database rows with rich fields (responsibilities, business_value,
key_capabilities, system_scope, etc.) from the AISession structured_output
JSON when available.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime

from automation.docgen.queries import get_client_row

logger = logging.getLogger(__name__)


def _extract_client_name_from_session(
    conn: sqlite3.Connection, work_item_id: int,
) -> str | None:
    """Extract the client name from the AISession generated prompt.

    The prompt header contains a line like: ``**Client:** ABC Optical (ABCO)``

    :param conn: Client database connection.
    :param work_item_id: Work item ID.
    :returns: Client name, or None.
    """
    row = conn.execute(
        "SELECT generated_prompt FROM AISession "
        "WHERE work_item_id = ? ORDER BY completed_at DESC LIMIT 1",
        (work_item_id,),
    ).fetchone()
    if not row or not row[0]:
        return None
    match = re.search(r"\*\*Client:\*\*\s*(.+?)(?:\s*\([A-Z0-9]+\))?\s*$", row[0], re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _load_structured_payload(
    conn: sqlite3.Connection,
    work_item_id: int,
) -> dict | None:
    """Load the structured_output payload from the most recent imported AISession.

    :param conn: Client database connection.
    :param work_item_id: The master_prd WorkItem.id.
    :returns: The payload dict, or None if unavailable.
    """
    row = conn.execute(
        "SELECT structured_output FROM AISession "
        "WHERE work_item_id = ? AND import_status = 'imported' "
        "ORDER BY completed_at DESC LIMIT 1",
        (work_item_id,),
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        envelope = json.loads(row[0])
        return envelope.get("payload")
    except (json.JSONDecodeError, AttributeError):
        return None


def _enrich_personas(
    personas: list[dict],
    payload: dict | None,
) -> list[dict]:
    """Merge rich persona fields from the structured payload.

    Adds responsibilities, crm_capabilities, and primary_domains when
    available in the payload but absent from the database row.
    """
    if not payload:
        return personas

    payload_by_code: dict[str, dict] = {}
    for p in payload.get("personas", []):
        code = p.get("identifier", p.get("code", ""))
        if code:
            payload_by_code[code] = p

    for persona in personas:
        extra = payload_by_code.get(persona["code"], {})
        persona.setdefault("responsibilities", extra.get("responsibilities", []))
        persona.setdefault("crm_capabilities", extra.get("crm_capabilities", []))
        persona.setdefault("primary_domains", extra.get("primary_domains", []))

    return personas


def _enrich_processes(
    domain_map: dict[int, dict],
    payload: dict | None,
) -> None:
    """Merge rich process fields from the structured payload.

    Adds business_value and key_capabilities when available.
    """
    if not payload:
        return

    payload_by_code: dict[str, dict] = {}
    for p in payload.get("processes", []):
        code = p.get("code", "")
        if code:
            payload_by_code[code] = p

    for domain in domain_map.values():
        for proc in domain.get("processes", []):
            extra = payload_by_code.get(proc["code"], {})
            proc.setdefault("business_value", extra.get("business_value", ""))
            proc.setdefault("key_capabilities", extra.get("key_capabilities", []))


def _build_cross_domain_services(
    domain_map: dict[int, dict],
    payload: dict | None,
) -> list[dict]:
    """Build cross-domain service dicts enriched with payload data.

    Database Domain rows with is_service=True provide the base; the
    payload's cross_domain_services list adds capabilities,
    consuming_domains, and owned_entities.
    """
    payload_svcs: dict[str, dict] = {}
    if payload:
        for svc in payload.get("cross_domain_services", []):
            name = svc.get("name", "")
            if name:
                payload_svcs[name] = svc

    services: list[dict] = []
    for d in domain_map.values():
        if not d.get("is_service"):
            continue
        if d.get("parent_domain_id") is not None:
            continue
        extra = payload_svcs.get(d["name"], {})
        services.append({
            "id": d["id"],
            "name": d["name"],
            "code": d["code"],
            "description": d.get("description", ""),
            "capabilities": extra.get("capabilities", []),
            "consuming_domains": extra.get("consuming_domains", []),
            "owned_entities": extra.get("owned_entities", []),
        })
    return services


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
        "system_scope": {},
        "last_updated": None,
    }

    # Load supplementary data from structured output
    payload = _load_structured_payload(conn, work_item_id)

    # Client info from master database.
    if master_conn:
        row = get_client_row(master_conn, conn,
                             columns="name, code, organization_overview")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]
            data["organization_overview"] = row[2]

    # Fall back to structured payload for organization overview and client name
    if not data["organization_overview"] and payload:
        data["organization_overview"] = payload.get("organization_overview")
    if not data["client_name"]:
        data["client_name"] = _extract_client_name_from_session(conn, work_item_id)
    if not data["client_short_name"]:
        from automation.docgen.queries import _detect_client_code
        data["client_short_name"] = _detect_client_code(conn) or ""

    # Last-updated timestamp from most recent AISession
    ts_row = conn.execute(
        "SELECT completed_at FROM AISession "
        "WHERE work_item_id = ? AND import_status = 'imported' "
        "ORDER BY completed_at DESC LIMIT 1",
        (work_item_id,),
    ).fetchone()
    if ts_row and ts_row[0]:
        try:
            dt = datetime.fromisoformat(ts_row[0])
            data["last_updated"] = dt.strftime("%m-%d-%y %H:%M")
        except (ValueError, TypeError):
            data["last_updated"] = ts_row[0]

    # Personas sorted by code
    personas = conn.execute(
        "SELECT id, name, code, description FROM Persona ORDER BY code"
    ).fetchall()
    data["personas"] = [
        {"id": r[0], "name": r[1], "code": r[2], "description": r[3]}
        for r in personas
    ]
    data["personas"] = _enrich_personas(data["personas"], payload)

    # Domains with hierarchy, split into domains vs services
    all_domains = conn.execute(
        "SELECT id, name, code, identifier, description, sort_order, "
        "parent_domain_id, is_service "
        "FROM Domain ORDER BY sort_order, name"
    ).fetchall()

    domain_map: dict[int, dict] = {}
    for r in all_domains:
        d = {
            "id": r[0], "name": r[1], "code": r[2], "identifier": r[3],
            "description": r[4], "sort_order": r[5],
            "parent_domain_id": r[6], "is_service": r[7],
            "sub_domains": [], "processes": [],
        }
        domain_map[r[0]] = d

    # Processes grouped by domain, sorted by sort_order
    processes = conn.execute(
        "SELECT id, domain_id, name, code, description, sort_order, tier "
        "FROM Process ORDER BY sort_order"
    ).fetchall()
    for r in processes:
        proc = {
            "id": r[0], "name": r[2], "code": r[3],
            "description": r[4], "sort_order": r[5], "tier": r[6],
        }
        if r[1] in domain_map:
            domain_map[r[1]]["processes"].append(proc)

    # Enrich processes with business_value and key_capabilities
    _enrich_processes(domain_map, payload)

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
            continue  # Handled separately
        data["domains"].append(d)

    # Build enriched service list
    data["services"] = _build_cross_domain_services(domain_map, payload)

    # System scope from structured payload
    if payload:
        data["system_scope"] = payload.get("system_scope", {})

    # Decisions
    decisions = conn.execute(
        "SELECT identifier, title, description FROM Decision ORDER BY identifier"
    ).fetchall()
    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2]}
        for r in decisions
    ]

    # Open issues
    open_issues = conn.execute(
        "SELECT identifier, title, description, priority "
        "FROM OpenIssue WHERE status = 'open' ORDER BY identifier"
    ).fetchall()
    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "priority": r[3]}
        for r in open_issues
    ]

    return data
