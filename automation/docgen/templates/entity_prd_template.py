"""Entity PRD document template.

Generates an Entity PRD Word document matching the structure and formatting
of the reference implementation in generate-entity-prd-template.js.

Document structure (9 sections):
  1. Entity Overview — metadata, description, domain coverage
  2. Native Fields — fields that exist on the platform entity type
  3. Custom Fields — fields created via YAML, grouped by category
  4. Relationships — all relationships involving this entity
  5. Dynamic Logic Rules — placeholder (reconstructed from layout data)
  6. Layout Guidance — panel/tab grouping
  7. Implementation Notes — placeholder
  8. Open Issues — unresolved questions
  9. Decisions Made — decisions from the entity definition session
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_data_row,
    add_field_table,
    add_header_row,
    add_heading,
    add_labeled_paragraph,
    add_meta_table,
    add_page_break,
    add_paragraph,
    add_two_col_table,
    create_document,
    set_draft_header,
    set_footer,
    set_header,
)
from automation.docgen.templates.formatting import (
    GRAY_TEXT_RGB,
    META_COL_WIDTHS_ENTITY,
    NATIVE_FIELD_COL_HEADERS,
    NATIVE_FIELD_COL_WIDTHS,
    REL_COL_HEADERS,
    REL_COL_WIDTHS,
    SMALL_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    TWO_COL_WIDTHS,
)


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate an Entity PRD Word document.

    :param data_dict: Data dictionary from queries.entity_prd.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    entity = data_dict.get("entity") or {}
    entity_name = entity.get("name", "Unknown")

    set_header(section, client_name, f"{entity_name} Entity PRD")
    set_footer(section, f"Entity PRD \u2014 {entity_name}")

    if is_draft:
        set_draft_header(section)

    # Title page
    add_paragraph(doc, client_name, bold=True, size=SMALL_SIZE,
                  color=GRAY_TEXT_RGB, space_after=40)
    add_paragraph(doc, f"{entity_name} Entity PRD", bold=True,
                  size=TITLE_SIZE, color=TITLE_COLOR_RGB, space_after=200)

    # Metadata table
    native_str = "Native" if entity.get("is_native") else "Custom"
    e_type = entity.get("entity_type", "")
    domains_str = ", ".join(
        f"{d['name']} ({d['code']})" for d in data_dict.get("contributing_domains", [])
    )
    add_meta_table(doc, [
        ("Document Type", "Entity PRD"),
        ("Entity", f"{entity_name} ({native_str} \u2014 {e_type} Type)"),
        ("Implementation", client_name),
    ], META_COL_WIDTHS_ENTITY)

    add_page_break(doc)

    # Section 1: Entity Overview
    add_heading(doc, "1. Entity Overview", level=1)
    meta_rows = [
        ("CRM Entity Name", entity_name),
        ("Native / Custom", native_str),
        ("Entity Type", e_type),
        ("Display Label (Singular)", entity.get("singular_label") or entity_name),
        ("Display Label (Plural)", entity.get("plural_label") or f"{entity_name}s"),
        ("Contributing Domains", domains_str or "\u2014"),
    ]
    add_meta_table(doc, meta_rows, META_COL_WIDTHS_ENTITY)

    desc = entity.get("description") or ""
    if desc:
        add_paragraph(doc, "")
        add_paragraph(doc, desc)

    # Section 2: Native Fields
    add_page_break(doc)
    add_heading(doc, "2. Native Fields", level=1)
    native_fields = data_dict.get("native_fields", [])
    if native_fields:
        table = doc.add_table(rows=1, cols=len(NATIVE_FIELD_COL_WIDTHS))
        table.autofit = False
        add_header_row(table, NATIVE_FIELD_COL_HEADERS, NATIVE_FIELD_COL_WIDTHS)

        for idx, f in enumerate(native_fields):
            proc_refs = ", ".join(p["code"] for p in f.get("process_references", []))
            add_data_row(
                table,
                [f.get("name", ""), f.get("field_type", ""),
                 f.get("label", ""), proc_refs or "\u2014"],
                NATIVE_FIELD_COL_WIDTHS,
                shaded=idx % 2 == 1,
                bold_indices={0},
            )
    else:
        add_paragraph(doc, "No native fields documented.", italic=True)

    # Section 3: Custom Fields
    add_page_break(doc)
    add_heading(doc, "3. Custom Fields", level=1)
    custom_fields = data_dict.get("custom_fields", [])
    if custom_fields:
        # Group by category
        categories: dict[str, list] = {}
        for f in custom_fields:
            cat = f.get("category") or "General"
            categories.setdefault(cat, []).append(f)

        for cat_name, fields in categories.items():
            add_heading(doc, cat_name, level=2)
            # Prepare field data for the field table
            table_fields = []
            for f in fields:
                options = f.get("options", [])
                values_str = ", ".join(o["label"] for o in options) if options else "\u2014"
                table_fields.append({
                    "label": f.get("label", f.get("name", "")),
                    "field_type": f.get("field_type", ""),
                    "is_required": f.get("is_required", False),
                    "values": values_str,
                    "default_value": f.get("default_value"),
                    "identifier": f.get("name", ""),
                    "description": f.get("description", ""),
                })
            add_field_table(doc, table_fields)
    else:
        add_paragraph(doc, "No custom fields defined.", italic=True)

    # Section 4: Relationships
    add_page_break(doc)
    add_heading(doc, "4. Relationships", level=1)
    rels = data_dict.get("relationships", [])
    if rels:
        table = doc.add_table(rows=1, cols=len(REL_COL_WIDTHS))
        table.autofit = False
        add_header_row(table, REL_COL_HEADERS, REL_COL_WIDTHS)

        for idx, r in enumerate(rels):
            # Determine the "other" entity
            other = r.get("foreign_entity_name", "") if r.get("entity_id") == entity.get("id") else r.get("entity_name", "")
            add_data_row(
                table,
                [r.get("name", ""), other, r.get("link_type", ""),
                 r.get("description", "") or "\u2014", "\u2014"],
                REL_COL_WIDTHS,
                shaded=idx % 2 == 1,
                bold_indices={0},
            )
    else:
        add_paragraph(doc, "No relationships defined.", italic=True)

    # Section 5: Dynamic Logic Rules (from layout panel conditions)
    add_page_break(doc)
    add_heading(doc, "5. Dynamic Logic Rules", level=1)
    panels = data_dict.get("layout_panels", [])
    has_logic = False
    for panel in panels:
        attr = panel.get("dynamic_logic_attribute")
        val = panel.get("dynamic_logic_value")
        if attr and val:
            has_logic = True
            add_labeled_paragraph(
                doc,
                f"Panel: {panel.get('label', '')} \u2014 ",
                f"Visible when {attr} = {val}",
            )
    if not has_logic:
        add_paragraph(doc, "No dynamic logic rules defined.", italic=True)

    # Section 6: Layout Guidance
    add_page_break(doc)
    add_heading(doc, "6. Layout Guidance", level=1)
    if panels:
        for panel in panels:
            label = panel.get("label", "")
            add_paragraph(doc, label, bold=True, color=TITLE_COLOR_RGB)
            rows = panel.get("rows", [])
            if rows:
                fields_text = ", ".join(
                    r.get("cell1_label") or r.get("cell1_name") or ""
                    for r in rows if r.get("cell1_name")
                )
                if fields_text:
                    add_paragraph(doc, fields_text)
    else:
        add_paragraph(doc, "No layout guidance defined.", italic=True)

    # Section 7: Implementation Notes
    add_heading(doc, "7. Implementation Notes", level=1)
    add_paragraph(doc, "Implementation notes will be added during YAML generation.", italic=True)

    # Section 8: Open Issues
    add_page_break(doc)
    add_heading(doc, "8. Open Issues", level=1)
    issues = data_dict.get("open_issues", [])
    if issues:
        add_two_col_table(
            doc, "ID", "Issue",
            [(i["identifier"], i.get("description", i.get("title", ""))) for i in issues],
            TWO_COL_WIDTHS,
        )
    else:
        add_paragraph(doc, "No open issues.", italic=True)

    # Section 9: Decisions Made
    add_heading(doc, "9. Decisions Made", level=1)
    decisions = data_dict.get("decisions", [])
    if decisions:
        add_two_col_table(
            doc, "ID", "Decision",
            [(d["identifier"], d.get("description", d.get("title", ""))) for d in decisions],
            TWO_COL_WIDTHS,
        )
    else:
        add_paragraph(doc, "No decisions recorded.", italic=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
