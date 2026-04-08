"""Entity Inventory document template.

Generates a Word document listing all entities with their classification,
business object origin, and process participation.
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_data_row,
    add_header_row,
    add_heading,
    add_page_break,
    add_paragraph,
    create_document,
    set_draft_header,
    set_footer,
    set_header,
)
from automation.docgen.templates.formatting import (
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    WD_ALIGN_PARAGRAPH,
)


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate an Entity Inventory Word document.

    :param data_dict: Data dictionary from queries.entity_inventory.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    set_header(section, client_name, "Entity Inventory")
    set_footer(section, f"Entity Inventory \u2014 {client_name}")

    if is_draft:
        set_draft_header(section)

    # Title
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, "Entity Inventory", bold=True, size=SUBTITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=400)

    add_page_break(doc)

    # Entities
    entities = data_dict.get("entities", [])
    native = [e for e in entities if e.get("is_native")]
    custom = [e for e in entities if not e.get("is_native")]

    add_heading(doc, "1. Native Entities", level=1)
    if native:
        _add_entity_table(doc, native)
    else:
        add_paragraph(doc, "No native entities defined.", italic=True)

    add_heading(doc, "2. Custom Entities", level=1)
    if custom:
        _add_entity_table(doc, custom)
    else:
        add_paragraph(doc, "No custom entities defined.", italic=True)

    # Business Objects
    bos = data_dict.get("business_objects", [])
    if bos:
        add_page_break(doc)
        add_heading(doc, "3. Business Objects", level=1)
        widths = [2000, 2500, 1500, 3360]
        table = doc.add_table(rows=1, cols=4)
        table.autofit = False
        add_header_row(table, ["Name", "Description", "Status", "Resolution"], widths)

        for idx, bo in enumerate(bos):
            resolution = bo.get("resolution") or ""
            detail = bo.get("resolution_detail") or ""
            resolved = bo.get("resolved_entity") or bo.get("resolved_process") or bo.get("resolved_persona") or ""
            res_text = f"{resolution}: {resolved}" if resolution and resolved else resolution
            if detail:
                res_text = f"{res_text} ({detail})" if res_text else detail
            add_data_row(
                table,
                [bo.get("name", ""), bo.get("description", "") or "", bo.get("status", ""), res_text],
                widths,
                shaded=idx % 2 == 1,
                bold_indices={0},
            )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


def _add_entity_table(doc, entities: list[dict]):
    """Add an entity summary table."""
    widths = [2000, 1200, 1200, 2000, 2960]
    table = doc.add_table(rows=1, cols=5)
    table.autofit = False
    add_header_row(table, ["Entity", "Type", "Native", "Domain", "Processes"], widths)

    for idx, e in enumerate(entities):
        procs = ", ".join(p["code"] for p in e.get("process_references", []))
        add_data_row(
            table,
            [
                e.get("name", ""),
                e.get("entity_type", ""),
                "Yes" if e.get("is_native") else "No",
                e.get("primary_domain") or "\u2014",
                procs or "\u2014",
            ],
            widths,
            shaded=idx % 2 == 1,
            bold_indices={0},
        )
