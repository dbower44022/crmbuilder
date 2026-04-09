"""Parse CBM-Entity-Inventory.docx → BusinessObjects + Entity stubs.

Extracts the entity-to-business-object mapping table. Identifies the
real inventory table by header content and ignores metadata/detail tables.
"""

from __future__ import annotations

import re
from pathlib import Path

from automation.cbm_import.docx_parser import (
    extract_tables,
    load_document,
)
from automation.cbm_import.reporter import ImportReport


def parse(path: str | Path) -> tuple[dict, ImportReport]:
    """Parse the Entity Inventory document.

    :param path: Path to CBM-Entity-Inventory.docx.
    :returns: Tuple of (parsed_data dict, ImportReport).
    """
    report = ImportReport()
    doc = load_document(path)
    tables = extract_tables(doc)

    data: dict = {
        "business_objects": [],
        "entities": [],
    }

    # Find the real inventory table by header content
    inv_table = _find_inventory_table(tables)
    if inv_table is None:
        report.add_warning("No entity inventory table found in document")
        return data, report

    # Parse only the inventory table
    entities_seen: set[str] = set()
    for row in inv_table[1:]:  # Skip header
        if len(row) < 2:
            continue

        bo_name = row[0].strip()
        entity_name = ""
        entity_type = "Base"
        is_native = False

        if not bo_name or bo_name.lower() in ("business concept", "concept", "prd entity name", ""):
            continue

        # Look for entity reference in other columns
        for _col_idx, cell in enumerate(row[1:], start=1):
            cell_text = cell.strip()
            if not cell_text or cell_text.lower() in ("", "—", "-", "n/a", "tbd"):
                continue

            cell_lower = cell_text.lower()

            # Type/Native detection
            if cell_lower in ("person", "company", "base", "event"):
                if cell_lower == "person":
                    entity_type = "Person"
                elif cell_lower == "company":
                    entity_type = "Company"
                elif cell_lower == "event":
                    entity_type = "Event"
                continue
            if "native" in cell_lower:
                is_native = True
                type_match = re.search(r"\((\w+)\)", cell_text)
                if type_match:
                    t = type_match.group(1)
                    if t in ("Person", "Company", "Event"):
                        entity_type = t
                continue
            if cell_lower == "custom":
                is_native = False
                continue

            # Entity name (first non-type, non-native column)
            if not entity_name and re.match(r"^[A-Z][a-z]", cell_text):
                entity_name = cell_text.split("(")[0].strip()

        data["business_objects"].append({
            "name": bo_name,
            "entity_name": entity_name,
            "status": "classified" if entity_name else "unclassified",
            "resolution": "entity" if entity_name else None,
        })
        report.record_parsed("BusinessObject", 1)

        if entity_name and entity_name not in entities_seen:
            entities_seen.add(entity_name)
            data["entities"].append({
                "name": entity_name,
                "code": entity_name.upper(),
                "entity_type": entity_type,
                "is_native": is_native,
            })
            report.record_parsed("Entity", 1)

    return data, report


def _find_inventory_table(tables: list[list[list[str]]]) -> list[list[str]] | None:
    """Find the real inventory table among all document tables.

    The inventory table has a header row containing both an "entity"-related
    column and a "native"-related column, with at least 5 columns.
    """
    for table in tables:
        if not table or len(table) < 2:
            continue
        header = [c.strip().lower() for c in table[0]]
        has_entity_col = any("entity" in h for h in header)
        has_native_col = any("native" in h or "custom" in h for h in header)
        if has_entity_col and has_native_col and len(header) >= 4:
            return table
    return None
