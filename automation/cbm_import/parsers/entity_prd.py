"""Parse Entity PRD .docx → Entity + Field + FieldOption + Relationship + Layout records.

Handles the standard CBM Entity PRD format with header table, native fields,
custom fields organized by functional group, relationships, and layouts.
"""

from __future__ import annotations

import re
from pathlib import Path

from automation.cbm_import.docx_parser import (
    extract_paragraphs,
    extract_tables,
    get_first_table,
    load_document,
)
from automation.cbm_import.parser_logic import (
    extract_enum_values,
    find_section_by_heading,
    parse_field_table,
    parse_header_table,
)
from automation.cbm_import.reporter import ImportReport

# Map CBM field type names to schema field_type values
_FIELD_TYPE_MAP = {
    "varchar": "varchar",
    "text": "text",
    "wysiwyg": "wysiwyg",
    "bool": "bool",
    "boolean": "bool",
    "int": "int",
    "integer": "int",
    "float": "float",
    "date": "date",
    "datetime": "datetime",
    "currency": "currency",
    "url": "url",
    "email": "email",
    "phone": "phone",
    "enum": "enum",
    "multienum": "multiEnum",
    "multi-enum": "multiEnum",
    "link": "varchar",  # Link fields stored as varchar reference
}


def parse(path: str | Path) -> tuple[dict, ImportReport]:
    """Parse an Entity PRD document.

    :param path: Path to the Entity PRD .docx file.
    :returns: Tuple of (parsed_data dict, ImportReport).
    """
    report = ImportReport()
    doc = load_document(path)
    paragraphs = extract_paragraphs(doc)
    tables = extract_tables(doc)
    source_file = Path(path).name

    data: dict = {
        "entity": {},
        "fields": [],
        "field_options": [],
        "relationships": [],
    }

    # Header table — first table in document
    header_table = get_first_table(doc)
    if header_table:
        header = parse_header_table(header_table)
        entity_name = header.get("Entity", header.get("Entity Name", ""))
        data["entity"] = {
            "name": entity_name,
            "entity_type": header.get("Entity Type", "Base"),
            "is_native": "native" in header.get("Native/Custom", "").lower(),
            "singular_label": header.get("Singular Label", entity_name),
            "plural_label": header.get("Plural Label", ""),
            "description": header.get("Description", ""),
        }
    else:
        # Try to extract entity name from filename
        name = Path(path).stem.replace("-Entity-PRD", "").replace("-", " ")
        data["entity"] = {
            "name": name,
            "entity_type": "Base",
            "is_native": False,
        }
        report.add_warning(f"No header table found in {source_file}")

    # Fields — scan all tables for field tables
    for table_idx, table in enumerate(tables):
        if table_idx == 0 and header_table:
            continue  # Skip header table

        fields = parse_field_table(table, source_file)
        for field in fields:
            field_name = field.get("field_name", "")
            if not field_name:
                continue

            field_type_raw = field.get("field_type", "varchar").lower().strip()
            field_type = _FIELD_TYPE_MAP.get(field_type_raw, "varchar")

            required = field.get("required", "").lower() in ("yes", "true", "y")

            field_record = {
                "name": field_name,
                "label": _to_label(field_name),
                "field_type": field_type,
                "is_required": required,
                "default_value": field.get("default_value"),
                "description": field.get("description", ""),
                "identifier": field.get("identifier", ""),
            }

            # Clean up default value
            if field_record["default_value"] in ("—", "-", "N/A", "", None):
                field_record["default_value"] = None

            data["fields"].append(field_record)
            report.record_parsed("Field", 1)

            # Extract enum options
            values_str = field.get("values", "")
            if field_type in ("enum", "multiEnum") and values_str:
                values = extract_enum_values(values_str)
                for sort_order, val in enumerate(values, 1):
                    data["field_options"].append({
                        "field_name": field_name,
                        "value": val,
                        "label": val,
                        "sort_order": sort_order,
                    })
                    report.record_parsed("FieldOption", 1)

    # Relationships — search for relationship section
    rel_idx = find_section_by_heading(paragraphs, r"relationship")
    if rel_idx is not None:
        rels = _extract_relationships(paragraphs, tables, rel_idx, source_file, report)
        data["relationships"] = rels

    return data, report


def _extract_relationships(
    paragraphs: list[str],
    tables: list[list[list[str]]],
    start_idx: int,
    source_file: str,
    report: ImportReport,
) -> list[dict]:
    """Extract relationship definitions from the Relationships section."""
    relationships: list[dict] = []

    # Look for relationship tables near the section heading
    for table in tables:
        for row in table:
            row_text = " ".join(row).lower()
            if any(kw in row_text for kw in ("onetomany", "manytoone", "manytomany",
                                               "one-to-many", "many-to-one", "many-to-many")):
                # This table contains relationships
                for data_row in table[1:]:  # Skip header
                    if len(data_row) < 3:
                        continue
                    name = data_row[0].strip()
                    if not name or name.lower() in ("name", "relationship name", ""):
                        continue

                    rel = {
                        "name": name,
                        "link_type": "oneToMany",  # Default
                        "entity_foreign": "",
                    }
                    for cell in data_row[1:]:
                        cell_lower = cell.strip().lower()
                        if cell_lower in ("onetomany", "one-to-many"):
                            rel["link_type"] = "oneToMany"
                        elif cell_lower in ("manytoone", "many-to-one"):
                            rel["link_type"] = "manyToOne"
                        elif cell_lower in ("manytomany", "many-to-many"):
                            rel["link_type"] = "manyToMany"
                        elif cell.strip() and not rel["entity_foreign"]:
                            rel["entity_foreign"] = cell.strip()

                    relationships.append(rel)
                    report.record_parsed("Relationship", 1)
                break

    return relationships


def _to_label(field_name: str) -> str:
    """Convert camelCase field name to a human-readable label."""
    # Insert spaces before uppercase letters
    label = re.sub(r"([a-z])([A-Z])", r"\1 \2", field_name)
    # Capitalize first letter
    return label[0].upper() + label[1:] if label else label
