"""Parse Domain Reconciliation .docx → Domain narrative + Decision records.

Extracts domain overview text, reconciliation text, and Decision records
from conflict resolution sections.
"""

from __future__ import annotations

import re
from pathlib import Path

from automation.cbm_import.docx_parser import (
    extract_paragraphs,
    extract_tables,
    load_document,
)
from automation.cbm_import.parser_logic import (
    extract_section_text,
    find_section_by_heading,
    parse_header_table,
)
from automation.cbm_import.reporter import ImportReport


def parse(path: str | Path) -> tuple[dict, ImportReport]:
    """Parse a Domain Reconciliation document.

    :param path: Path to the domain PRD .docx file.
    :returns: Tuple of (parsed_data dict, ImportReport).
    """
    report = ImportReport()
    doc = load_document(path)
    paragraphs = extract_paragraphs(doc)
    tables = extract_tables(doc)
    source_file = Path(path).name

    data: dict = {
        "domain_code": "",
        "domain_overview_text": "",
        "domain_reconciliation_text": "",
        "decisions": [],
    }

    # Header table
    if tables:
        header = parse_header_table(tables[0])
        data["domain_code"] = header.get("Domain Code", header.get("Domain", ""))

    # Try to get domain code from filename
    if not data["domain_code"]:
        stem = Path(path).stem
        match = re.search(r"(MN|MR|CR|FU)", stem, re.IGNORECASE)
        if match:
            data["domain_code"] = match.group(1).upper()

    # Domain overview — look for overview section
    overview_idx = find_section_by_heading(
        paragraphs, r"domain\s+overview|1\.\s+domain\s+overview"
    )
    if overview_idx is not None:
        data["domain_overview_text"] = extract_section_text(paragraphs, overview_idx)

    # Reconciliation text — look for reconciliation or consolidated section
    recon_idx = find_section_by_heading(
        paragraphs, r"reconcil|consolidat|conflict|design\s+decision"
    )
    if recon_idx is not None:
        data["domain_reconciliation_text"] = extract_section_text(paragraphs, recon_idx)

    # If no specific overview found, use the full document text
    if not data["domain_overview_text"]:
        # Concatenate all substantial paragraphs
        text_parts = [p for p in paragraphs if len(p) > 50]
        data["domain_overview_text"] = "\n".join(text_parts[:20])

    # Decisions — look for decision patterns
    decisions = _extract_decisions(paragraphs, tables, source_file)
    data["decisions"] = decisions
    report.record_parsed("Decision", len(decisions))

    return data, report


def _extract_decisions(
    paragraphs: list[str],
    tables: list[list[list[str]]],
    source_file: str,
) -> list[dict]:
    """Extract Decision records from the document."""
    decisions: list[dict] = []
    seen_ids: set[str] = set()

    # Search for decision patterns: DEC-NNN, DOMAIN-DEC-NNN
    for para in paragraphs:
        matches = re.findall(r"([\w-]*DEC-\d+)\s*[:\-–—]\s*(.+?)(?:\.|$)", para)
        for identifier, title in matches:
            if identifier not in seen_ids:
                seen_ids.add(identifier)
                decisions.append({
                    "identifier": identifier,
                    "title": title.strip(),
                    "description": title.strip(),
                    "status": "locked",
                })

    # Also look in tables for decision-like content
    for table in tables:
        for row in table:
            row_text = " ".join(row)
            matches = re.findall(r"([\w-]*DEC-\d+)", row_text)
            for identifier in matches:
                if identifier not in seen_ids:
                    seen_ids.add(identifier)
                    title = " ".join(cell.strip() for cell in row if identifier not in cell)
                    decisions.append({
                        "identifier": identifier,
                        "title": title.strip() or identifier,
                        "description": title.strip() or identifier,
                        "status": "locked",
                    })

    return decisions
