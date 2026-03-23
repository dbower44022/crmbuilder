"""Appendices A and B builder."""

from typing import Any

from tools.docgen.models import DocParagraph, DocSection, DocTable
from tools.docgen.yaml_loader import get_display_name

ENUM_TYPES: set[str] = {"enum", "multiEnum"}
MAX_INLINE_OPTIONS = 6


def build_appendix_a(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Appendix A — Enum Value Reference.

    Lists all enum/multiEnum fields with more than 6 options.

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for Appendix A.
    """
    section = DocSection(title="Appendix A \u2014 Enum Value Reference", level=1)

    for name, data in entities:
        fields = data.get("fields", [])
        enum_fields = [
            f
            for f in fields
            if isinstance(f, dict)
            and f.get("type") in ENUM_TYPES
            and len(f.get("options", [])) > MAX_INLINE_OPTIONS
        ]
        if not enum_fields:
            continue

        display = get_display_name(name)
        title = f"{display}" if display == name else f"{display} ({name})"
        entity_section = DocSection(title=title, level=2)

        for f in enum_fields:
            label = f.get("label", f.get("name", ""))
            field_section = DocSection(title=label, level=3)
            options = f.get("options", [])
            for opt in options:
                field_section.content.append(
                    DocParagraph(text=f"\u2022 {opt}")
                )
            entity_section.content.append(field_section)

        section.content.append(entity_section)

    return section


def build_appendix_b(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Appendix B — Deployment Status.

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for Appendix B.
    """
    section = DocSection(
        title="Appendix B \u2014 Deployment Status", level=1
    )

    headers = ["Entity", "Fields", "Layout", "Relationships", "Status"]
    rows: list[list[str]] = []

    for name, data in entities:
        display = get_display_name(name)
        fields = data.get("fields", [])
        layout = data.get("layout", {})

        fields_status = (
            f"\u2713 Defined ({len(fields)})" if fields else "Planned"
        )
        layout_status = "\u2713 Defined" if layout else "Planned"
        rel_status = "Planned"

        if fields and layout:
            status = "Ready to deploy"
        elif fields:
            status = "Partially defined"
        else:
            status = "Planned"

        rows.append([display, fields_status, layout_status, rel_status, status])

    table = DocTable(headers=headers, rows=rows)
    section.content.append(table)

    return section
