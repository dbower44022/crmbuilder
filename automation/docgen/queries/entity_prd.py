"""Data query for Entity PRD generation.

Implements L2 PRD Section 13.3.3 — queries Entity, Field, FieldOption,
Relationship, LayoutPanel, LayoutRow, LayoutTab, ListColumn, Decision,
OpenIssue, ProcessField, and ProcessEntity tables.
"""

from __future__ import annotations

import sqlite3

from automation.docgen.queries import get_client_row


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for an Entity PRD.

    :param conn: Client database connection.
    :param work_item_id: The entity_prd WorkItem.id.
    :param master_conn: Master database connection (for Client record).
    :returns: Data dictionary for the Entity PRD template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "client_name": None,
        "client_short_name": None,
        "entity": None,
        "fields": [],
        "native_fields": [],
        "custom_fields": [],
        "relationships": [],
        "layout_panels": [],
        "list_columns": [],
        "decisions": [],
        "open_issues": [],
        "contributing_domains": [],
    }

    if master_conn:
        row = get_client_row(master_conn, conn, columns="name, code")
        if row:
            data["client_name"] = row[0]
            data["client_short_name"] = row[1]

    # Get the entity_id from work item
    wi = conn.execute(
        "SELECT entity_id FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if not wi or not wi[0]:
        return data
    entity_id = wi[0]

    # Entity record
    row = conn.execute(
        "SELECT id, name, code, entity_type, is_native, singular_label, "
        "plural_label, description, primary_domain_id "
        "FROM Entity WHERE id = ?",
        (entity_id,),
    ).fetchone()
    if not row:
        return data

    data["entity"] = {
        "id": row[0], "name": row[1], "code": row[2],
        "entity_type": row[3], "is_native": bool(row[4]),
        "singular_label": row[5], "plural_label": row[6],
        "description": row[7], "primary_domain_id": row[8],
    }

    # Contributing domains via ProcessEntity
    domains = conn.execute(
        "SELECT DISTINCT d.name, d.code FROM ProcessEntity pe "
        "JOIN Process p ON pe.process_id = p.id "
        "JOIN Domain d ON p.domain_id = d.id "
        "WHERE pe.entity_id = ? ORDER BY d.name",
        (entity_id,),
    ).fetchall()
    data["contributing_domains"] = [
        {"name": r[0], "code": r[1]} for r in domains
    ]

    # Fields with FieldOptions, split into native/custom
    fields = conn.execute(
        "SELECT id, name, label, field_type, is_required, default_value, "
        "read_only, audited, category, max_length, min_value, max_value, "
        "is_sorted, display_as_label, tooltip, description, sort_order, is_native "
        "FROM Field WHERE entity_id = ? ORDER BY sort_order, name",
        (entity_id,),
    ).fetchall()

    for f in fields:
        field_id = f[0]
        # Get options for enum/multiEnum
        options = []
        if f[3] in ("enum", "multiEnum"):
            opt_rows = conn.execute(
                "SELECT value, label, description, style, sort_order, is_default "
                "FROM FieldOption WHERE field_id = ? ORDER BY sort_order, value",
                (field_id,),
            ).fetchall()
            options = [
                {"value": o[0], "label": o[1], "description": o[2],
                 "style": o[3], "sort_order": o[4], "is_default": bool(o[5])}
                for o in opt_rows
            ]

        # Get processes that reference this field
        proc_refs = conn.execute(
            "SELECT DISTINCT p.name, p.code, pf.usage "
            "FROM ProcessField pf "
            "JOIN Process p ON pf.process_id = p.id "
            "WHERE pf.field_id = ? ORDER BY p.code",
            (field_id,),
        ).fetchall()

        field_dict = {
            "id": f[0], "name": f[1], "label": f[2], "field_type": f[3],
            "is_required": bool(f[4]), "default_value": f[5],
            "read_only": bool(f[6]), "audited": bool(f[7]),
            "category": f[8], "max_length": f[9],
            "min_value": f[10], "max_value": f[11],
            "is_sorted": bool(f[12]), "display_as_label": bool(f[13]),
            "tooltip": f[14], "description": f[15],
            "sort_order": f[16], "is_native": bool(f[17]),
            "options": options,
            "process_references": [
                {"name": p[0], "code": p[1], "usage": p[2]} for p in proc_refs
            ],
        }
        data["fields"].append(field_dict)

        if field_dict["is_native"]:
            data["native_fields"].append(field_dict)
        else:
            data["custom_fields"].append(field_dict)

    # Relationships where this entity is involved
    rels = conn.execute(
        "SELECT r.id, r.name, r.description, r.entity_id, r.entity_foreign_id, "
        "r.link_type, r.link, r.link_foreign, r.label, r.label_foreign, "
        "r.relation_name, "
        "e1.name AS entity_name, e2.name AS foreign_entity_name "
        "FROM Relationship r "
        "JOIN Entity e1 ON r.entity_id = e1.id "
        "JOIN Entity e2 ON r.entity_foreign_id = e2.id "
        "WHERE r.entity_id = ? OR r.entity_foreign_id = ? "
        "ORDER BY r.name",
        (entity_id, entity_id),
    ).fetchall()
    data["relationships"] = [
        {
            "id": r[0], "name": r[1], "description": r[2],
            "entity_id": r[3], "entity_foreign_id": r[4],
            "link_type": r[5], "link": r[6], "link_foreign": r[7],
            "label": r[8], "label_foreign": r[9], "relation_name": r[10],
            "entity_name": r[11], "foreign_entity_name": r[12],
        }
        for r in rels
    ]

    # Layout panels with rows and tabs
    panels = conn.execute(
        "SELECT id, label, description, tab_break, tab_label, style, hidden, "
        "sort_order, layout_mode, dynamic_logic_attribute, dynamic_logic_value "
        "FROM LayoutPanel WHERE entity_id = ? ORDER BY sort_order",
        (entity_id,),
    ).fetchall()

    for p in panels:
        panel_id = p[0]
        rows = conn.execute(
            "SELECT lr.sort_order, "
            "f1.name AS cell1_name, f1.label AS cell1_label, "
            "f2.name AS cell2_name, f2.label AS cell2_label, "
            "lr.is_full_width "
            "FROM LayoutRow lr "
            "LEFT JOIN Field f1 ON lr.cell_1_field_id = f1.id "
            "LEFT JOIN Field f2 ON lr.cell_2_field_id = f2.id "
            "WHERE lr.panel_id = ? ORDER BY lr.sort_order",
            (panel_id,),
        ).fetchall()

        tabs = conn.execute(
            "SELECT label, category, sort_order "
            "FROM LayoutTab WHERE panel_id = ? ORDER BY sort_order",
            (panel_id,),
        ).fetchall()

        data["layout_panels"].append({
            "id": panel_id, "label": p[1], "description": p[2],
            "tab_break": bool(p[3]), "tab_label": p[4],
            "style": p[5], "hidden": bool(p[6]),
            "sort_order": p[7], "layout_mode": p[8],
            "dynamic_logic_attribute": p[9], "dynamic_logic_value": p[10],
            "rows": [
                {
                    "sort_order": r[0], "cell1_name": r[1],
                    "cell1_label": r[2], "cell2_name": r[3],
                    "cell2_label": r[4], "is_full_width": bool(r[5]),
                }
                for r in rows
            ],
            "tabs": [
                {"label": t[0], "category": t[1], "sort_order": t[2]}
                for t in tabs
            ],
        })

    # List columns
    lc = conn.execute(
        "SELECT lc.sort_order, f.name, f.label, lc.width "
        "FROM ListColumn lc "
        "JOIN Field f ON lc.field_id = f.id "
        "WHERE lc.entity_id = ? ORDER BY lc.sort_order",
        (entity_id,),
    ).fetchall()
    data["list_columns"] = [
        {"sort_order": r[0], "field_name": r[1], "field_label": r[2], "width": r[3]}
        for r in lc
    ]

    # Decisions scoped to this entity
    decisions = conn.execute(
        "SELECT identifier, title, description, status "
        "FROM Decision WHERE entity_id = ? ORDER BY identifier",
        (entity_id,),
    ).fetchall()
    data["decisions"] = [
        {"identifier": r[0], "title": r[1], "description": r[2], "status": r[3]}
        for r in decisions
    ]

    # Open issues scoped to this entity
    issues = conn.execute(
        "SELECT identifier, title, description, status, priority "
        "FROM OpenIssue WHERE entity_id = ? ORDER BY identifier",
        (entity_id,),
    ).fetchall()
    data["open_issues"] = [
        {"identifier": r[0], "title": r[1], "description": r[2],
         "status": r[3], "priority": r[4]}
        for r in issues
    ]

    return data
