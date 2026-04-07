"""Mapper for domain_reconciliation payloads.

Target tables: Domain (update), Persona (update), ProcessEntity (update),
ProcessField (update), ProcessPersona (update), Decision (create), Field (update).
Per L2 PRD Section 11.3.6.
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
    """Map a domain_reconciliation payload to proposed records."""
    records: list[ProposedRecord] = []
    domain_id = work_item.get("domain_id")

    # Domain reconciliation text update
    narrative = payload.get("domain_overview_narrative", "")
    if domain_id and narrative:
        records.append(ProposedRecord(
            table_name="Domain",
            action="update",
            target_id=domain_id,
            values={"domain_reconciliation_text": narrative},
            source_payload_path="payload.domain_overview_narrative",
        ))

    # Persona consolidated role updates
    for i, p in enumerate(payload.get("personas", [])):
        persona_code = p.get("identifier", p.get("code", ""))
        if persona_code:
            persona_id = resolve_by_code(conn, "Persona", "code", persona_code)
            if persona_id is not None:
                update_vals: dict[str, Any] = {}
                if p.get("consolidated_role") or p.get("description"):
                    update_vals["description"] = (
                        p.get("consolidated_role") or p.get("description", "")
                    )
                if update_vals:
                    records.append(ProposedRecord(
                        table_name="Persona",
                        action="update",
                        target_id=persona_id,
                        values=update_vals,
                        source_payload_path=f"payload.personas[{i}]",
                    ))

    # Conflict resolutions -> Decision records
    for i, res in enumerate(payload.get("conflict_resolutions", [])):
        dec_values: dict[str, Any] = {
            "identifier": res.get("identifier", f"RECON-DEC-{i+1:03d}"),
            "title": res.get("title", res.get("resolution_description", "")[:100]),
            "description": res.get("resolution_description", res.get("description", "")),
            "status": "locked",
            "locked_by_session_id": ai_session_id,
            "created_by_session_id": ai_session_id,
        }
        if domain_id:
            dec_values["domain_id"] = domain_id

        records.append(ProposedRecord(
            table_name="Decision",
            action="create",
            target_id=None,
            values=dec_values,
            source_payload_path=f"payload.conflict_resolutions[{i}]",
            batch_id=f"batch:decision:{dec_values['identifier']}",
        ))

        # If resolution changes a field, propose field update
        affected = res.get("affected_items", [])
        for item in affected:
            if isinstance(item, dict) and item.get("table") == "Field":
                field_id = item.get("field_id")
                if field_id and item.get("changes"):
                    records.append(ProposedRecord(
                        table_name="Field",
                        action="update",
                        target_id=field_id,
                        values=item["changes"],
                        source_payload_path=f"payload.conflict_resolutions[{i}].affected",
                    ))

    # Consolidated data reference updates
    for i, ref in enumerate(payload.get("consolidated_data_reference", [])):
        entity_name = ref.get("entity_name", "")
        entity_id = resolve_by_name(conn, "Entity", entity_name) if entity_name else None
        if entity_id is None and entity_name:
            entity_id = resolve_by_code(conn, "Entity", "code", entity_name)

        if entity_id is None:
            continue

        # Update ProcessEntity/ProcessField records in this domain
        for fi, field_ref in enumerate(ref.get("deduplicated_fields", [])):
            field_name = field_ref if isinstance(field_ref, str) else field_ref.get("name", "")
            field_id = resolve_field_by_name(conn, entity_id, field_name)
            if field_id is not None and isinstance(field_ref, dict):
                # Check for existing ProcessField to update
                if domain_id:
                    existing = conn.execute(
                        "SELECT pf.id FROM ProcessField pf "
                        "JOIN Process p ON p.id = pf.process_id "
                        "WHERE pf.field_id = ? AND p.domain_id = ? LIMIT 1",
                        (field_id, domain_id),
                    ).fetchone()
                    if existing:
                        update_vals = {}
                        if field_ref.get("usage"):
                            update_vals["usage"] = field_ref["usage"]
                        if field_ref.get("description"):
                            update_vals["description"] = field_ref["description"]
                        if update_vals:
                            records.append(ProposedRecord(
                                table_name="ProcessField",
                                action="update",
                                target_id=existing[0],
                                values=update_vals,
                                source_payload_path=(
                                    f"payload.consolidated_data_reference[{i}]"
                                    f".deduplicated_fields[{fi}]"
                                ),
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
