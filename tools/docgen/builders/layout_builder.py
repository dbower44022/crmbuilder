"""Section 4 — Layout reference builder."""

from typing import Any

from tools.docgen.models import DocParagraph, DocSection, DocTable
from tools.docgen.yaml_loader import get_display_name


def build_layout_sections(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Section 4 — Layouts.

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for layouts.
    """
    section = DocSection(title="Layouts", level=1)

    for name, data in entities:
        layout_data = data.get("layout", {})
        if not layout_data:
            continue

        display = get_display_name(name)
        title = f"{display}" if display == name else f"{display} ({name})"
        entity_section = DocSection(title=title, level=2)

        # Detail view
        detail = layout_data.get("detail", {})
        if detail:
            detail_section = DocSection(title="Detail View", level=3)
            panels = detail.get("panels", [])
            for i, panel in enumerate(panels, 1):
                if not isinstance(panel, dict):
                    continue
                label = panel.get("label", f"Panel {i}")
                tab_info = ""
                if panel.get("tabBreak"):
                    tab_label = panel.get("tabLabel", "")
                    tab_info = f" (Tab: {tab_label})"

                dlv = panel.get("dynamicLogicVisible")
                condition = ""
                if dlv:
                    attr = dlv.get("attribute", "")
                    val = dlv.get("value", "")
                    condition = f" \u2014 visible when {attr} = {val}"

                panel_header = f"Panel {i}: {label}{tab_info}{condition}"
                detail_section.content.append(
                    DocParagraph(text=f"**{panel_header}**")
                )

                # Panel description
                panel_desc = panel.get("description")
                if panel_desc:
                    detail_section.content.append(
                        DocParagraph(text=panel_desc.strip())
                    )

                # Tabs
                tabs = panel.get("tabs", [])
                if tabs:
                    for tab in tabs:
                        if not isinstance(tab, dict):
                            continue
                        tab_label = tab.get("label", "")
                        category = tab.get("category", "")
                        # Collect fields for this category
                        fields = data.get("fields", [])
                        cat_fields = [
                            f.get("label", f.get("name", ""))
                            for f in fields
                            if isinstance(f, dict)
                            and f.get("category") == category
                        ]
                        field_list = ", ".join(cat_fields) if cat_fields else "(no fields)"
                        detail_section.content.append(
                            DocParagraph(
                                text=f"  {tab_label}: {field_list}"
                            )
                        )

                # Explicit rows
                rows = panel.get("rows", [])
                if rows and not tabs:
                    field_names: list[str] = []
                    for row in rows:
                        if isinstance(row, list):
                            for cell in row:
                                if isinstance(cell, str):
                                    field_names.append(cell)
                    if field_names:
                        detail_section.content.append(
                            DocParagraph(
                                text=f"  Fields: {', '.join(field_names)}"
                            )
                        )

            entity_section.content.append(detail_section)

        # List view
        list_layout = layout_data.get("list", {})
        if list_layout:
            list_section = DocSection(title="List View", level=3)
            columns = list_layout.get("columns", [])
            if columns:
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

                table = DocTable(
                    headers=["#", "Field", "Width"],
                    rows=rows,
                )
                list_section.content.append(table)
            entity_section.content.append(list_section)

        section.content.append(entity_section)

    return section
