"""Mapper for master_prd payloads.

Target tables: Client (update), Domain (create), Persona (create), Process (create).
Per L2 PRD Section 11.3.1.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.mappers.base import map_decisions, map_open_issues
from automation.importer.proposed import ProposedBatch, ProposedRecord


def map_payload(
    conn: sqlite3.Connection,
    work_item: dict,
    payload: dict,
    session_type: str,
    ai_session_id: int,
    master_conn: sqlite3.Connection | None = None,
    envelope: dict | None = None,
) -> ProposedBatch:
    """Map a master_prd payload to proposed records."""
    records: list[ProposedRecord] = []

    # Organization overview -> Client update (master db)
    overview = payload.get("organization_overview")
    if overview and master_conn is not None:
        client_row = master_conn.execute(
            "SELECT id FROM Client LIMIT 1"
        ).fetchone()
        if client_row:
            records.append(ProposedRecord(
                table_name="Client",
                action="update",
                target_id=client_row[0],
                values={"organization_overview": overview},
                source_payload_path="payload.organization_overview",
            ))

    # Personas
    for i, p in enumerate(payload.get("personas", [])):
        code = p.get("identifier", p.get("code", ""))
        values: dict[str, Any] = {
            "name": p.get("name", ""),
            "code": code,
            "description": p.get("description"),
            "created_by_session_id": ai_session_id,
        }
        records.append(ProposedRecord(
            table_name="Persona",
            action="create",
            target_id=None,
            values=values,
            source_payload_path=f"payload.personas[{i}]",
            batch_id=f"batch:persona:{code}",
        ))

    # Domains (with sub-domains)
    for i, d in enumerate(payload.get("domains", [])):
        domain_code = d.get("code", "")
        domain_values: dict[str, Any] = {
            "name": d.get("name", ""),
            "code": domain_code,
            "identifier": d.get("identifier"),
            "description": d.get("description"),
            "sort_order": d.get("sort_order"),
            "is_service": bool(d.get("is_service", False)),
            "created_by_session_id": ai_session_id,
        }
        records.append(ProposedRecord(
            table_name="Domain",
            action="create",
            target_id=None,
            values=domain_values,
            source_payload_path=f"payload.domains[{i}]",
            batch_id=f"batch:domain:{domain_code}",
        ))

        # Sub-domains
        for j, sd in enumerate(d.get("sub_domains", [])):
            sd_code = sd.get("code", "")
            sd_values: dict[str, Any] = {
                "name": sd.get("name", ""),
                "code": sd_code,
                "identifier": sd.get("identifier"),
                "description": sd.get("description"),
                "sort_order": sd.get("sort_order"),
                "is_service": bool(sd.get("is_service", False)),
                "created_by_session_id": ai_session_id,
            }
            records.append(ProposedRecord(
                table_name="Domain",
                action="create",
                target_id=None,
                values=sd_values,
                source_payload_path=f"payload.domains[{i}].sub_domains[{j}]",
                batch_id=f"batch:domain:{sd_code}",
                intra_batch_refs={"parent_domain_id": f"batch:domain:{domain_code}"},
            ))

    # Processes
    for i, p in enumerate(payload.get("processes", [])):
        proc_code = p.get("code", "")
        domain_code = p.get("domain_code", "")
        proc_values: dict[str, Any] = {
            "name": p.get("name", ""),
            "code": proc_code,
            "description": p.get("description"),
            "sort_order": p.get("sort_order", i + 1),
            "tier": p.get("tier"),
            "created_by_session_id": ai_session_id,
        }

        # Try to resolve domain_id from code
        intra_refs: dict[str, str] = {}
        if domain_code:
            domain_row = conn.execute(
                "SELECT id FROM Domain WHERE code = ?", (domain_code,)
            ).fetchone()
            if domain_row:
                proc_values["domain_id"] = domain_row[0]
            else:
                # Reference a domain being created in this batch
                intra_refs["domain_id"] = f"batch:domain:{domain_code}"

        records.append(ProposedRecord(
            table_name="Process",
            action="create",
            target_id=None,
            values=proc_values,
            source_payload_path=f"payload.processes[{i}]",
            batch_id=f"batch:process:{proc_code}",
            intra_batch_refs=intra_refs,
        ))

    # Cross-domain services -> Domain records with is_service=True
    for i, svc in enumerate(payload.get("cross_domain_services", [])):
        svc_code = svc.get("code", "")
        if not svc_code:
            # Auto-generate: SVC + index (e.g. SVC1, SVC2)
            svc_code = f"SVC{i + 1}"
        svc_values: dict[str, Any] = {
            "name": svc.get("name", ""),
            "code": svc_code,
            "description": svc.get("description"),
            "sort_order": svc.get("sort_order", i + 1),
            "is_service": True,
            "created_by_session_id": ai_session_id,
        }
        records.append(ProposedRecord(
            table_name="Domain",
            action="create",
            target_id=None,
            values=svc_values,
            source_payload_path=f"payload.cross_domain_services[{i}]",
            batch_id=f"batch:domain:{svc_code}" if svc_code else None,
        ))

    # Decisions and open issues from envelope
    if envelope:
        records.extend(map_decisions(
            envelope.get("decisions", []), conn, session_type, ai_session_id,
        ))
        records.extend(map_open_issues(
            envelope.get("open_issues", []), conn, session_type, ai_session_id,
        ))

    return ProposedBatch(
        records=records,
        ai_session_id=ai_session_id,
        work_item_id=work_item["id"],
        session_type=session_type,
    )
