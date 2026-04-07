"""Mapper for business_object_discovery payloads.

Target tables: BusinessObject (create), Entity (create), Field (create),
FieldOption (create), Persona (update).
Per L2 PRD Section 11.3.2.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.mappers.base import (
    map_decisions,
    map_open_issues,
    resolve_by_code,
    resolve_by_name,
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
    """Map a business_object_discovery payload to proposed records."""
    records: list[ProposedRecord] = []

    for i, bo in enumerate(payload.get("business_objects", [])):
        bo_name = bo.get("name", "")
        classification = bo.get("classification", "")
        status = "classified" if classification else "unclassified"
        if bo.get("status"):
            status = bo["status"]

        # Map resolution from classification
        resolution_map = {
            "entity": "entity",
            "process": "process",
            "persona": "persona",
            "field_value": "field_value",
            "lifecycle_state": "lifecycle_state",
            "relationship": "relationship",
        }
        resolution = resolution_map.get(classification)

        bo_values: dict[str, Any] = {
            "name": bo_name,
            "description": bo.get("description"),
            "status": status,
            "resolution": resolution,
            "created_by_session_id": ai_session_id,
        }

        intra_refs_bo: dict[str, str] = {}

        # Entity-classified: create Entity record
        if classification == "entity":
            entity_name = bo.get("entity_name", bo_name)
            entity_code = bo.get("entity_code", "")
            # Sometimes the entity data is nested
            if not entity_code:
                # Generate from name
                entity_code = entity_name.upper().replace(" ", "")

            entity_type = bo.get("entity_type", "Base")
            is_native = bo.get("is_native", False)

            # Resolve primary_domain_id
            primary_domain_id = None
            domain_code = None
            src_domains = bo.get("source_domains", [])
            if src_domains:
                domain_code = src_domains[0] if isinstance(src_domains[0], str) else None
                if domain_code:
                    primary_domain_id = resolve_by_code(conn, "Domain", "code", domain_code)

            entity_values: dict[str, Any] = {
                "name": entity_name,
                "code": entity_code,
                "entity_type": entity_type,
                "is_native": is_native,
                "singular_label": bo.get("singular_label", entity_name),
                "plural_label": bo.get("plural_label", entity_name + "s"),
                "description": bo.get("description"),
                "created_by_session_id": ai_session_id,
            }
            if primary_domain_id is not None:
                entity_values["primary_domain_id"] = primary_domain_id

            entity_batch_id = f"batch:entity:{entity_code}"
            records.append(ProposedRecord(
                table_name="Entity",
                action="create",
                target_id=None,
                values=entity_values,
                source_payload_path=f"payload.business_objects[{i}].entity",
                batch_id=entity_batch_id,
            ))

            intra_refs_bo["resolved_to_entity_id"] = entity_batch_id

            # Initial fields for this entity
            for fi, field_data in enumerate(bo.get("fields", [])):
                field_name = field_data.get("field_name", field_data.get("name", ""))
                field_values: dict[str, Any] = {
                    "name": field_name,
                    "label": field_data.get("label", field_name),
                    "field_type": field_data.get("field_type", "varchar"),
                    "is_required": field_data.get("is_required", False),
                    "is_native": field_data.get("is_native", False),
                    "description": field_data.get("description"),
                    "created_by_session_id": ai_session_id,
                }

                field_batch_id = f"batch:field:{entity_code}:{field_name}"
                records.append(ProposedRecord(
                    table_name="Field",
                    action="create",
                    target_id=None,
                    values=field_values,
                    source_payload_path=f"payload.business_objects[{i}].fields[{fi}]",
                    batch_id=field_batch_id,
                    intra_batch_refs={"entity_id": entity_batch_id},
                ))

                # Field options for enum/multiEnum
                if field_values["field_type"] in ("enum", "multiEnum"):
                    for oi, opt in enumerate(field_data.get("options", [])):
                        opt_values: dict[str, Any] = {
                            "value": opt.get("value", ""),
                            "label": opt.get("label", opt.get("value", "")),
                            "created_by_session_id": ai_session_id,
                        }
                        records.append(ProposedRecord(
                            table_name="FieldOption",
                            action="create",
                            target_id=None,
                            values=opt_values,
                            source_payload_path=(
                                f"payload.business_objects[{i}].fields[{fi}].options[{oi}]"
                            ),
                            intra_batch_refs={"field_id": field_batch_id},
                        ))

        elif classification == "process":
            proc_code = bo.get("process_code", "")
            if proc_code:
                proc_id = resolve_by_code(conn, "Process", "code", proc_code)
                if proc_id is not None:
                    bo_values["resolved_to_process_id"] = proc_id

        elif classification == "persona":
            persona_code = bo.get("persona_code", "")
            if persona_code:
                persona_id = resolve_by_code(conn, "Persona", "code", persona_code)
                if persona_id is not None:
                    bo_values["resolved_to_persona_id"] = persona_id

        records.append(ProposedRecord(
            table_name="BusinessObject",
            action="create",
            target_id=None,
            values=bo_values,
            source_payload_path=f"payload.business_objects[{i}]",
            batch_id=f"batch:bo:{bo_name}",
            intra_batch_refs=intra_refs_bo,
        ))

    # Persona CRM mapping updates
    for bo in payload.get("business_objects", []):
        if bo.get("classification") == "persona" and bo.get("persona_mapping"):
            mapping = bo["persona_mapping"]
            persona_code = bo.get("persona_code", "")
            persona_id = resolve_by_code(conn, "Persona", "code", persona_code)
            if persona_id is not None:
                update_values: dict[str, Any] = {}
                entity_name = mapping.get("entity_name")
                if entity_name:
                    eid = resolve_by_name(conn, "Entity", entity_name)
                    if eid is not None:
                        update_values["persona_entity_id"] = eid
                field_name = mapping.get("field_name")
                if field_name and update_values.get("persona_entity_id"):
                    from automation.importer.mappers.base import resolve_field_by_name
                    fid = resolve_field_by_name(
                        conn, update_values["persona_entity_id"], field_name,
                    )
                    if fid is not None:
                        update_values["persona_field_id"] = fid
                fval = mapping.get("field_value")
                if fval is not None:
                    update_values["persona_field_value"] = fval

                if update_values:
                    records.append(ProposedRecord(
                        table_name="Persona",
                        action="update",
                        target_id=persona_id,
                        values=update_values,
                        source_payload_path="payload.business_objects.persona_mapping",
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
