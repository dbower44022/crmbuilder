"""Domain Overview document template.

Generates a Domain Overview Word document with domain purpose, personas,
process inventory, and data reference.
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_data_row,
    add_header_row,
    add_heading,
    add_labeled_paragraph,
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
    """Generate a Domain Overview Word document.

    :param data_dict: Data dictionary from queries.domain_overview.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    domain = data_dict.get("domain") or {}
    domain_name = domain.get("name", "Unknown")
    domain_code = domain.get("code", "")

    set_header(section, client_name, f"Domain Overview \u2014 {domain_name}")
    set_footer(section, f"Domain Overview \u2014 {domain_name} Domain")

    if is_draft:
        set_draft_header(section)

    # Title
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, f"Domain Overview \u2014 {domain_name} ({domain_code})",
                  bold=True, size=SUBTITLE_SIZE, color=TITLE_COLOR_RGB,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=400)

    add_page_break(doc)

    # Section 1: Domain Purpose
    add_heading(doc, "1. Domain Purpose", level=1)
    overview_text = data_dict.get("domain_overview_text") or ""
    if overview_text:
        for para in overview_text.split("\n\n"):
            if para.strip():
                add_paragraph(doc, para.strip())
    else:
        add_paragraph(doc, "Domain overview text not yet defined.", italic=True)

    parent = data_dict.get("parent_domain")
    if parent:
        add_paragraph(doc, f"Parent domain: {parent['name']} ({parent['code']})")

    # Section 2: Personas
    add_heading(doc, "2. Personas", level=1)
    personas = data_dict.get("personas", [])
    if personas:
        for persona in personas:
            name = persona.get("name", "")
            code = persona.get("code", "")
            desc = persona.get("description", "") or ""
            add_labeled_paragraph(doc, f"{name} ({code})", f" \u2014 {desc}" if desc else "")
            roles = persona.get("roles", [])
            if roles:
                for role in roles:
                    add_paragraph(doc, f"  \u2022 {role['role']} in {role['process_name']}")
    else:
        add_paragraph(doc, "No personas involved in this domain.", italic=True)

    # Section 3: Process Inventory
    add_heading(doc, "3. Process Inventory", level=1)
    processes = data_dict.get("processes", [])
    if processes:
        for proc in processes:
            name = proc.get("name", "")
            code = proc.get("code", "")
            desc = proc.get("description", "") or ""
            add_labeled_paragraph(doc, f"{name} ({code})", f" \u2014 {desc}" if desc else "")
    else:
        add_paragraph(doc, "No processes defined in this domain.", italic=True)

    # Section 4: Data Reference
    add_page_break(doc)
    add_heading(doc, "4. Data Reference", level=1)
    data_ref = data_dict.get("data_reference", [])
    if data_ref:
        for entity in data_ref:
            entity_name = entity.get("name", "")
            add_heading(doc, f"Entity: {entity_name}", level=2)

            fields = entity.get("fields", [])
            if fields:
                widths = [2000, 2000, 1400, 1500, 2460]
                table = doc.add_table(rows=1, cols=5)
                table.autofit = False
                add_header_row(table, ["Field", "Label", "Type", "Usage", "Notes"], widths)

                for idx, f in enumerate(fields):
                    add_data_row(
                        table,
                        [f.get("name", ""), f.get("label", ""),
                         f.get("field_type", ""), f.get("usage", ""), ""],
                        widths,
                        shaded=idx % 2 == 1,
                    )
    else:
        add_paragraph(doc, "No data references defined.", italic=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
