"""Section 3 — Field reference builder."""

import logging
from typing import Any

from tools.docgen.models import DocSection, DocTable
from tools.docgen.yaml_loader import get_display_name

logger = logging.getLogger(__name__)

TYPE_DISPLAY_MAP: dict[str, str] = {
    "varchar": "Text",
    "text": "Text (multi-line)",
    "wysiwyg": "Rich Text",
    "bool": "Boolean",
    "int": "Integer",
    "float": "Decimal",
    "date": "Date",
    "datetime": "Date/Time",
    "enum": "Enum",
    "multiEnum": "Multi-select",
    "url": "URL",
    "email": "Email",
    "phone": "Phone",
    "currency": "Currency",
}

ENUM_TYPES: set[str] = {"enum", "multiEnum"}
MAX_INLINE_OPTIONS = 6
MAX_DESCRIPTION_LEN = 200


def _c_prefix(name: str) -> str:
    """Apply the c-prefix to a field name."""
    return f"c{name[0].upper()}{name[1:]}"


def _get_display_type(yaml_type: str) -> str:
    """Map YAML field type to display type."""
    return TYPE_DISPLAY_MAP.get(yaml_type, yaml_type)


def _truncate(text: str, max_len: int = MAX_DESCRIPTION_LEN) -> str:
    """Truncate text to max_len, appending '...' if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _build_notes(field_data: dict[str, Any]) -> str:
    """Build the Notes column for a field."""
    notes_parts: list[str] = []
    field_type = field_data.get("type", "")

    if field_type in ENUM_TYPES:
        options = field_data.get("options", [])
        if options and len(options) <= MAX_INLINE_OPTIONS:
            notes_parts.append(f"Values: {' | '.join(str(o) for o in options)}")
        elif options:
            notes_parts.append("See Appendix A")

    if field_data.get("readOnly"):
        notes_parts.append("Read-only.")

    default = field_data.get("default")
    if default is not None and default != "":
        notes_parts.append(f"Default: {default}")

    min_val = field_data.get("min")
    max_val = field_data.get("max")
    if min_val is not None and max_val is not None:
        notes_parts.append(f"Range: {min_val}–{max_val}")
    elif min_val is not None:
        notes_parts.append(f"Min: {min_val}")
    elif max_val is not None:
        notes_parts.append(f"Max: {max_val}")

    max_len = field_data.get("maxLength")
    if max_len is not None:
        notes_parts.append(f"Max length: {max_len}")

    return "; ".join(notes_parts) if notes_parts else "\u2014"


def build_field_sections(
    entities: list[tuple[str, dict[str, Any]]],
) -> DocSection:
    """Build Section 3 — Fields.

    :param entities: Ordered list of (entity_name, entity_data).
    :returns: DocSection for fields.
    """
    section = DocSection(title="Fields", level=1)

    for name, data in entities:
        fields = data.get("fields", [])
        if not fields:
            continue

        display = get_display_name(name)
        title = f"{display}" if display == name else f"{display} ({name})"
        subsection = DocSection(title=title, level=2)

        headers = [
            "Field Name",
            "Internal Name",
            "Type",
            "Required",
            "Category",
            "Description",
            "Notes",
        ]

        # Group fields by category
        categorized: dict[str, list[dict]] = {}
        for f in fields:
            if not isinstance(f, dict):
                continue
            cat = f.get("category", "") or "General"
            categorized.setdefault(cat, []).append(f)

        rows: list[list[str]] = []
        # Ensure "General" appears first, then other categories in order
        cat_order: list[str] = []
        if "General" in categorized:
            cat_order.append("General")
        for cn in categorized:
            if cn != "General":
                cat_order.append(cn)
        for cat_name in cat_order:
            # Add category header row
            if len(categorized) > 1:
                rows.append([f"— {cat_name} —", "", "", "", "", "", ""])

            for f in categorized[cat_name]:
                field_name = f.get("name", "")
                label = f.get("label", field_name)
                internal = _c_prefix(field_name) if field_name else ""
                display_type = _get_display_type(f.get("type", ""))
                required = "Yes" if f.get("required") else "No"
                category = f.get("category", "") or "\u2014"

                desc = f.get("description", "")
                if desc:
                    desc = _truncate(desc.strip())
                else:
                    desc = "\u2014"

                notes = _build_notes(f)

                rows.append([
                    label,
                    f"`{internal}`",
                    display_type,
                    required,
                    category,
                    desc,
                    notes,
                ])

        table = DocTable(headers=headers, rows=rows)
        subsection.content.append(table)
        section.content.append(subsection)

    return section
