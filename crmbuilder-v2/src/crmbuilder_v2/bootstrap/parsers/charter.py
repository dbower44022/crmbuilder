"""Parse ``charter.md`` into a list of charter version rows.

Strategy: parse the top-level ``## Change Log`` table to enumerate
historical versions, then build N rows where the most recent version
carries the full structured payload (sections + raw markdown) and
older versions carry a slim payload (description from the change-log
entry). The most recent version is flagged ``is_current=True``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

_HEADER_TOP = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FIELD_TOP = re.compile(r"^\*\*(?P<label>[^*:]+?):\*\*\s*(?P<value>.*)$", re.MULTILINE)
_SECTION_RE = re.compile(r"^##\s+(.+?)$", re.MULTILINE)
_CHANGELOG_ROW = re.compile(
    r"^\|\s*([\d.]+)\s*\|\s*([\d-]+(?:\s+\d{1,2}:\d{2})?)\s*\|\s*(.+?)\s*\|\s*$",
    re.MULTILINE,
)


def _parse_sections(text: str, start: int) -> dict[str, str]:
    """Extract ``## Section Name`` → body text for everything after ``start``."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(text, start))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        sections[name] = body
    return sections


def _parse_changelog_table(section_body: str) -> list[dict]:
    """Extract change-log rows from the ``## Change Log`` table body.

    Returns a list of ``{"version_label": "0.1", "date": "05-06-26",
    "description": "..."}`` dicts in source order (typically chronological).
    """
    rows = []
    for m in _CHANGELOG_ROW.finditer(section_body):
        version_label, date, description = m.group(1, 2, 3)
        # Skip the table header row ("Version | Date | Description") which
        # the regex doesn't match anyway since "Version" isn't [\d.]+.
        rows.append(
            {
                "version_label": version_label.strip(),
                "date": date.strip(),
                "description": description.strip(),
            }
        )
    return rows


def parse_charter(path: Path) -> list[dict]:
    """Parse ``charter.md``. Returns a list of dicts with keys
    ``version`` (int), ``is_current`` (bool), ``payload`` (dict),
    ``created_at`` (datetime | None).

    The most recent change-log row produces the current row carrying the
    full structured payload. Older change-log rows produce historical
    rows whose payload is a slim ``{"summary": "...", "version_label": ..., "date": ...}``
    descriptor.
    """
    text = path.read_text(encoding="utf-8")
    title_match = _HEADER_TOP.search(text)
    title = title_match.group(1).strip() if title_match else "Charter"

    metadata: dict[str, str] = {}
    for m in _FIELD_TOP.finditer(text):
        # Stop at the first markdown table line, since change-log entries
        # use **Version:** in their own lines that we don't want to capture.
        if m.start() > (title_match.end() if title_match else 0):
            metadata[m.group("label").strip()] = m.group("value").strip()

    sections = _parse_sections(text, title_match.end() if title_match else 0)
    changelog = _parse_changelog_table(sections.get("Change Log", ""))

    sections_for_payload = {
        name: body for name, body in sections.items() if name != "Change Log"
    }
    full_payload = {
        "title": title,
        "metadata": metadata,
        "sections": sections_for_payload,
        "markdown": text,
    }

    if not changelog:
        # No change log → emit one current row at version 1 with the full payload.
        return [
            {
                "version": 1,
                "is_current": True,
                "payload": full_payload,
                "created_at": None,
            }
        ]

    rows = []
    for i, entry in enumerate(changelog):
        version_int = i + 1  # 1, 2, 3, ... regardless of label
        is_current = i == len(changelog) - 1
        if is_current:
            payload = full_payload | {"version_label": entry["version_label"]}
        else:
            payload = {
                "version_label": entry["version_label"],
                "date": entry["date"],
                "description": entry["description"],
                "note": "Historical entry from migration; full content not preserved.",
            }
        rows.append(
            {
                "version": version_int,
                "is_current": is_current,
                "payload": payload,
                "created_at": _parse_date(entry["date"]),
            }
        )
    return rows


def _parse_date(s: str) -> datetime | None:
    """Best-effort parse of an ``MM-DD-YY`` or ``MM-DD-YY HH:MM`` date string."""
    s = s.strip()
    for fmt in ("%m-%d-%y %H:%M", "%m-%d-%y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
