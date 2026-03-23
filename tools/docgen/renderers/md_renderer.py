"""Markdown renderer for the documentation generator."""

from tools.docgen.models import DocDocument, DocParagraph, DocSection, DocTable


def render(doc: DocDocument) -> str:
    """Render a DocDocument to a Markdown string.

    :param doc: Document to render.
    :returns: Markdown string.
    """
    lines: list[str] = []

    # Title page
    lines.append(f"# {doc.title}")
    lines.append("")
    lines.append(f"## {doc.subtitle}")
    lines.append("")
    lines.append("Generated from YAML program files")
    lines.append(f"  Version: {doc.version}")
    lines.append(f"  Generated: {doc.timestamp}")
    lines.append("")
    lines.append(
        "This document defines the EspoCRM configuration required to support "
        "the requirements specified in the CBM PRD documents. It is generated "
        "automatically from the YAML program files and must not be edited manually."
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    # Sections
    for section in doc.sections:
        lines.extend(_render_section(section))

    return "\n".join(lines)


def _render_section(section: DocSection) -> list[str]:
    """Render a section recursively.

    :param section: Section to render.
    :returns: List of Markdown lines.
    """
    lines: list[str] = []
    prefix = "#" * min(section.level, 4)
    lines.append(f"{prefix} {section.title}")
    lines.append("")

    for item in section.content:
        if isinstance(item, DocSection):
            lines.extend(_render_section(item))
        elif isinstance(item, DocTable):
            lines.extend(_render_table(item))
        elif isinstance(item, DocParagraph):
            lines.extend(_render_paragraph(item))

    return lines


def _render_table(table: DocTable) -> list[str]:
    """Render a table as a GitHub pipe table.

    :param table: Table to render.
    :returns: List of Markdown lines.
    """
    lines: list[str] = []

    if table.caption:
        lines.append(f"*{table.caption}*")
        lines.append("")

    # Header
    lines.append("| " + " | ".join(table.headers) + " |")
    lines.append("| " + " | ".join("---" for _ in table.headers) + " |")

    # Rows
    for row in table.rows:
        # Pad row to match header count
        padded = row + [""] * (len(table.headers) - len(row))
        # Escape pipes in cell content
        cells = [c.replace("|", "\\|") for c in padded]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    return lines


def _render_paragraph(para: DocParagraph) -> list[str]:
    """Render a paragraph.

    :param para: Paragraph to render.
    :returns: List of Markdown lines.
    """
    lines: list[str] = []

    if para.style == "note":
        lines.append(f"> **Note:** {para.text}")
    elif para.style == "status":
        lines.append(f"> \u26a0\ufe0f **{para.text}**")
    elif para.style == "code":
        lines.append(f"`{para.text}`")
    else:
        lines.append(para.text)

    lines.append("")
    return lines
