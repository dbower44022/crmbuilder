"""Parse CBM-Entity-Inventory.docx → BusinessObjects + Entity stubs.

Extracts the entity-to-business-object mapping table.
"""

from __future__ import annotations

import re
from pathlib import Path

from automation.cbm_import.docx_parser import (
    extract_paragraphs,
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
    extract_paragraphs(doc)  # Available for future paragraph-based parsing
    tables = extract_tables(doc)

    data: dict = {
        "business_objects": [],
        "entities": [],
    }

    # Entity inventory is primarily in tables
    entities_seen: set[str] = set()
    for table in tables:
        for row in table[1:]:  # Skip header
            if len(row) < 2:
                continue

            # Try to identify entity name and business concept
            bo_name = row[0].strip()
            entity_name = ""
            entity_type = "Base"
            is_native = False

            if not bo_name or bo_name.lower() in ("business concept", "concept", ""):
                continue

            # Look for entity reference in other columns
            for _col_idx, cell in enumerate(row[1:], start=1):
                cell_text = cell.strip()
                if not cell_text or cell_text.lower() in ("", "—", "-", "n/a", "tbd"):
                    continue

                cell_lower = cell_text.lower()

                # Type/Native detection (usually in later columns)
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
                    # Also extract type from "Native (Person)" format
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

    # If no tables found, try to parse from paragraphs
    if not data["entities"]:
        report.add_warning("No entity inventory tables found in document")

    return data, report
