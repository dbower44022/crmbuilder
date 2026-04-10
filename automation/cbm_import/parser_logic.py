"""Pure-Python parsing helpers for CBM document structure detection.

No dependency on python-docx. All functions operate on lists of strings
(paragraph text) or lists of lists (table rows). Testable with hand-built data.
"""

from __future__ import annotations

import re


def find_section_by_heading(
    paragraphs: list[str],
    heading_pattern: str,
    *,
    case_sensitive: bool = False,
) -> int | None:
    """Find the index of a paragraph matching a heading pattern.

    :param paragraphs: List of paragraph text strings.
    :param heading_pattern: Regex pattern to match.
    :param case_sensitive: Whether matching is case-sensitive.
    :returns: Index of the matching paragraph, or None.
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    for i, text in enumerate(paragraphs):
        if re.search(heading_pattern, text.strip(), flags):
            return i
    return None


def extract_section_text(
    paragraphs: list[str],
    start_idx: int,
    stop_patterns: list[str] | None = None,
) -> str:
    """Extract text from start_idx+1 until the next heading or stop pattern.

    :param paragraphs: List of paragraph text strings.
    :param start_idx: Index of the section heading (content starts at start_idx+1).
    :param stop_patterns: Regex patterns that indicate the end of the section.
    :returns: Joined text of the section paragraphs.
    """
    lines: list[str] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if stop_patterns:
            for pat in stop_patterns:
                if re.match(pat, text, re.IGNORECASE):
                    return "\n".join(lines).strip()
        # Stop at next numbered section heading (e.g., "2.", "3.", "4.1")
        if re.match(r"^\d+(\.\d+)*\.\s+\S", text):
            return "\n".join(lines).strip()
        if text:
            lines.append(text)
    return "\n".join(lines).strip()


def parse_header_table(rows: list[list[str]]) -> dict[str, str]:
    """Parse a document header table into key-value pairs.

    CBM documents start with a table containing metadata like:
    Document Type | Master PRD
    Version | 2.3
    Status | Active

    :param rows: Table rows, each a list of cell text strings.
    :returns: Dict mapping header keys to values.
    """
    result: dict[str, str] = {}
    for row in rows:
        if len(row) >= 2:
            key = row[0].strip().rstrip(":")
            value = row[1].strip()
            if key and value:
                result[key] = value
    return result


def parse_field_table(
    rows: list[list[str]],
    source_file: str = "",
) -> list[dict[str, str]]:
    """Parse a CBM field table into a list of field dicts.

    CBM field tables have varying column structures but commonly include:
    Field Name | Type | Required | Values | Default | ID

    Some tables have a Description column. Some have two rows per field
    (the second row being a description spanning all columns).

    :param rows: Table rows, each a list of cell text strings.
    :param source_file: Source file name for error reporting.
    :returns: List of field dicts with normalized keys.
    """
    if not rows:
        return []

    # Detect header row
    header_row = rows[0]
    headers = [_normalize_header(h) for h in header_row]

    fields: list[dict[str, str]] = []
    i = 1
    while i < len(rows):
        row = rows[i]
        if len(row) < 2:
            i += 1
            continue

        # Skip rows that look like sub-headers or empty rows
        first_cell = row[0].strip()
        if not first_cell or first_cell.lower() in ("field name", "native field", "field"):
            i += 1
            continue

        # Detect merged description rows: python-docx returns merged cells
        # with the same text in every cell. Check 3+ cells to avoid false
        # positives (e.g., field name "email" with type "email").
        if len(row) >= 3:
            second_cell = row[1].strip()
            third_cell = row[2].strip()
            if first_cell and second_cell and first_cell == second_cell == third_cell:
                # Merged description row — attach to previous field
                if fields:
                    prev_desc = fields[-1].get("description", "")
                    if first_cell not in prev_desc:
                        fields[-1]["description"] = first_cell
                i += 1
                continue

        # Safety net: field names are short camelCase identifiers, never
        # longer than ~40 chars. Anything over 200 is a description.
        if len(first_cell) > 200:
            if fields:
                prev_desc = fields[-1].get("description", "")
                if first_cell not in prev_desc:
                    fields[-1]["description"] = first_cell
            i += 1
            continue

        field: dict[str, str] = {}
        for j, cell in enumerate(row):
            if j < len(headers):
                field[headers[j]] = cell.strip()
            elif cell.strip():
                field[f"col_{j}"] = cell.strip()

        # Check if the next row is a description continuation
        if i + 1 < len(rows):
            next_row = rows[i + 1]
            # A description row typically has content only in the first cell
            if len(next_row) >= 1 and next_row[0].strip():
                all_others_empty = all(
                    not c.strip() for c in next_row[1:]
                ) if len(next_row) > 1 else True
                if all_others_empty and not re.match(r"^[a-z]", next_row[0].strip()):
                    # Consume the description row and attach to this field
                    field["description"] = next_row[0].strip()
                    i += 1

        if field.get("field_name"):
            fields.append(field)
        i += 1

    return fields


def parse_persona_list(
    paragraphs: list[str],
    start_idx: int,
) -> list[dict[str, str]]:
    """Parse a persona list from section content.

    Personas appear as bullet points or table rows with format:
    MST-PER-001: System Administrator — ...

    :param paragraphs: List of paragraph text strings.
    :param start_idx: Index of the Personas heading.
    :returns: List of persona dicts with 'code', 'name', 'description'.
    """
    personas: list[dict[str, str]] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if not text:
            continue
        # Stop at next section heading
        if re.match(r"^\d+(\.\d+)*\.\s+\S", text):
            break

        # Try to match persona pattern: CODE: Name — Description
        match = re.match(
            r"(MST-PER-\d+)\s*[:\-–—]\s*(.+?)(?:\s*[:\-–—]\s*(.+))?$",
            text,
        )
        if match:
            personas.append({
                "code": match.group(1),
                "name": match.group(2).strip(),
                "description": (match.group(3) or "").strip(),
            })
            continue

        # Also try: Name (CODE) — Description
        match2 = re.match(
            r"(.+?)\s*\((MST-PER-\d+)\)\s*[:\-–—]?\s*(.*)",
            text,
        )
        if match2:
            personas.append({
                "code": match2.group(2),
                "name": match2.group(1).strip(),
                "description": match2.group(3).strip(),
            })

    return personas


def parse_numbered_list(
    paragraphs: list[str],
    start_idx: int,
) -> list[dict[str, str]]:
    """Parse a numbered list from section content.

    Each item has format: N. Description text

    :param paragraphs: List of paragraph text strings.
    :param start_idx: Index of the section heading.
    :returns: List of dicts with 'number' and 'text'.
    """
    items: list[dict[str, str]] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if not text:
            continue
        if re.match(r"^\d+(\.\d+)*\.\s+\S", text) and not re.match(r"^\d+\.\s", text):
            break  # Next section heading (multi-level numbering)

        match = re.match(r"^(\d+)\.\s+(.+)", text)
        if match:
            items.append({
                "number": match.group(1),
                "text": match.group(2).strip(),
            })
    return items


def parse_requirement_list(
    paragraphs: list[str],
    start_idx: int,
    code_prefix: str = "",
) -> list[dict[str, str]]:
    """Parse a requirements section.

    Requirements have identifiers like REQ-001 or MN-INTAKE-REQ-001.

    :param paragraphs: List of paragraph text strings.
    :param start_idx: Index of the section heading.
    :param code_prefix: Expected prefix for requirement identifiers.
    :returns: List of dicts with 'identifier', 'description', 'priority'.
    """
    reqs: list[dict[str, str]] = []
    for i in range(start_idx + 1, len(paragraphs)):
        text = paragraphs[i].strip()
        if not text:
            continue
        if re.match(r"^\d+(\.\d+)*\.\s+\S", text):
            break

        # Match requirement pattern: IDENTIFIER: Description
        match = re.match(r"([\w-]+-(?:REQ|SYS|DAT)-\d+)\s*[:\-–—]\s*(.+)", text)
        if match:
            reqs.append({
                "identifier": match.group(1),
                "description": match.group(2).strip(),
                "priority": "must",  # Default
            })
    return reqs


def extract_enum_values(values_str: str) -> list[str]:
    """Extract enum values from a field table cell.

    Values may be pipe-separated, comma-separated, or one per line.

    :param values_str: Raw values string from the field table.
    :returns: List of individual values.
    """
    if not values_str or values_str.strip() in ("—", "-", "N/A", "TBD", ""):
        return []

    # Try pipe separation first
    if "|" in values_str:
        return [v.strip() for v in values_str.split("|") if v.strip()]

    # Try comma separation
    if "," in values_str:
        return [v.strip() for v in values_str.split(",") if v.strip()]

    # Try newline separation
    if "\n" in values_str:
        return [v.strip() for v in values_str.split("\n") if v.strip()]

    # Single value
    return [values_str.strip()] if values_str.strip() else []


def _normalize_header(header: str) -> str:
    """Normalize a table header to a consistent key name."""
    h = header.strip().lower()
    h = re.sub(r"[^a-z0-9]+", "_", h)
    h = h.strip("_")

    # Common mappings
    mappings = {
        "field_name": "field_name",
        "field": "field_name",
        "native_field": "field_name",
        "name": "field_name",
        "type": "field_type",
        "data_type": "field_type",
        "required": "required",
        "values": "values",
        "options": "values",
        "default": "default_value",
        "default_value": "default_value",
        "id": "identifier",
        "req_id": "identifier",
        "description": "description",
    }
    return mappings.get(h, h)
