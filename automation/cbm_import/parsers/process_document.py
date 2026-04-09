"""Parse Process Document .docx → Process + ProcessStep + Requirement + cross-references.

Handles the standard CBM Process Document format: purpose, triggers,
personas, workflow steps, completion criteria, requirements, process data.
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
    """Parse a Process Document.

    :param path: Path to the process document .docx file.
    :returns: Tuple of (parsed_data dict, ImportReport).
    """
    report = ImportReport()
    doc = load_document(path)
    paragraphs = extract_paragraphs(doc)
    tables = extract_tables(doc)
    source_file = Path(path).name

    data: dict = {
        "process": {},
        "steps": [],
        "requirements": [],
        "personas": [],
        "entities": [],
        "fields": [],
    }

    # Header table
    if tables:
        header = parse_header_table(tables[0])
        process_code = header.get("Process Code", header.get("Code", ""))
        domain_code = header.get("Domain", header.get("Domain Code", ""))
        data["process"] = {
            "code": process_code,
            "domain_code": domain_code,
            "name": header.get("Process Name", header.get("Name", "")),
            "description": "",
            "triggers": "",
            "completion_criteria": "",
        }
    else:
        # Derive from filename (e.g., MN-INTAKE.docx)
        stem = Path(path).stem
        data["process"] = {
            "code": stem,
            "domain_code": stem.split("-")[0] if "-" in stem else "",
            "name": stem,
            "description": "",
            "triggers": "",
            "completion_criteria": "",
        }
        report.add_warning(f"No header table found in {source_file}")

    # Process purpose
    purpose_idx = find_section_by_heading(paragraphs, r"process\s+purpose|1\.\s+process\s+purpose")
    if purpose_idx is not None:
        data["process"]["description"] = extract_section_text(paragraphs, purpose_idx)

    # Process triggers
    triggers_idx = find_section_by_heading(paragraphs, r"process\s+trigger|2\.\s+process\s+trigger")
    if triggers_idx is not None:
        data["process"]["triggers"] = extract_section_text(paragraphs, triggers_idx)

    # Process completion
    completion_idx = find_section_by_heading(paragraphs, r"process\s+completion|5\.\s+process\s+completion")
    if completion_idx is not None:
        data["process"]["completion_criteria"] = extract_section_text(paragraphs, completion_idx)

    # Workflow steps — use Document object for style detection
    workflow_idx = find_section_by_heading(paragraphs, r"process\s+workflow|4\.\s+process\s+workflow")
    if workflow_idx is not None:
        steps = _extract_steps_from_doc(doc, workflow_idx)
        data["steps"] = steps
        report.record_parsed("ProcessStep", len(steps))

    # Requirements — primary: scan tables for ID/Requirement header
    reqs = _extract_requirements_from_tables(tables)
    if not reqs:
        # Fallback: scan paragraphs for requirement-like patterns
        reqs = _extract_requirements_from_text(paragraphs, source_file)
    data["requirements"] = reqs
    report.record_parsed("Requirement", len(reqs))

    # Personas — extract from Personas section
    persona_idx = find_section_by_heading(paragraphs, r"personas?\s+involved|3\.\s+personas")
    if persona_idx is not None:
        personas = _extract_persona_refs(paragraphs, persona_idx)
        data["personas"] = personas

    # Process data / entities referenced
    data_idx = find_section_by_heading(paragraphs, r"process\s+data|7\.\s+process\s+data")
    if data_idx is not None:
        entities, fields = _extract_process_data(paragraphs, tables, data_idx)
        data["entities"] = entities
        data["fields"] = fields

    report.record_parsed("Process", 1)
    return data, report


def _extract_steps_from_doc(doc, workflow_heading_idx: int) -> list[dict]:
    """Extract workflow steps using paragraph style detection.

    CBM process documents store workflow steps as Word 'List Paragraph'
    style items where the number prefix is managed by Word's numbering
    engine and not present in the paragraph text. This function uses
    style-name detection (Option B) and assigns sort_order by position.

    :param doc: python-docx Document object.
    :param workflow_heading_idx: Index of the workflow heading in doc.paragraphs.
    :returns: List of step dicts.
    """
    steps: list[dict] = []
    sort_order = 0
    in_section = False

    for i, para in enumerate(doc.paragraphs):
        if i <= workflow_heading_idx:
            continue

        text = para.text.strip()
        style_name = para.style.name if para.style else ""

        # Stop at next top-level section (Heading 1 only)
        if style_name == "Heading 1":
            if in_section or sort_order > 0:
                break
            continue

        # Skip sub-section headings (Heading 2, Heading 3) without breaking
        if style_name and style_name.startswith("Heading"):
            continue

        if not text:
            continue

        in_section = True

        # Also stop on numbered section headings in body text
        if re.match(
            r"^\d+\.\s+(?:Process\s+(?:Purpose|Trigger|Completion|Data)|"
            r"System\s+Requirement|Personas?\s+Involved)",
            text, re.IGNORECASE,
        ):
            break

        # Detect list items by style name
        is_list_item = "list" in style_name.lower()

        # Also try regex for explicitly numbered steps (fallback)
        match = re.match(r"^(?:Step\s+)?(\d+)[.):]\s*(.+)", text, re.IGNORECASE)

        if is_list_item:
            sort_order += 1
            steps.append({
                "name": text[:200],
                "description": text,
                "step_type": "action",
                "sort_order": sort_order,
            })
        elif match:
            sort_order += 1
            steps.append({
                "name": match.group(2).strip()[:200],
                "description": match.group(2).strip(),
                "step_type": "action",
                "sort_order": int(match.group(1)),
            })
        elif steps and len(text) > 20:
            # Continuation text — append to previous step's description
            steps[-1]["description"] += " " + text

    return steps


def _extract_requirements_from_tables(tables: list[list[list[str]]]) -> list[dict]:
    """Extract requirements from ID/Requirement tables.

    CBM process documents store requirements in a two-column table with
    header row ['ID', 'Requirement'] followed by data rows.
    """
    reqs: list[dict] = []
    seen: set[str] = set()
    for table in tables:
        if len(table) < 2:
            continue
        header = [c.strip().lower() for c in table[0]]
        # Match tables where first col is 'id' and second col contains 'requirement'
        if len(header) < 2:
            continue
        if header[0] != "id" or "requirement" not in header[1]:
            continue
        # This is a requirements table
        for row in table[1:]:
            if len(row) < 2:
                continue
            identifier = row[0].strip()
            description = row[1].strip()
            if not identifier or not description:
                continue
            # Only accept rows with requirement-like identifiers
            if not re.search(r"REQ-\d+", identifier):
                continue
            if identifier not in seen:
                seen.add(identifier)
                reqs.append({
                    "identifier": identifier,
                    "description": description,
                    "priority": "must",
                })
    return reqs


def _extract_requirements_from_text(
    paragraphs: list[str], source_file: str
) -> list[dict]:
    """Extract requirements from paragraph text using identifier patterns."""
    reqs: list[dict] = []
    seen: set[str] = set()
    for para in paragraphs:
        matches = re.findall(r"([\w-]+-(?:REQ|SYS|DAT)-\d+)\s*[:\-–—]\s*(.+?)(?:\.|$)", para)
        for identifier, desc in matches:
            if identifier not in seen:
                seen.add(identifier)
                reqs.append({
                    "identifier": identifier,
                    "description": desc.strip(),
                    "priority": "must",
                })
    return reqs


def _extract_persona_refs(paragraphs: list[str], start_idx: int) -> list[dict]:
    """Extract persona references from the Personas section."""
    personas: list[dict] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if not text:
            continue
        if re.match(r"^\d+\.\s+\S", text):
            break
        match = re.search(r"(MST-PER-\d+)", text)
        if match:
            # Extract role description
            role = "performer"
            if "initiat" in text.lower():
                role = "initiator"
            elif "approv" in text.lower():
                role = "approver"
            elif "receiv" in text.lower() or "notif" in text.lower():
                role = "recipient"
            personas.append({
                "code": match.group(1),
                "role": role,
            })
    return personas


def _extract_process_data(
    paragraphs: list[str],
    tables: list[list[list[str]]],
    start_idx: int,
) -> tuple[list[dict], list[dict]]:
    """Extract entity and field references from Process Data section."""
    entities: list[dict] = []
    fields: list[dict] = []

    # Process data is often in tables with Entity: Field Name | Type | Description
    # Look for tables after the section heading
    for table in tables:
        for row in table:
            if len(row) >= 2:
                first_cell = row[0].strip()
                # Check if first cell is an entity name
                if re.match(r"^[A-Z][a-z]+", first_cell) and ":" not in first_cell:
                    if first_cell not in [e.get("name") for e in entities]:
                        entities.append({"name": first_cell, "role": "referenced"})

    return entities, fields
