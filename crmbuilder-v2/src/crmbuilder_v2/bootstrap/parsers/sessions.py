"""Parse ``sessions.md`` into session-row dicts plus their ``decided_in`` references."""

from __future__ import annotations

import re
from pathlib import Path

from crmbuilder_v2.bootstrap.parsers._md import expand_decision_range, split_fields

_HEADER_RE = re.compile(
    r"^##\s+(SES-\d{3}):\s+(.+)$", re.MULTILINE
)


def parse_sessions(path: Path) -> list[dict]:
    """Returns a list of session dicts. Each dict carries an extra
    ``decisions_made`` key with a sorted list of DEC-NNN identifiers
    extracted from the ``Decisions made:`` field for cross-reference
    materialisation by the migration driver."""
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
        block = re.sub(r"\n---\s*$", "", block, flags=re.MULTILINE).rstrip()
        fields = split_fields(block)
        decisions_made_raw = fields.get("Decisions made", "")
        rows.append(
            {
                "identifier": identifier,
                "title": title,
                "session_date": fields.get("Date", "").strip(),
                "status": fields.get("Status", "").strip() or "Complete",
                "conversation_reference": fields.get(
                    "Conversation reference", ""
                ).strip(),
                "topics_covered": fields.get("Topics covered", "").strip(),
                "summary": fields.get("Summary", "").strip(),
                "artifacts_produced": fields.get("Artifacts produced", "").strip(),
                "in_flight_at_end": fields.get(
                    "In-flight at session end", ""
                ).strip(),
                "decisions_made": expand_decision_range(decisions_made_raw),
            }
        )
    return rows
