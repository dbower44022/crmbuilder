"""Parse ``decisions.md`` into decision-row dicts."""

from __future__ import annotations

import re
from pathlib import Path

from crmbuilder_v2.bootstrap.parsers._md import split_fields

# Match a top-level decision header: "### DEC-NNN: Title"
_HEADER_RE = re.compile(
    r"^###\s+(DEC-\d{3}):\s+(.+)$", re.MULTILINE
)


def parse_decisions(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    headers = list(_HEADER_RE.finditer(text))
    if not headers:
        return []
    rows: list[dict] = []
    for i, h in enumerate(headers):
        identifier = h.group(1)
        title = h.group(2).strip()
        body_start = h.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        block = text[body_start:body_end]
        # Strip trailing horizontal rules used as section separators.
        block = re.sub(r"\n---\s*$", "", block, flags=re.MULTILINE).rstrip()
        fields = split_fields(block)
        rows.append(
            {
                "identifier": identifier,
                "title": title,
                "decision_date": fields.get("Date", "").strip(),
                "status": fields.get("Status", "").strip() or "Active",
                "context": fields.get("Context", "").strip(),
                "decision": fields.get("Decision", "").strip(),
                "rationale": fields.get("Rationale", "").strip(),
                "alternatives_considered": fields.get(
                    "Alternatives considered", ""
                ).strip(),
                "consequences": fields.get("Consequences", "").strip(),
            }
        )
    return rows
