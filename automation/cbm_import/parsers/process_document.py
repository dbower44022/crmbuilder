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
    parse_requirement_list,
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

    # Workflow steps
    workflow_idx = find_section_by_heading(paragraphs, r"process\s+workflow|4\.\s+process\s+workflow")
    if workflow_idx is not None:
        steps = _extract_steps(paragraphs, workflow_idx)
        data["steps"] = steps
        report.record_parsed("ProcessStep", len(steps))

    # Requirements
    req_idx = find_section_by_heading(paragraphs, r"system\s+requirement|6\.\s+system\s+requirement")
    if req_idx is not None:
        reqs = parse_requirement_list(paragraphs, req_idx, data["process"].get("code", ""))
        data["requirements"] = reqs
        report.record_parsed("Requirement", len(reqs))

    # Also scan paragraphs for requirement-like patterns
    if not data["requirements"]:
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


def _extract_steps(paragraphs: list[str], start_idx: int) -> list[dict]:
    """Extract workflow steps from the Process Workflow section."""
    steps: list[dict] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if not text:
            continue
        # Stop at next top-level section heading (single digit + period + section keyword)
        if re.match(
            r"^\d+\.\s+(?:Process\s+(?:Purpose|Trigger|Completion|Data)|"
            r"System\s+Requirement|Personas?\s+Involved)",
            text, re.IGNORECASE,
        ):
            break

        # Match numbered steps
        match = re.match(r"^(?:Step\s+)?(\d+)[.):]\s*(.+)", text, re.IGNORECASE)
        if match:
            steps.append({
                "name": match.group(2).strip()[:200],  # Truncate long descriptions
                "description": match.group(2).strip(),
                "step_type": "action",
                "sort_order": int(match.group(1)),
            })
        elif steps and len(text) > 20:
            # Continuation of previous step description
            steps[-1]["description"] += " " + text

    return steps


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
