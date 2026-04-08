"""Master PRD document template.

Generates a Word document containing the organization overview, personas,
domain inventory, and process inventory.
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
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
    """Generate a Master PRD Word document.

    :param data_dict: Data dictionary from queries.master_prd.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    set_header(section, client_name, "Master PRD")
    set_footer(section, f"Master PRD \u2014 {client_name}")

    if is_draft:
        set_draft_header(section)

    # Title page
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, "Master PRD", bold=True, size=SUBTITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=400)

    add_page_break(doc)

    # Section 1: Organization Overview
    add_heading(doc, "1. Organization Overview", level=1)
    overview = data_dict.get("organization_overview") or ""
    if overview:
        for para_text in overview.split("\n\n"):
            if para_text.strip():
                add_paragraph(doc, para_text.strip())
    else:
        add_paragraph(doc, "Organization overview not yet defined.", italic=True)

    # Section 2: Personas
    add_heading(doc, "2. Personas", level=1)
    personas = data_dict.get("personas", [])
    if personas:
        for persona in personas:
            name = persona.get("name", "")
            code = persona.get("code", "")
            desc = persona.get("description", "") or ""
            add_labeled_paragraph(doc, f"{name} ({code})", f" \u2014 {desc}" if desc else "")
    else:
        add_paragraph(doc, "No personas defined.", italic=True)

    # Section 3: Domains
    add_page_break(doc)
    add_heading(doc, "3. Domain Inventory", level=1)
    domains = data_dict.get("domains", [])
    if domains:
        for domain in domains:
            name = domain.get("name", "")
            code = domain.get("code", "")
            desc = domain.get("description", "") or ""
            add_heading(doc, f"{name} ({code})", level=2)
            if desc:
                add_paragraph(doc, desc)

            # Sub-domains
            for sub in domain.get("sub_domains", []):
                sub_name = sub.get("name", "")
                sub_code = sub.get("code", "")
                sub_desc = sub.get("description", "") or ""
                add_heading(doc, f"{sub_name} ({sub_code})", level=3)
                if sub_desc:
                    add_paragraph(doc, sub_desc)

            # Processes in this domain
            procs = domain.get("processes", [])
            if procs:
                add_paragraph(doc, "Processes:", bold=True)
                for proc in procs:
                    p_name = proc.get("name", "")
                    p_code = proc.get("code", "")
                    p_desc = proc.get("description", "") or ""
                    add_labeled_paragraph(doc, f"{p_name} ({p_code})",
                                          f" \u2014 {p_desc}" if p_desc else "")
    else:
        add_paragraph(doc, "No domains defined.", italic=True)

    # Section 4: Services
    services = data_dict.get("services", [])
    if services:
        add_heading(doc, "4. Service Domains", level=1)
        for svc in services:
            name = svc.get("name", "")
            code = svc.get("code", "")
            desc = svc.get("description", "") or ""
            add_heading(doc, f"{name} ({code})", level=2)
            if desc:
                add_paragraph(doc, desc)

    # Write
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
