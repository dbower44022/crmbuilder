"""Domain PRD document template.

Generates a Domain PRD Word document with reconciliation narrative,
consolidated personas, process summaries, conflict resolutions,
and consolidated data reference.
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
    add_requirement_table,
    add_two_col_table,
    create_document,
    set_draft_header,
    set_footer,
    set_header,
)
from automation.docgen.templates.formatting import (
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    TWO_COL_WIDTHS,
    WD_ALIGN_PARAGRAPH,
)


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate a Domain PRD Word document.

    :param data_dict: Data dictionary from queries.domain_prd.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    domain = data_dict.get("domain") or {}
    domain_name = domain.get("name", "Unknown")
    domain_code = domain.get("code", "")

    set_header(section, client_name, f"Domain PRD \u2014 {domain_name}")
    set_footer(section, f"Domain PRD \u2014 {domain_name} Domain")

    if is_draft:
        set_draft_header(section)

    # Title
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, f"Domain PRD \u2014 {domain_name} ({domain_code})",
                  bold=True, size=SUBTITLE_SIZE, color=TITLE_COLOR_RGB,
                  alignment=WD_ALIGN_PARAGRAPH.CENTER, space_after=400)

    add_page_break(doc)

    # Section 1: Reconciliation Narrative
    add_heading(doc, "1. Domain Reconciliation", level=1)
    recon = data_dict.get("reconciliation_text") or ""
    if recon:
        for para in recon.split("\n\n"):
            if para.strip():
                add_paragraph(doc, para.strip())
    else:
        add_paragraph(doc, "Reconciliation narrative not yet defined.", italic=True)

    # Section 2: Consolidated Personas
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

    # Section 3: Process Summaries
    add_heading(doc, "3. Processes", level=1)
    processes = data_dict.get("processes", [])
    if processes:
        for proc in processes:
            name = proc.get("name", "")
            code = proc.get("code", "")
            add_heading(doc, f"{name} ({code})", level=2)

            desc = proc.get("description", "")
            if desc:
                add_paragraph(doc, desc)

            reqs = proc.get("requirements", [])
            if reqs:
                add_paragraph(doc, "Requirements:", bold=True)
                add_requirement_table(doc, reqs)
    else:
        add_paragraph(doc, "No processes defined in this domain.", italic=True)

    # Section 4: Consolidated Data Reference
    add_page_break(doc)
    add_heading(doc, "4. Data Reference", level=1)
    data_ref = data_dict.get("data_reference", [])
    if data_ref:
        for entity in data_ref:
            entity_name = entity.get("entity_name", "")
            add_heading(doc, f"Entity: {entity_name}", level=2)

            fields = entity.get("fields", [])
            if fields:
                widths = [2200, 2200, 1500, 3460]
                table = doc.add_table(rows=1, cols=4)
                table.autofit = False
                add_header_row(table, ["Field", "Label", "Type", "Usage"], widths)

                for idx, f in enumerate(fields):
                    add_data_row(
                        table,
                        [f.get("name", ""), f.get("label", ""),
                         f.get("field_type", ""), f.get("usage", "")],
                        widths,
                        shaded=idx % 2 == 1,
                    )
    else:
        add_paragraph(doc, "No data references defined.", italic=True)

    # Section 5: Decisions
    add_heading(doc, "5. Decisions", level=1)
    decisions = data_dict.get("decisions", [])
    if decisions:
        add_two_col_table(
            doc, "ID", "Decision",
            [(d["identifier"], d.get("description", d.get("title", ""))) for d in decisions],
            TWO_COL_WIDTHS,
        )
    else:
        add_paragraph(doc, "No decisions recorded.", italic=True)

    # Section 6: Open Issues
    add_heading(doc, "6. Open Issues", level=1)
    issues = data_dict.get("open_issues", [])
    if issues:
        add_two_col_table(
            doc, "ID", "Issue",
            [(i["identifier"], i.get("description", i.get("title", ""))) for i in issues],
            TWO_COL_WIDTHS,
        )
    else:
        add_paragraph(doc, "No open issues.", italic=True)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
