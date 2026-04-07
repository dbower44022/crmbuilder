"""Mapper for entity_prd payloads.

Target tables: Entity (update), Field (create/update), FieldOption (create/update),
Relationship (create), Requirement (create).
Per L2 PRD Section 11.3.3.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from automation.importer.mappers.base import (
    find_existing_for_revision,
    find_field_for_revision,
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
    """Map an entity_prd payload to proposed records."""
    records: list[ProposedRecord] = []
    entity_id = work_item.get("entity_id")

    # Entity metadata update
    metadata = payload.get("entity_metadata", {})
    if entity_id and metadata:
        entity_update: dict[str, Any] = {}
        for key in ("entity_type", "is_native", "singular_label",
                     "plural_label", "description"):
            if key in metadata:
                entity_update[key] = metadata[key]
        if entity_update:
            records.append(ProposedRecord(
                table_name="Entity",
                action="update",
                target_id=entity_id,
                values=entity_update,
                source_payload_path="payload.entity_metadata",
            ))

    # Native fields
    for i, f in enumerate(payload.get("native_fields", [])):
        _map_field(
            conn, records, f, entity_id, ai_session_id,
            session_type, is_native=True,
            path=f"payload.native_fields[{i}]",
        )

    # Custom fields
    for i, f in enumerate(payload.get("custom_fields", [])):
        _map_field(
            conn, records, f, entity_id, ai_session_id,
            session_type, is_native=False,
            path=f"payload.custom_fields[{i}]",
        )

    # Relationships
    for i, rel in enumerate(payload.get("relationships", [])):
        rel_values: dict[str, Any] = {
            "name": rel.get("name", ""),
            "description": rel.get("description", ""),
            "link_type": rel.get("link_type", "oneToMany"),
            "link": rel.get("link", ""),
            "link_foreign": rel.get("link_foreign", ""),
            "label": rel.get("label", ""),
            "label_foreign": rel.get("label_foreign", ""),
            "relation_name": rel.get("relation_name"),
            "audited": rel.get("audited", False),
            "audited_foreign": rel.get("audited_foreign", False),
            "action": rel.get("action"),
            "created_by_session_id": ai_session_id,
        }
        if entity_id is not None:
            rel_values["entity_id"] = entity_id

        # Resolve foreign entity
        intra_refs: dict[str, str] = {}
        foreign_entity = rel.get("entity_foreign")
        if foreign_entity:
            if isinstance(foreign_entity, int):
                rel_values["entity_foreign_id"] = foreign_entity
            else:
                feid = resolve_by_name(conn, "Entity", foreign_entity)
                if feid is None:
                    feid = resolve_by_code(conn, "Entity", "code", foreign_entity)
                if feid is not None:
                    rel_values["entity_foreign_id"] = feid

        records.append(ProposedRecord(
            table_name="Relationship",
            action="create",
            target_id=None,
            values=rel_values,
            source_payload_path=f"payload.relationships[{i}]",
            intra_batch_refs=intra_refs,
        ))

    # Requirements
    for i, req in enumerate(payload.get("system_requirements",
                                         payload.get("requirements", []))):
        req_id = req.get("identifier", "")
        req_values: dict[str, Any] = {
            "identifier": req_id,
            "description": req.get("description", ""),
            "priority": req.get("priority"),
            "status": req.get("status", "proposed"),
            "created_by_session_id": ai_session_id,
        }

        # Resolve process_id from scope
        proc_code = req.get("process_code")
        if proc_code:
            pid = resolve_by_code(conn, "Process", "code", proc_code)
            if pid is not None:
                req_values["process_id"] = pid
        elif work_item.get("process_id"):
            req_values["process_id"] = work_item["process_id"]

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
            source_payload_path=f"payload.requirements[{i}]",
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


def _map_field(
    conn: sqlite3.Connection,
    records: list[ProposedRecord],
    f: dict,
    entity_id: int | None,
    ai_session_id: int,
    session_type: str,
    is_native: bool,
    path: str,
) -> None:
    """Map a single field definition to ProposedRecord(s)."""
    field_name = f.get("field_name", f.get("name", ""))
    field_values: dict[str, Any] = {
        "name": field_name,
        "label": f.get("label", field_name),
        "field_type": f.get("field_type", "varchar"),
        "is_required": f.get("is_required", False),
        "default_value": f.get("default_value"),
        "read_only": f.get("read_only", False),
        "audited": f.get("audited", False),
        "category": f.get("category"),
        "max_length": f.get("max_length"),
        "min_value": f.get("min_value"),
        "max_value": f.get("max_value"),
        "is_sorted": f.get("is_sorted", False),
        "display_as_label": f.get("display_as_label", False),
        "tooltip": f.get("tooltip"),
        "description": f.get("description"),
        "sort_order": f.get("sort_order"),
        "is_native": is_native,
    }

    # Check if field already exists (update vs create)
    action = "create"
    target_id = None
    intra_refs: dict[str, str] = {}

    if entity_id is not None:
        existing_fid = find_field_for_revision(conn, entity_id, field_name)
        if existing_fid is not None:
            action = "update"
            target_id = existing_fid
        else:
            field_values["entity_id"] = entity_id
            field_values["created_by_session_id"] = ai_session_id

    field_batch_id = f"batch:field:{entity_id}:{field_name}"
    records.append(ProposedRecord(
        table_name="Field",
        action=action,
        target_id=target_id,
        values=field_values,
        source_payload_path=path,
        batch_id=field_batch_id,
        intra_batch_refs=intra_refs,
    ))

    # Field options for enum/multiEnum
    if field_values["field_type"] in ("enum", "multiEnum"):
        for oi, opt in enumerate(f.get("options", [])):
            opt_value = opt.get("value", "")
            opt_values: dict[str, Any] = {
                "value": opt_value,
                "label": opt.get("label", opt_value),
                "description": opt.get("description"),
                "style": opt.get("style"),
                "sort_order": opt.get("sort_order"),
                "is_default": opt.get("is_default", False),
            }

            opt_action = "create"
            opt_target = None

            # If field exists, check for existing option
            if target_id is not None:
                existing_opt = conn.execute(
                    "SELECT id FROM FieldOption WHERE field_id = ? AND value = ?",
                    (target_id, opt_value),
                ).fetchone()
                if existing_opt:
                    opt_action = "update"
                    opt_target = existing_opt[0]
                else:
                    opt_values["created_by_session_id"] = ai_session_id
            else:
                opt_values["created_by_session_id"] = ai_session_id

            records.append(ProposedRecord(
                table_name="FieldOption",
                action=opt_action,
                target_id=opt_target,
                values=opt_values,
                source_payload_path=f"{path}.options[{oi}]",
                intra_batch_refs=(
                    {"field_id": field_batch_id} if opt_action == "create" else {}
                ),
            ))
