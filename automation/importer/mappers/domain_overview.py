"""Mapper for domain_overview payloads.

Target tables: Domain (update), ProcessPersona (create), ProcessEntity (create),
ProcessField (create).
Per L2 PRD Section 11.3.4.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.mappers.base import (
    map_decisions,
    map_open_issues,
    resolve_by_code,
    resolve_by_name,
    resolve_field_by_name,
)
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
    """Map a domain_overview payload to proposed records."""
    records: list[ProposedRecord] = []
    domain_id = work_item.get("domain_id")

    # Domain overview text update
    purpose = payload.get("domain_purpose", "")
    if domain_id and purpose:
        records.append(ProposedRecord(
            table_name="Domain",
            action="update",
            target_id=domain_id,
            values={"domain_overview_text": purpose},
            source_payload_path="payload.domain_purpose",
        ))

    # Process updates from business_process_inventory
    for i, proc_info in enumerate(payload.get("business_process_inventory", [])):
        proc_code = proc_info.get("process_code", "")
        if proc_code:
            proc_id = resolve_by_code(conn, "Process", "code", proc_code)
            if proc_id is not None:
                update_vals: dict[str, Any] = {}
                if proc_info.get("description"):
                    update_vals["description"] = proc_info["description"]
                if update_vals:
                    records.append(ProposedRecord(
                        table_name="Process",
                        action="update",
                        target_id=proc_id,
                        values=update_vals,
                        source_payload_path=f"payload.business_process_inventory[{i}]",
                    ))

    # Persona roles -> ProcessPersona
    for i, p in enumerate(payload.get("personas", [])):
        persona_code = p.get("identifier", p.get("code", ""))
        persona_id = None
        if persona_code:
            persona_id = resolve_by_code(conn, "Persona", "code", persona_code)

        if persona_id is None:
            continue

        # Create ProcessPersona for each process this persona participates in
        processes = p.get("processes", [])
        if not processes and p.get("domain_specific_role"):
            # Single role for all processes in domain
            if domain_id:
                domain_processes = conn.execute(
                    "SELECT id FROM Process WHERE domain_id = ?", (domain_id,)
                ).fetchall()
                for proc_row in domain_processes:
                    records.append(ProposedRecord(
                        table_name="ProcessPersona",
                        action="create",
                        target_id=None,
                        values={
                            "process_id": proc_row[0],
                            "persona_id": persona_id,
                            "role": p.get("role", "performer"),
                            "description": p.get("domain_specific_role", ""),
                        },
                        source_payload_path=f"payload.personas[{i}]",
                    ))
        else:
            for proc_ref in processes:
                proc_code = proc_ref if isinstance(proc_ref, str) else proc_ref.get("process_code", "")
                proc_id = resolve_by_code(conn, "Process", "code", proc_code)
                if proc_id is not None:
                    records.append(ProposedRecord(
                        table_name="ProcessPersona",
                        action="create",
                        target_id=None,
                        values={
                            "process_id": proc_id,
                            "persona_id": persona_id,
                            "role": (proc_ref.get("role", "performer")
                                     if isinstance(proc_ref, dict) else "performer"),
                            "description": (proc_ref.get("description", "")
                                            if isinstance(proc_ref, dict)
                                            else p.get("domain_specific_role", "")),
                        },
                        source_payload_path=f"payload.personas[{i}]",
                    ))

    # Data reference -> ProcessEntity and ProcessField
    for i, ref in enumerate(payload.get("data_reference", [])):
        entity_name = ref.get("entity_identifier", ref.get("entity_name", ""))
        entity_id = None
        if entity_name:
            entity_id = resolve_by_name(conn, "Entity", entity_name)
            if entity_id is None:
                entity_id = resolve_by_code(conn, "Entity", "code", entity_name)

        if entity_id is None:
            continue

        # Determine process — from usage_notes or domain context
        process_ids: list[int] = []
        if domain_id:
            rows = conn.execute(
                "SELECT id FROM Process WHERE domain_id = ?", (domain_id,)
            ).fetchall()
            process_ids = [r[0] for r in rows]

        for pid in process_ids:
            records.append(ProposedRecord(
                table_name="ProcessEntity",
                action="create",
                target_id=None,
                values={
                    "process_id": pid,
                    "entity_id": entity_id,
                    "role": ref.get("role", "referenced"),
                    "description": ref.get("usage_notes", ""),
                },
                source_payload_path=f"payload.data_reference[{i}]",
            ))

        # Referenced fields
        for fi, field_ref in enumerate(ref.get("referenced_fields", [])):
            field_name = field_ref if isinstance(field_ref, str) else field_ref.get("name", "")
            field_id = resolve_field_by_name(conn, entity_id, field_name) if entity_id else None
            if field_id is not None:
                for pid in process_ids:
                    usage = "displayed"
                    desc = ""
                    if isinstance(field_ref, dict):
                        usage = field_ref.get("usage", "displayed")
                        desc = field_ref.get("description", "")
                    records.append(ProposedRecord(
                        table_name="ProcessField",
                        action="create",
                        target_id=None,
                        values={
                            "process_id": pid,
                            "field_id": field_id,
                            "usage": usage,
                            "description": desc,
                        },
                        source_payload_path=f"payload.data_reference[{i}].referenced_fields[{fi}]",
                    ))

    # Decisions and open issues
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
