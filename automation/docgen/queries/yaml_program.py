"""Data query for YAML Program Files generation.

Implements L2 PRD Section 13.3.7 — queries Entity, Field, FieldOption,
Relationship, LayoutPanel, LayoutRow, LayoutTab, and ListColumn tables.

Only custom fields (is_native = FALSE) are included in YAML output.
"""

from __future__ import annotations

import sqlite3


def query(
    conn: sqlite3.Connection,
    work_item_id: int,
    master_conn: sqlite3.Connection | None = None,
) -> dict:
    """Assemble the data dictionary for YAML Program Files.

    :param conn: Client database connection.
    :param work_item_id: The yaml_generation WorkItem.id.
    :param master_conn: Master database connection (unused).
    :returns: Data dictionary for the YAML Program template.
    """
    data: dict = {
        "work_item_id": work_item_id,
        "entities": [],
    }

    # Get domain_id from work item
    wi = conn.execute(
        "SELECT domain_id FROM WorkItem WHERE id = ?", (work_item_id,)
    ).fetchone()
    if not wi or not wi[0]:
        return data
    domain_id = wi[0]

    # Entities in scope for this domain
    entity_rows = conn.execute(
        "SELECT DISTINCT e.id, e.name, e.code, e.entity_type, e.is_native, "
        "e.singular_label, e.plural_label, e.description "
        "FROM Entity e "
        "LEFT JOIN ProcessEntity pe ON pe.entity_id = e.id "
        "LEFT JOIN Process p ON pe.process_id = p.id "
        "WHERE e.primary_domain_id = ? OR p.domain_id = ? "
        "ORDER BY e.name",
        (domain_id, domain_id),
    ).fetchall()

    for er in entity_rows:
        entity_id = er[0]
        entity = {
            "id": entity_id,
            "name": er[1], "code": er[2], "entity_type": er[3],
            "is_native": bool(er[4]),
            "singular_label": er[5], "plural_label": er[6],
            "description": er[7],
            "fields": [],
            "relationships": [],
            "layout_panels": [],
            "list_columns": [],
        }

        # Custom fields only (is_native = FALSE)
        fields = conn.execute(
            "SELECT id, name, label, field_type, is_required, default_value, "
            "read_only, audited, max_length, tooltip, description, sort_order "
            "FROM Field WHERE entity_id = ? AND is_native = 0 "
            "ORDER BY sort_order, name",
            (entity_id,),
        ).fetchall()

        for f in fields:
            field_id = f[0]
            options = []
            if f[3] in ("enum", "multiEnum"):
                opt_rows = conn.execute(
                    "SELECT value, label, style, sort_order, is_default "
                    "FROM FieldOption WHERE field_id = ? ORDER BY sort_order, value",
                    (field_id,),
                ).fetchall()
                options = [
                    {"value": o[0], "label": o[1], "style": o[2],
                     "sort_order": o[3], "is_default": bool(o[4])}
                    for o in opt_rows
                ]

            entity["fields"].append({
                "name": f[1], "label": f[2], "field_type": f[3],
                "is_required": bool(f[4]), "default_value": f[5],
                "read_only": bool(f[6]), "audited": bool(f[7]),
                "max_length": f[8], "tooltip": f[9],
                "description": f[10], "sort_order": f[11],
                "options": options,
            })

        # Relationships involving this entity
        rels = conn.execute(
            "SELECT r.name, r.link_type, r.link, r.link_foreign, "
            "r.label, r.label_foreign, r.relation_name, "
            "r.entity_id, r.entity_foreign_id, "
            "e1.name AS entity_name, e2.name AS foreign_entity_name "
            "FROM Relationship r "
            "JOIN Entity e1 ON r.entity_id = e1.id "
            "JOIN Entity e2 ON r.entity_foreign_id = e2.id "
            "WHERE r.entity_id = ? OR r.entity_foreign_id = ?",
            (entity_id, entity_id),
        ).fetchall()

        entity["relationships"] = [
            {
                "name": r[0], "link_type": r[1],
                "link": r[2], "link_foreign": r[3],
                "label": r[4], "label_foreign": r[5],
                "relation_name": r[6],
                "entity_id": r[7], "entity_foreign_id": r[8],
                "entity_name": r[9], "foreign_entity_name": r[10],
            }
            for r in rels
        ]

        # Layout panels with rows and tabs
        panels = conn.execute(
            "SELECT id, label, tab_break, tab_label, style, hidden, "
            "sort_order, layout_mode, dynamic_logic_attribute, dynamic_logic_value "
            "FROM LayoutPanel WHERE entity_id = ? ORDER BY sort_order",
            (entity_id,),
        ).fetchall()

        for p in panels:
            panel_id = p[0]
            rows = conn.execute(
                "SELECT f1.name, f2.name, lr.is_full_width, lr.sort_order "
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

            entity["layout_panels"].append({
                "label": p[1], "tab_break": bool(p[2]),
                "tab_label": p[3], "style": p[4],
                "hidden": bool(p[5]), "sort_order": p[6],
                "layout_mode": p[7],
                "dynamic_logic_attribute": p[8],
                "dynamic_logic_value": p[9],
                "rows": [
                    {"cell1": r[0], "cell2": r[1],
                     "is_full_width": bool(r[2]), "sort_order": r[3]}
                    for r in rows
                ],
                "tabs": [
                    {"label": t[0], "category": t[1], "sort_order": t[2]}
                    for t in tabs
                ],
            })

        # List columns
        lc_rows = conn.execute(
            "SELECT f.name, lc.width, lc.sort_order "
            "FROM ListColumn lc "
            "JOIN Field f ON lc.field_id = f.id "
            "WHERE lc.entity_id = ? ORDER BY lc.sort_order",
            (entity_id,),
        ).fetchall()
        entity["list_columns"] = [
            {"field": r[0], "width": r[1], "sort_order": r[2]}
            for r in lc_rows
        ]

        data["entities"].append(entity)

    return data
