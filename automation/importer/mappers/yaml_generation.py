"""Mapper for yaml_generation payloads.

Target tables: Field (update), FieldOption (update), Relationship (update),
LayoutPanel (create), LayoutRow (create), LayoutTab (create),
ListColumn (create), Decision (create), OpenIssue (create).
Per L2 PRD Section 11.3.7.
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
    """Map a yaml_generation payload to proposed records."""
    records: list[ProposedRecord] = []

    # Entity configurations -> Field updates
    for i, entity_config in enumerate(payload.get("entity_configurations", [])):
        entity_name = entity_config.get("entity_name", entity_config.get("name", ""))
        entity_id = resolve_by_name(conn, "Entity", entity_name) if entity_name else None
        if entity_id is None and entity_name:
            entity_id = resolve_by_code(conn, "Entity", "code", entity_name)

        if entity_id is None:
            continue

        for fi, field_data in enumerate(entity_config.get("fields", [])):
            field_name = field_data.get("field_name", field_data.get("name", ""))
            field_id = resolve_field_by_name(conn, entity_id, field_name)

            if field_id is not None:
                update_vals: dict[str, Any] = {}
                for key in ("tooltip", "sort_order", "category",
                             "display_as_label", "is_sorted"):
                    if key in field_data:
                        update_vals[key] = field_data[key]
                if update_vals:
                    records.append(ProposedRecord(
                        table_name="Field",
                        action="update",
                        target_id=field_id,
                        values=update_vals,
                        source_payload_path=(
                            f"payload.entity_configurations[{i}].fields[{fi}]"
                        ),
                    ))

                # FieldOption style updates
                for oi, opt in enumerate(field_data.get("options", [])):
                    opt_value = opt.get("value", "")
                    existing_opt = conn.execute(
                        "SELECT id FROM FieldOption WHERE field_id = ? AND value = ?",
                        (field_id, opt_value),
                    ).fetchone()
                    if existing_opt:
                        opt_updates: dict[str, Any] = {}
                        if "style" in opt:
                            opt_updates["style"] = opt["style"]
                        if "label" in opt:
                            opt_updates["label"] = opt["label"]
                        if opt_updates:
                            records.append(ProposedRecord(
                                table_name="FieldOption",
                                action="update",
                                target_id=existing_opt[0],
                                values=opt_updates,
                                source_payload_path=(
                                    f"payload.entity_configurations[{i}]"
                                    f".fields[{fi}].options[{oi}]"
                                ),
                            ))

    # Relationship configurations -> Relationship updates
    for i, rel_config in enumerate(payload.get("relationship_configurations", [])):
        rel_name = rel_config.get("name", "")
        if rel_name:
            rel_row = conn.execute(
                "SELECT id FROM Relationship WHERE name = ?", (rel_name,)
            ).fetchone()
            if rel_row:
                update_vals = {}
                for key in ("link", "link_foreign", "label", "label_foreign",
                             "relation_name", "audited", "audited_foreign", "action"):
                    if key in rel_config:
                        update_vals[key] = rel_config[key]
                if update_vals:
                    records.append(ProposedRecord(
                        table_name="Relationship",
                        action="update",
                        target_id=rel_row[0],
                        values=update_vals,
                        source_payload_path=f"payload.relationship_configurations[{i}]",
                    ))

    # Layout definitions
    for i, layout in enumerate(payload.get("layout_definitions", [])):
        entity_name = layout.get("entity_name", layout.get("name", ""))
        entity_id = resolve_by_name(conn, "Entity", entity_name) if entity_name else None
        if entity_id is None and entity_name:
            entity_id = resolve_by_code(conn, "Entity", "code", entity_name)
        if entity_id is None:
            continue

        for pi, panel in enumerate(layout.get("panels", [])):
            panel_values: dict[str, Any] = {
                "entity_id": entity_id,
                "label": panel.get("label", ""),
                "description": panel.get("description"),
                "tab_break": panel.get("tab_break", False),
                "tab_label": panel.get("tab_label"),
                "style": panel.get("style"),
                "hidden": panel.get("hidden", False),
                "sort_order": panel.get("sort_order", pi + 1),
                "layout_mode": panel.get("layout_mode", "rows"),
                "dynamic_logic_attribute": panel.get("dynamic_logic_attribute"),
                "dynamic_logic_value": panel.get("dynamic_logic_value"),
                "created_by_session_id": ai_session_id,
            }
            panel_batch_id = f"batch:panel:{entity_id}:{pi}"
            records.append(ProposedRecord(
                table_name="LayoutPanel",
                action="create",
                target_id=None,
                values=panel_values,
                source_payload_path=f"payload.layout_definitions[{i}].panels[{pi}]",
                batch_id=panel_batch_id,
            ))

            # Rows
            if panel.get("layout_mode", "rows") == "rows":
                for ri, row in enumerate(panel.get("rows", [])):
                    row_values: dict[str, Any] = {
                        "sort_order": row.get("sort_order", ri + 1),
                        "is_full_width": row.get("is_full_width", False),
                    }

                    # Resolve field references
                    cell_1 = row.get("cell_1_field", row.get("cell_1"))
                    if cell_1:
                        fid = resolve_field_by_name(conn, entity_id, cell_1)
                        if fid is not None:
                            row_values["cell_1_field_id"] = fid
                    cell_2 = row.get("cell_2_field", row.get("cell_2"))
                    if cell_2:
                        fid = resolve_field_by_name(conn, entity_id, cell_2)
                        if fid is not None:
                            row_values["cell_2_field_id"] = fid

                    records.append(ProposedRecord(
                        table_name="LayoutRow",
                        action="create",
                        target_id=None,
                        values=row_values,
                        source_payload_path=(
                            f"payload.layout_definitions[{i}].panels[{pi}].rows[{ri}]"
                        ),
                        intra_batch_refs={"panel_id": panel_batch_id},
                    ))

            # Tabs
            if panel.get("layout_mode") == "tabs":
                for ti, tab in enumerate(panel.get("tabs", [])):
                    tab_values: dict[str, Any] = {
                        "label": tab.get("label", ""),
                        "category": tab.get("category", ""),
                        "sort_order": tab.get("sort_order", ti + 1),
                    }
                    records.append(ProposedRecord(
                        table_name="LayoutTab",
                        action="create",
                        target_id=None,
                        values=tab_values,
                        source_payload_path=(
                            f"payload.layout_definitions[{i}].panels[{pi}].tabs[{ti}]"
                        ),
                        intra_batch_refs={"panel_id": panel_batch_id},
                    ))

        # List columns
        for ci, col in enumerate(layout.get("list_columns", [])):
            field_name = col.get("field_name", col.get("name", ""))
            field_id = resolve_field_by_name(conn, entity_id, field_name)
            if field_id is not None:
                col_values: dict[str, Any] = {
                    "entity_id": entity_id,
                    "field_id": field_id,
                    "width": col.get("width"),
                    "sort_order": col.get("sort_order", ci + 1),
                }
                records.append(ProposedRecord(
                    table_name="ListColumn",
                    action="create",
                    target_id=None,
                    values=col_values,
                    source_payload_path=f"payload.layout_definitions[{i}].list_columns[{ci}]",
                ))

    # Resolved exceptions -> Decision records
    for i, exc in enumerate(payload.get("resolved_exceptions", [])):
        records.append(ProposedRecord(
            table_name="Decision",
            action="create",
            target_id=None,
            values={
                "identifier": exc.get("identifier", f"YAML-DEC-{i+1:03d}"),
                "title": exc.get("description", "")[:100],
                "description": exc.get("resolution", exc.get("description", "")),
                "status": "locked",
                "locked_by_session_id": ai_session_id,
                "created_by_session_id": ai_session_id,
            },
            source_payload_path=f"payload.resolved_exceptions[{i}]",
        ))

    # Unresolved exceptions -> OpenIssue records
    for i, exc in enumerate(payload.get("unresolved_exceptions", [])):
        records.append(ProposedRecord(
            table_name="OpenIssue",
            action="create",
            target_id=None,
            values={
                "identifier": exc.get("identifier", f"YAML-ISS-{i+1:03d}"),
                "title": exc.get("description", "")[:100],
                "description": exc.get("impact", exc.get("description", "")),
                "status": "open",
                "priority": exc.get("priority", "medium"),
                "created_by_session_id": ai_session_id,
            },
            source_payload_path=f"payload.unresolved_exceptions[{i}]",
        ))

    # Envelope-level decisions and open issues
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
