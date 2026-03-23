"""Section 5 — Views (List Views) builder."""

from typing import Any

from tools.docgen.models import DocSection, DocTable
from tools.docgen.yaml_loader import get_display_name


def build_view_sections(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Section 5 — Views (List Views).

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for views.
    """
    section = DocSection(title="Views (List Views)", level=1)
    section.content.append(
        __import__("tools.docgen.models", fromlist=["DocParagraph"]).DocParagraph(
            text="Status: Defined in YAML \u2014 Implemented",
            style="status",
        )
    )

    for name, data in entities:
        layout = data.get("layout", {})
        list_layout = layout.get("list", {})
        if not list_layout:
            continue

        display = get_display_name(name)
        title = f"{display}" if display == name else f"{display} ({name})"
        subsection = DocSection(title=title, level=2)

        columns = list_layout.get("columns", [])
        rows: list[list[str]] = []
        for i, col in enumerate(columns, 1):
            if isinstance(col, dict):
                field_name = col.get("field", "")
                width = col.get("width", "")
                width_str = f"{width}%" if width else "Auto"
            elif isinstance(col, str):
                field_name = col
                width_str = "Auto"
            else:
                continue
            rows.append([str(i), field_name, width_str])

        if rows:
            table = DocTable(
                headers=["#", "Field", "Width"],
                rows=rows,
            )
            subsection.content.append(table)
        section.content.append(subsection)

    return section
