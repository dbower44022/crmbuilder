"""Parse an Entity Inventory .docx into a Path B envelope JSON string.

Adapter that turns a Word Entity Inventory document into a Path B envelope
suitable for processing by the business_object_discovery mapper.

Replaces the Path A parser at automation.cbm_import.parsers.entity_inventory.
Fixes Bug 7 (domain assignment never extracted) by parsing Owning Domain
from entity detail cards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from docx import Document

from automation.importer.parsers import EntityInventoryParseError, ParseReport

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# "Name (CODE)" pattern for domains
_NAME_CODE_RE = re.compile(r"^(.+?)\s*\(([A-Z][A-Z0-9-]*)\)\s*$")

# Entity name prefix before parenthetical qualifier
_ENTITY_NAME_PREFIX_RE = re.compile(r"^(.+?)(?:\s*\(.+\))?\s*$")

# Placeholder values to treat as empty
_EMPTY_VALUES = frozenset({"", "—", "–", "-", "n/a", "N/A", "tbd", "TBD"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _table_header(table: Any) -> list[str]:
    """Return lowercased, stripped header row cells."""
    if not table.rows:
        return []
    return [cell.text.strip().lower() for cell in table.rows[0].cells]


def _table_rows(table: Any) -> list[list[str]]:
    """Return data rows (excluding header) as lists of stripped cell strings."""
    rows = []
    for i in range(1, len(table.rows)):
        rows.append([cell.text.strip() for cell in table.rows[i].cells])
    return rows


def _is_empty(value: str) -> bool:
    """Check if a cell value is effectively empty."""
    return value.strip() in _EMPTY_VALUES


# ---------------------------------------------------------------------------
# Table classification
# ---------------------------------------------------------------------------


def _classify_tables(doc: Document) -> dict[str, Any]:
    """Classify all document tables by content."""
    result: dict[str, Any] = {
        "header": None,
        "entity_map": None,
        "detail_cards": [],
        "open_issues": None,
    }

    for table in doc.tables:
        header = _table_header(table)
        ncols = len(header)

        # Header table: 2-col, any cell contains "document type"
        if ncols == 2 and result["header"] is None:
            if any("document type" in h for h in header):
                result["header"] = table
                continue

        # Entity Map: ≥7 cols, header contains "prd entity name"
        if ncols >= 7 and result["entity_map"] is None:
            if any("prd entity name" in h for h in header):
                result["entity_map"] = table
                continue

        # Detail Cards: 2-col, row 0 col 0 starts with "entity type"
        if ncols == 2 and len(table.rows) >= 2:
            first_cell = table.rows[0].cells[0].text.strip().lower()
            if first_cell.startswith("entity type"):
                result["detail_cards"].append(table)
                continue

        # Cross-Domain Matrix: ≥6 cols, header contains "domain count" — skip
        if ncols >= 6 and any("domain count" in h for h in header):
            continue

        # Open Issues: 3 cols, header contains "id" and "issue"
        if ncols == 3 and result["open_issues"] is None:
            if "id" in header and any("issue" in h for h in header):
                result["open_issues"] = table
                continue

    return result


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_header_table(
    table: Any, report: ParseReport,
) -> dict[str, str]:
    """Extract source metadata from the header key/value table."""
    metadata: dict[str, str] = {}
    key_map = {
        "document type": "document_type",
        "implementation": "implementation",
        "target platform": "target_platform",
        "version": "version",
        "status": "status",
        "last updated": "last_updated",
        "source documents": "source_documents",
    }

    for row in table.rows:
        key = row.cells[0].text.strip().lower()
        value = row.cells[1].text.strip()
        mapped = key_map.get(key)
        if mapped:
            metadata[mapped] = value

    expected = {"version", "status"}
    for field in expected:
        if field not in metadata:
            report.warn(
                "missing_header_field",
                "Header table",
                f"Missing expected row: {field}",
            )

    return metadata


def _parse_entity_map(
    table: Any, report: ParseReport,
) -> list[dict[str, Any]]:
    """Parse the 7-column Entity Map table into business_objects entries."""
    business_objects: list[dict[str, Any]] = []

    skip_values = {"prd entity name", "business concept", "concept", ""}

    for row_data in _table_rows(table):
        if len(row_data) < 7:
            continue

        bo_name = row_data[0].strip()
        if bo_name.lower() in skip_values:
            continue

        crm_entity = row_data[1].strip()
        native_custom = row_data[2].strip().lower()
        entity_type = row_data[3].strip()
        discriminator = row_data[4].strip()
        disc_value = row_data[5].strip()
        domains_raw = row_data[6].strip()

        bo: dict[str, Any] = {
            "name": bo_name,
            "classification": "entity",
        }

        # CRM Entity
        if crm_entity:
            bo["entity_name"] = crm_entity
            bo["status"] = "classified"
        else:
            bo["status"] = "unclassified"
            report.warn(
                "unclassified_bo",
                f"BO {bo_name}",
                "No CRM Entity mapped — marked as unclassified",
            )

        # Native / Custom
        if "native" in native_custom:
            bo["is_native"] = True
        else:
            bo["is_native"] = False

        # Entity Type
        if entity_type and not _is_empty(entity_type):
            bo["entity_type"] = entity_type
        else:
            bo["entity_type"] = "Base"

        # Discriminator → description
        desc_parts: list[str] = []
        if not _is_empty(discriminator) and not _is_empty(disc_value):
            desc_parts.append(f"Discriminator: {discriminator} = {disc_value}")
        bo["description"] = "; ".join(desc_parts) if desc_parts else ""

        # Domain(s)
        if domains_raw and not _is_empty(domains_raw):
            # Split on comma, strip parens/annotations, extract codes
            raw_parts = [d.strip() for d in domains_raw.split(",")]
            codes: list[str] = []
            for part in raw_parts:
                # Handle "All" or "All (Notes Svc)" → skip or treat as-is
                if part.lower().startswith("all"):
                    codes.append("All")
                    continue
                # Handle "MN, CR (Survey Svc)" → extract just the code
                clean = re.sub(r"\s*\(.*\)\s*$", "", part).strip()
                if clean:
                    codes.append(clean)
            bo["source_domains"] = codes
        else:
            bo["source_domains"] = []

        business_objects.append(bo)
        report.parsed_counts["business_objects"] = (
            report.parsed_counts.get("business_objects", 0) + 1
        )

    return business_objects


def _parse_detail_cards(
    cards: list[Any],
    business_objects: list[dict[str, Any]],
    report: ParseReport,
) -> None:
    """Enrich business_objects in-place from entity detail cards."""
    # Build index: CRM entity name (lower) → list of BO dicts
    entity_bo_map: dict[str, list[dict[str, Any]]] = {}
    for bo in business_objects:
        ename = bo.get("entity_name", "")
        if ename:
            entity_bo_map.setdefault(ename.lower(), []).append(bo)

    for card in cards:
        if len(card.rows) < 2:
            continue

        # Extract entity name from singular label row
        singular_label = ""
        plural_label = ""
        owning_domain_raw = ""
        activity_stream = ""

        for row in card.rows:
            key = row.cells[0].text.strip().lower()
            value = row.cells[1].text.strip()

            if "display label" in key and "singular" in key:
                singular_label = value
            elif "display label" in key and "plural" in key:
                plural_label = value
            elif "owning domain" in key:
                owning_domain_raw = value
            elif "activity stream" in key:
                activity_stream = value

        # Match by singular label (which equals CRM Entity name)
        match_key = singular_label.lower()
        matched_bos = entity_bo_map.get(match_key, [])

        if not matched_bos:
            report.warn(
                "unmatched_detail_card",
                f"Detail card {singular_label}",
                f"No business objects match entity name '{singular_label}'",
            )
            report.parsed_counts["detail_cards"] = (
                report.parsed_counts.get("detail_cards", 0) + 1
            )
            continue

        # Parse Owning Domain
        owning_domain_code: str | None = None
        if owning_domain_raw:
            m = _NAME_CODE_RE.match(owning_domain_raw)
            if m:
                owning_domain_code = m.group(2)
            else:
                report.warn(
                    "owning_domain_parse_failure",
                    f"Detail card {singular_label}",
                    f"Could not parse Owning Domain: {owning_domain_raw!r}",
                )

        # Apply enrichment to all matching BOs
        for bo in matched_bos:
            bo["singular_label"] = singular_label
            bo["plural_label"] = plural_label

            # Owning Domain → source_domains[0]
            if owning_domain_code:
                existing = bo.get("source_domains", [])
                # Check if owning domain code is in existing domains
                if owning_domain_code not in existing:
                    report.warn(
                        "owning_domain_not_in_table1",
                        f"Detail card {singular_label}",
                        f"Owning Domain code '{owning_domain_code}' not in "
                        f"Table 1 Domain(s): {existing}",
                    )
                # Insert at front, dedup
                new_domains = [owning_domain_code] + [
                    d for d in existing if d != owning_domain_code
                ]
                bo["source_domains"] = new_domains

            # Activity Stream → append to description
            if activity_stream:
                existing_desc = bo.get("description", "")
                activity_note = f"Activity Stream: {activity_stream}"
                if existing_desc:
                    bo["description"] = f"{existing_desc}; {activity_note}"
                else:
                    bo["description"] = activity_note

        report.parsed_counts["detail_cards"] = (
            report.parsed_counts.get("detail_cards", 0) + 1
        )


def _parse_open_issues(
    table: Any, report: ParseReport,
) -> list[dict[str, str]]:
    """Parse the 3-column Open Issues table."""
    issues: list[dict[str, str]] = []
    skip_values = {"id", ""}

    for row_data in _table_rows(table):
        if len(row_data) < 3:
            continue
        identifier = row_data[0].strip()
        if identifier.lower() in skip_values:
            continue

        issues.append({
            "identifier": identifier,
            "description": row_data[1].strip(),
            "resolution_path": row_data[2].strip(),
            "status": "open",
        })
        report.parsed_counts["open_issues"] = (
            report.parsed_counts.get("open_issues", 0) + 1
        )

    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(
    path: str | Path,
    work_item: dict,
    session_type: str = "initial",
) -> tuple[str, ParseReport]:
    """Parse an Entity Inventory .docx into a Path B envelope JSON string.

    :param path: Path to Entity Inventory .docx file.
    :param work_item: Must have item_type == 'business_object_discovery'.
    :param session_type: Session type for envelope metadata.
    :returns: Tuple of (JSON envelope string, ParseReport).
    :raises ValueError: If work_item['item_type'] != 'business_object_discovery'.
    :raises FileNotFoundError: If path does not exist.
    :raises EntityInventoryParseError: If document is structurally unparseable.
    """
    if work_item.get("item_type") != "business_object_discovery":
        msg = (
            f"Expected work_item item_type='business_object_discovery', "
            f"got {work_item.get('item_type')!r}"
        )
        raise ValueError(msg)

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Entity Inventory file not found: {path}")

    report = ParseReport()
    doc = Document(str(path))

    # Classify tables
    tables = _classify_tables(doc)

    if tables["entity_map"] is None:
        raise EntityInventoryParseError(
            "No Entity Map table found (expected ≥7 cols with "
            "'PRD Entity Name' header)"
        )

    # Parse header metadata
    source_metadata: dict[str, str] = {}
    if tables["header"] is not None:
        source_metadata = _parse_header_table(tables["header"], report)
    else:
        report.warn(
            "missing_header_table",
            "Document",
            "No header metadata table found",
        )

    # Parse Entity Map
    business_objects = _parse_entity_map(tables["entity_map"], report)

    # Enrich from detail cards
    if tables["detail_cards"]:
        _parse_detail_cards(tables["detail_cards"], business_objects, report)
    else:
        report.info(
            "no_detail_cards",
            "Document",
            "No entity detail card tables found",
        )

    # Check for BOs without detail card enrichment
    for bo in business_objects:
        if (
            bo.get("status") == "classified"
            and "singular_label" not in bo
        ):
            report.warn(
                "missing_detail_card",
                f"BO {bo['name']}",
                f"No detail card found for entity '{bo.get('entity_name', '')}'",
            )

    # Parse Open Issues
    open_issues: list[dict[str, str]] = []
    if tables["open_issues"] is not None:
        open_issues = _parse_open_issues(tables["open_issues"], report)
    else:
        report.warn(
            "missing_open_issues",
            "Document",
            "No Open Issues table found",
        )

    # Build envelope
    envelope = {
        "output_version": "1.0",
        "work_item_type": "business_object_discovery",
        "work_item_id": work_item["id"],
        "session_type": session_type,
        "payload": {
            "source_metadata": source_metadata,
            "business_objects": business_objects,
        },
        "decisions": [],
        "open_issues": open_issues,
    }

    return json.dumps(envelope, indent=2, ensure_ascii=False), report
