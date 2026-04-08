"""Process Document template.

Generates a Process Document Word document matching the structure and
formatting of the reference implementation in generate-process-doc-template.js.

Document structure:
  1. Process Purpose and Trigger
  2. Personas Involved
  3. Process Workflow (with optional diagram)
  4. System Requirements
  5. Process Data (Pre-Existing)
  6. Data Collected (field tables per entity)
  7. Decisions Made
  8. Open Issues
"""

from __future__ import annotations

from pathlib import Path

from automation.docgen.templates.doc_helpers import (
    add_field_table,
    add_heading,
    add_labeled_paragraph,
    add_meta_table,
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
    BORDER_COLOR,
    CONTENT_WIDTH,
    GRAY_TEXT_RGB,
    META_COL_WIDTHS_PROCESS,
    SMALL_SIZE,
    SUBTITLE_SIZE,
    TITLE_COLOR_RGB,
    TITLE_SIZE,
    TWO_COL_WIDTHS,
    WD_ALIGN_PARAGRAPH,
)


def generate(data_dict: dict, output_path: str | Path, is_draft: bool = False) -> None:
    """Generate a Process Document Word document.

    :param data_dict: Data dictionary from queries.process_document.query().
    :param output_path: Path where the .docx file will be written.
    :param is_draft: If True, add draft indicators.
    """
    doc = create_document(is_draft)
    section = doc.sections[0]

    client_name = data_dict.get("client_name") or "Organization"
    process = data_dict.get("process") or {}
    domain = data_dict.get("domain") or {}
    process_name = process.get("name", "Unknown")
    process_code = process.get("code", "")
    domain_name = domain.get("name", "")
    domain_code = domain.get("code", "")

    # Human-readable-first: "Client Intake (MN-INTAKE)"
    process_label = f"{process_name} ({process_code})" if process_code else process_name

    set_header(section, client_name, process_label)
    set_footer(section, f"Process Document \u2014 {domain_name} Domain")

    if is_draft:
        set_draft_header(section)

    # Title page
    add_paragraph(doc, client_name, bold=True, size=TITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=60)
    add_paragraph(doc, process_label, bold=True, size=SUBTITLE_SIZE,
                  color=TITLE_COLOR_RGB, alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=200)
    add_paragraph(doc, "Process Document", alignment=WD_ALIGN_PARAGRAPH.CENTER,
                  space_after=400)

    # Metadata table
    add_meta_table(doc, [
        ("Domain", f"{domain_name} ({domain_code})" if domain_code else domain_name),
        ("Process Code", process_code),
    ], META_COL_WIDTHS_PROCESS)

    add_page_break(doc)

    # Section 1: Process Purpose and Trigger
    add_heading(doc, "1. Process Purpose and Trigger", level=1)
    desc = process.get("description", "")
    if desc:
        add_paragraph(doc, desc)
    triggers = process.get("triggers", "")
    if triggers:
        add_labeled_paragraph(doc, "Trigger: ", triggers)
    completion = process.get("completion_criteria", "")
    if completion:
        add_labeled_paragraph(doc, "Completion: ", completion)

    # Section 2: Personas Involved
    add_heading(doc, "2. Personas Involved", level=1)
    personas = data_dict.get("personas", [])
    if personas:
        for persona in personas:
            name = persona.get("name", "")
            code = persona.get("code", "")
            desc_text = persona.get("description", "") or ""
            role = persona.get("role", "")
            add_labeled_paragraph(doc, f"{name} ({code})",
                                  f" [{role}] \u2014 {desc_text}" if desc_text else f" [{role}]")
    else:
        add_paragraph(doc, "No personas defined.", italic=True)

    # Section 3: Process Workflow
    add_heading(doc, "3. Process Workflow", level=1)
    steps = data_dict.get("steps", [])
    if steps:
        for i, step in enumerate(steps, 1):
            step_desc = step.get("description", step.get("name", ""))
            performer = step.get("performer_name", "")
            text = f"{step_desc}"
            if performer:
                text = f"[{performer}] {text}"
            add_paragraph(doc, f"{i}. {text}")
    else:
        add_paragraph(doc, "No workflow steps defined.", italic=True)

    # Workflow diagram
    diagram_path = data_dict.get("diagram_path")
    _add_workflow_diagram(doc, diagram_path)

    # Section 4: System Requirements
    add_heading(doc, "4. System Requirements", level=1)
    requirements = data_dict.get("requirements", [])
    if requirements:
        add_requirement_table(doc, requirements)
    else:
        add_paragraph(doc, "No requirements defined.", italic=True)

    # Section 5: Process Data
    add_heading(doc, "5. Process Data", level=1)
    add_paragraph(doc, "Data references for this process are detailed below.")

    # Section 6: Data Collected (field tables per entity)
    add_heading(doc, "6. Data Collected", level=1)
    data_ref = data_dict.get("data_reference", [])
    if data_ref:
        for entity_ref in data_ref:
            entity_name = entity_ref.get("entity_name", "")
            add_heading(doc, f"Entity: {entity_name}", level=2)

            fields = entity_ref.get("fields", [])
            if fields:
                table_fields = []
                for f in fields:
                    table_fields.append({
                        "label": f.get("label", f.get("name", "")),
                        "field_type": f.get("field_type", ""),
                        "is_required": False,
                        "values": "\u2014",
                        "default_value": None,
                        "identifier": f.get("name", ""),
                        "description": f.get("description") or f.get("usage", ""),
                    })
                add_field_table(doc, table_fields)
            add_paragraph(doc, "")
    else:
        add_paragraph(doc, "No data references defined.", italic=True)

    # Section 7: Decisions Made
    decisions = data_dict.get("decisions", [])
    if decisions:
        add_heading(doc, "7. Decisions Made", level=1)
        add_two_col_table(
            doc, "ID", "Decision",
            [(d["identifier"], d.get("description", d.get("title", ""))) for d in decisions],
            TWO_COL_WIDTHS,
        )

    # Section 8: Open Issues
    issues = data_dict.get("open_issues", [])
    if issues:
        add_heading(doc, "8. Open Issues", level=1)
        add_two_col_table(
            doc, "ID", "Issue",
            [(i["identifier"], i.get("description", i.get("title", ""))) for i in issues],
            TWO_COL_WIDTHS,
        )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))


def _add_workflow_diagram(doc, diagram_path: str | Path | None):
    """Embed a workflow diagram or insert a placeholder."""
    add_paragraph(doc, "Process Workflow Diagram", bold=True, space_after=60)

    if diagram_path and Path(diagram_path).exists():
        doc.add_picture(str(diagram_path), width=CONTENT_WIDTH)
    else:
        # Dashed placeholder
        table = doc.add_table(rows=1, cols=1)
        table.autofit = False
        cell = table.rows[0].cells[0]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(
            "Workflow diagram to be inserted. Export from draw.io as PNG."
        )
        run.font.name = "Arial"
        run.font.size = SMALL_SIZE
        run.font.color.rgb = GRAY_TEXT_RGB
        run.font.italic = True

        # Dashed borders
        from automation.docgen.templates.doc_helpers import (
            _set_cell_border,
            _set_cell_margins,
        )
        _set_cell_border(cell,
                         top={"val": "dashed", "sz": "4", "color": BORDER_COLOR},
                         bottom={"val": "dashed", "sz": "4", "color": BORDER_COLOR},
                         left={"val": "dashed", "sz": "4", "color": BORDER_COLOR},
                         right={"val": "dashed", "sz": "4", "color": BORDER_COLOR})
        _set_cell_margins(cell, 200, 200, 200, 200)
