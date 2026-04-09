"""Parse CBM-Master-PRD.docx → Personas + Domains + Process inventory.

Extracts:
- Organization overview text
- Personas with MST-PER-NNN codes
- Domains with domain codes
- Process inventory grouped by domain
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
)
from automation.cbm_import.reporter import ImportReport


def parse(path: str | Path) -> tuple[dict, ImportReport]:
    """Parse the Master PRD document.

    :param path: Path to CBM-Master-PRD.docx.
    :returns: Tuple of (parsed_data dict, ImportReport).
    """
    report = ImportReport()
    doc = load_document(path)
    paragraphs = extract_paragraphs(doc)
    tables = extract_tables(doc)

    data: dict = {
        "organization_overview": "",
        "personas": [],
        "domains": [],
        "processes": [],
    }

    # Organization overview — typically Section 1
    overview_idx = find_section_by_heading(paragraphs, r"organization\s+overview|about\s+cbm|1\.\s")
    if overview_idx is not None:
        data["organization_overview"] = extract_section_text(paragraphs, overview_idx)
    else:
        # Fallback: use first substantial paragraph
        for p in paragraphs:
            if len(p) > 100:
                data["organization_overview"] = p
                break
        report.add_warning("Could not find Organization Overview section")

    # Personas — scan tables and text for MST-PER patterns
    personas = _extract_personas(paragraphs, tables)
    data["personas"] = personas
    report.record_parsed("Persona", len(personas))

    # Domains — scan for domain inventory
    domains = _extract_domains(paragraphs, tables)
    data["domains"] = domains
    report.record_parsed("Domain", len(domains))

    # Process inventory — scan for process tables or lists
    # Note: Process parse count is NOT recorded here. The authoritative
    # Process count comes from individual process documents being parsed.
    # The Master PRD's role is to provide inventory metadata (domain
    # associations, expected process codes), not to create Process records.
    processes = _extract_processes(paragraphs, tables, domains)
    data["processes"] = processes

    return data, report


def _extract_personas(
    paragraphs: list[str], tables: list[list[list[str]]]
) -> list[dict[str, str]]:
    """Extract personas from the Master PRD."""
    personas: list[dict[str, str]] = []
    seen_codes: set[str] = set()

    # Search in tables first (more structured)
    for table in tables:
        for row in table:
            row_text = " ".join(row)
            match = re.search(r"(MST-PER-\d+)", row_text)
            if match:
                code = match.group(1)
                if code in seen_codes:
                    continue
                seen_codes.add(code)

                # Try to extract name and description from row cells
                name = ""
                desc = ""
                for cell in row:
                    cell = cell.strip()
                    if code in cell:
                        # This cell contains the code — name is usually the next non-empty cell
                        continue
                    if not name and cell and code not in cell:
                        name = cell
                    elif name and cell:
                        desc = cell
                        break

                if not name:
                    name = code
                personas.append({"code": code, "name": name, "description": desc})

    # Also search paragraphs
    for para in paragraphs:
        match = re.search(r"(MST-PER-\d+)\s*[:\-–—]\s*(.+?)(?:\s*[:\-–—]\s*(.+))?$", para)
        if match:
            code = match.group(1)
            if code not in seen_codes:
                seen_codes.add(code)
                personas.append({
                    "code": code,
                    "name": match.group(2).strip(),
                    "description": (match.group(3) or "").strip(),
                })

    return sorted(personas, key=lambda p: p["code"])


def _extract_domains(
    paragraphs: list[str], tables: list[list[list[str]]]
) -> list[dict]:
    """Extract domains from the Master PRD."""
    domains: list[dict] = []
    seen_codes: set[str] = set()

    # Known CBM domain codes
    known_codes = {"MN", "MR", "CR", "FU"}

    # Search in paragraphs for domain patterns
    for para in paragraphs:
        for code in known_codes:
            if code in seen_codes:
                continue
            # Look for patterns like "MN — Mentoring" or "Mentoring (MN)"
            match = re.search(
                rf"\b({code})\b\s*[:\-–—]\s*(.+?)(?:\s*[:\-–—]|$)", para
            )
            if match:
                seen_codes.add(code)
                domains.append({
                    "code": code,
                    "name": match.group(2).strip().split(".")[0].strip(),
                    "description": "",
                })
                continue

            match2 = re.search(rf"(.+?)\s*\(({code})\)", para)
            if match2:
                seen_codes.add(code)
                domains.append({
                    "code": code,
                    "name": match2.group(1).strip(),
                    "description": "",
                })

    # Also check tables
    for table in tables:
        for row in table:
            row_text = " ".join(row)
            for code in known_codes - seen_codes:
                if re.search(rf"\b{code}\b", row_text):
                    # Extract name from the row
                    name = ""
                    for cell in row:
                        cell_clean = cell.strip()
                        if cell_clean == code:
                            continue
                        if cell_clean and code not in cell_clean and len(cell_clean) > 2:
                            name = cell_clean
                            break
                    if name:
                        seen_codes.add(code)
                        domains.append({"code": code, "name": name, "description": ""})

    # Hardcode fallbacks for well-known CBM domains if not found
    _domain_names = {
        "MN": "Mentoring",
        "MR": "Mentor Recruitment",
        "CR": "Client Recruiting",
        "FU": "Fundraising",
    }
    for code, name in _domain_names.items():
        if code not in seen_codes:
            domains.append({"code": code, "name": name, "description": ""})

    return sorted(domains, key=lambda d: d["code"])


def _extract_processes(
    paragraphs: list[str],
    tables: list[list[list[str]]],
    domains: list[dict],
) -> list[dict]:
    """Extract process inventory from the Master PRD."""
    processes: list[dict] = []
    seen_codes: set[str] = set()

    # Process codes follow the pattern DOMAIN-NAME (e.g., MN-INTAKE, MR-RECRUIT)
    domain_codes = {d["code"] for d in domains}

    # Search paragraphs for process codes
    for para in paragraphs:
        matches = re.findall(r"\b([A-Z]{2,3}-[A-Z]{2,}(?:-[A-Z]+)*)\b", para)
        for code in matches:
            prefix = code.split("-")[0]
            if prefix in domain_codes and code not in seen_codes:
                seen_codes.add(code)
                # Extract name after the code
                name_match = re.search(
                    rf"{re.escape(code)}\s*[:\-–—]\s*(.+?)(?:\s*[:\-–—]|$)", para
                )
                name = name_match.group(1).strip() if name_match else code
                processes.append({
                    "code": code,
                    "name": name.split(".")[0].strip(),
                    "domain_code": prefix,
                    "sort_order": len(processes) + 1,
                })

    # Also search tables
    for table in tables:
        for row in table:
            for cell in row:
                matches = re.findall(r"\b([A-Z]{2,3}-[A-Z]{2,}(?:-[A-Z]+)*)\b", cell)
                for code in matches:
                    prefix = code.split("-")[0]
                    if prefix in domain_codes and code not in seen_codes:
                        seen_codes.add(code)
                        # Try to get name from another cell in the same row
                        name = code
                        for other_cell in row:
                            other = other_cell.strip()
                            if other and other != code and len(other) > 3:
                                name = other
                                break
                        processes.append({
                            "code": code,
                            "name": name.split(".")[0].strip(),
                            "domain_code": prefix,
                            "sort_order": len(processes) + 1,
                        })

    return sorted(processes, key=lambda p: p["code"])
