"""Common markdown parsing helpers for the bootstrap migration."""

from __future__ import annotations

import re

# Match ``**Label:**`` at start of line, optionally followed by inline content.
_FIELD_RE = re.compile(r"^\*\*(?P<label>[^*:]+?):\*\*[ \t]*(?P<inline>.*)$", re.MULTILINE)


def split_fields(block: str) -> dict[str, str]:
    """Parse a markdown block of ``**Label:** value`` fields into a dict.

    Multi-line values are supported: a field's value runs from its label
    line up to the next label line or end of block. Both inline content
    (same line as label) and continuation lines are concatenated.
    """
    matches = list(_FIELD_RE.finditer(block))
    if not matches:
        return {}
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        label = m.group("label").strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        inline = m.group("inline").strip()
        rest = block[body_start:body_end].strip()
        # ``rest`` already includes a trailing newline plus continuation
        # content; if inline is non-empty, prepend it.
        body = (inline + "\n" + rest if inline and rest else inline or rest).strip()
        out[label] = body
    return out


def expand_decision_range(text: str) -> list[str]:
    """Expand references like ``DEC-001 through DEC-011`` into [DEC-001, ..., DEC-011].

    Also picks out individually-named DEC-NNN tokens. Returns a sorted unique list.
    """
    found: set[str] = set()
    # Range pattern
    for a, b in re.findall(r"DEC-(\d{3})\s+(?:through|to)\s+DEC-(\d{3})", text):
        for n in range(int(a), int(b) + 1):
            found.add(f"DEC-{n:03d}")
    # Individual tokens
    for tok in re.findall(r"\bDEC-\d{3}\b", text):
        found.add(tok)
    return sorted(found)
