"""Mapper for process_definition payloads.

Target tables: Process (update), ProcessStep (create), Requirement (create),
ProcessEntity (create/update), ProcessField (create/update),
ProcessPersona (create/update).
Per L2 PRD Section 11.3.5.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.mappers.base import (
    find_existing_for_revision,
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
    """Map a process_definition payload to proposed records."""
    records: list[ProposedRecord] = []
    process_id = work_item.get("process_id")

    # Process update
    if process_id:
        proc_values: dict[str, Any] = {}
        if payload.get("process_purpose"):
            proc_values["description"] = payload["process_purpose"]
        triggers = payload.get("triggers")
        if triggers:
            import json
            proc_values["triggers"] = json.dumps(triggers) if isinstance(triggers, dict) else str(triggers)
        completion = payload.get("completion")
        if completion:
            import json
            proc_values["completion_criteria"] = (
                json.dumps(completion) if isinstance(completion, dict) else str(completion)
            )
        if proc_values:
            records.append(ProposedRecord(
                table_name="Process",
                action="update",
                target_id=process_id,
                values=proc_values,
                source_payload_path="payload",
            ))

    # Personas -> ProcessPersona
    for i, p in enumerate(payload.get("personas", [])):
        persona_code = p.get("identifier", p.get("code", ""))
        persona_id = resolve_by_code(conn, "Persona", "code", persona_code) if persona_code else None

        if persona_id is None or process_id is None:
            continue

        # Check for existing ProcessPersona (from domain_overview)
        existing = conn.execute(
            "SELECT id FROM ProcessPersona WHERE process_id = ? AND persona_id = ?",
            (process_id, persona_id),
        ).fetchone()

        if existing:
            records.append(ProposedRecord(
                table_name="ProcessPersona",
                action="update",
                target_id=existing[0],
                values={
                    "role": p.get("role", "performer"),
                    "description": p.get("description", ""),
                },
                source_payload_path=f"payload.personas[{i}]",
            ))
        else:
            records.append(ProposedRecord(
                table_name="ProcessPersona",
                action="create",
                target_id=None,
                values={
                    "process_id": process_id,
                    "persona_id": persona_id,
                    "role": p.get("role", "performer"),
                    "description": p.get("description", ""),
                },
                source_payload_path=f"payload.personas[{i}]",
            ))

    # Workflow steps -> ProcessStep
    for i, step in enumerate(payload.get("workflow", [])):
        step_values: dict[str, Any] = {
            "name": step.get("step_name", step.get("name", "")),
            "description": step.get("description"),
            "step_type": step.get("step_type", "action"),
            "sort_order": step.get("sort_order", i + 1),
            "created_by_session_id": ai_session_id,
        }
        if process_id is not None:
            step_values["process_id"] = process_id

        # Resolve performer persona
        performer = step.get("performer_persona", step.get("performer_persona_id"))
        if performer:
            if isinstance(performer, int):
                step_values["performer_persona_id"] = performer
            elif isinstance(performer, str):
                pid = resolve_by_code(conn, "Persona", "code", performer)
                if pid is not None:
                    step_values["performer_persona_id"] = pid

        step_batch_id = f"batch:step:{process_id}:{i}"
        records.append(ProposedRecord(
            table_name="ProcessStep",
            action="create",
            target_id=None,
            values=step_values,
            source_payload_path=f"payload.workflow[{i}]",
            batch_id=step_batch_id,
        ))

    # Delete old process-level cross-references for this process (they'll be
    # replaced by step-level records). We record these as proposed deletes by
    # noting them but the actual delete happens in commit with special handling.
    # For now, we skip deletion of old records — the new records replace them.

    # Process data -> ProcessEntity and ProcessField
    for i, data_group in enumerate(payload.get("process_data", [])):
        entity_name = data_group.get("entity_name", "")
        entity_id = resolve_by_name(conn, "Entity", entity_name) if entity_name else None
        if entity_id is None and entity_name:
            entity_id = resolve_by_code(conn, "Entity", "code", entity_name)

        if entity_id is not None and process_id is not None:
            records.append(ProposedRecord(
                table_name="ProcessEntity",
                action="create",
                target_id=None,
                values={
                    "process_id": process_id,
                    "entity_id": entity_id,
                    "role": data_group.get("role", "referenced"),
                    "description": data_group.get("description", ""),
                },
                source_payload_path=f"payload.process_data[{i}]",
            ))

            for fi, field_ref in enumerate(data_group.get("field_references", [])):
                field_name = field_ref if isinstance(field_ref, str) else field_ref.get("name", "")
                field_id = resolve_field_by_name(conn, entity_id, field_name)
                if field_id is not None:
                    records.append(ProposedRecord(
                        table_name="ProcessField",
                        action="create",
                        target_id=None,
                        values={
                            "process_id": process_id,
                            "field_id": field_id,
                            "usage": (field_ref.get("usage", "displayed")
                                      if isinstance(field_ref, dict) else "displayed"),
                            "description": (field_ref.get("description", "")
                                            if isinstance(field_ref, dict) else ""),
                        },
                        source_payload_path=f"payload.process_data[{i}].field_references[{fi}]",
                    ))

    # Data collected -> new Fields
    for i, dc_group in enumerate(payload.get("data_collected", [])):
        entity_name = dc_group.get("entity_name", "")
        entity_id = resolve_by_name(conn, "Entity", entity_name) if entity_name else None
        if entity_id is None and entity_name:
            entity_id = resolve_by_code(conn, "Entity", "code", entity_name)

        if entity_id is not None:
            for fi, nf in enumerate(dc_group.get("new_fields", [])):
                field_name = nf.get("field_name", nf.get("name", ""))
                # Check if field exists
                existing_fid = resolve_field_by_name(conn, entity_id, field_name)
                if existing_fid:
                    # Update existing field
                    fv: dict[str, Any] = {}
                    for k in ("label", "field_type", "is_required", "description"):
                        if k in nf:
                            fv[k] = nf[k]
                    if fv:
                        records.append(ProposedRecord(
                            table_name="Field",
                            action="update",
                            target_id=existing_fid,
                            values=fv,
                            source_payload_path=f"payload.data_collected[{i}].new_fields[{fi}]",
                        ))
                else:
                    fv = {
                        "entity_id": entity_id,
                        "name": field_name,
                        "label": nf.get("label", field_name),
                        "field_type": nf.get("field_type", "varchar"),
                        "is_required": nf.get("is_required", False),
                        "description": nf.get("description"),
                        "created_by_session_id": ai_session_id,
                    }
                    records.append(ProposedRecord(
                        table_name="Field",
                        action="create",
                        target_id=None,
                        values=fv,
                        source_payload_path=f"payload.data_collected[{i}].new_fields[{fi}]",
                    ))

    # System requirements -> Requirement
    for i, req in enumerate(payload.get("system_requirements", [])):
        req_id = req.get("identifier", "")
        req_values: dict[str, Any] = {
            "identifier": req_id,
            "description": req.get("description", ""),
            "priority": req.get("priority"),
            "status": req.get("status", "proposed"),
            "created_by_session_id": ai_session_id,
        }
        if process_id is not None:
            req_values["process_id"] = process_id

        action = "create"
        target_id = None
        if session_type in ("revision", "clarification") and req_id:
            existing = find_existing_for_revision(
                conn, "Requirement", "identifier", req_id,
            )
            if existing is not None:
                action = "update"
                target_id = existing
                req_values.pop("created_by_session_id", None)

        records.append(ProposedRecord(
            table_name="Requirement",
            action=action,
            target_id=target_id,
            values=req_values,
            source_payload_path=f"payload.system_requirements[{i}]",
            batch_id=f"batch:requirement:{req_id}" if req_id else None,
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
