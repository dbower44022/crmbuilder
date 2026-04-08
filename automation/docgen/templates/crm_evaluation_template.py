"""CRM Evaluation Report template.

This is the ONLY document type permitted to include product names.
Generates a Word document with platform recommendation, evaluation decisions,
requirements coverage, and scale summary.
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_heading,
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
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    TWO_COL_WIDTHS,
    WD_ALIGN_PARAGRAPH,
)


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate a CRM Evaluation Report Word document.

    :param data_dict: Data dictionary from queries.crm_evaluation.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    set_header(section, client_name, "CRM Evaluation Report")
    set_footer(section, f"CRM Evaluation Report \u2014 {client_name}")

    if is_draft:
        set_draft_header(section)

    # Title
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, "CRM Evaluation Report", bold=True, size=SUBTITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=400)

    add_page_break(doc)

    # Section 1: Recommended Platform
    add_heading(doc, "1. Recommended Platform", level=1)
    platform = data_dict.get("crm_platform") or ""
    if platform:
        add_paragraph(doc, f"Recommended CRM platform: {platform}", bold=True)
    else:
        add_paragraph(doc, "No CRM platform recommendation specified.", italic=True)

    # Section 2: Scale Summary
    add_heading(doc, "2. Implementation Scale", level=1)
    scale = data_dict.get("scale_summary", {})
    add_meta_table(doc, [
        ("Entities", str(scale.get("entity_count", 0))),
        ("Fields", str(scale.get("field_count", 0))),
        ("Relationships", str(scale.get("relationship_count", 0))),
    ])

    # Section 3: Requirements Coverage
    add_heading(doc, "3. Requirements Coverage", level=1)
    req_summary = data_dict.get("requirements_summary", {})
    total = req_summary.get("total", 0)
    must = req_summary.get("must", 0)
    should = req_summary.get("should", 0)
    may = req_summary.get("may", 0)

    add_meta_table(doc, [
        ("Total Requirements", str(total)),
        ("Must", str(must)),
        ("Should", str(should)),
        ("May", str(may)),
    ])

    # Section 4: Evaluation Decisions
    add_page_break(doc)
    add_heading(doc, "4. Evaluation Decisions", level=1)
    decisions = data_dict.get("decisions", [])
    if decisions:
        add_two_col_table(
            doc, "ID", "Decision",
            [(d["identifier"], d.get("description", d.get("title", ""))) for d in decisions],
            TWO_COL_WIDTHS,
        )
    else:
        add_paragraph(doc, "No evaluation decisions recorded.", italic=True)

    # Section 5: Open Issues
    add_heading(doc, "5. Open Issues", level=1)
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
