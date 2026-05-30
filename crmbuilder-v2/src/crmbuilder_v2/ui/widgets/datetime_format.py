"""Shared timestamp display formatting for panel list/detail views (PI-107).

Governance records carry ``created_at`` / ``updated_at`` (and the
per-entity-prefixed equivalents such as ``session_created_at``) as
ISO-8601 strings in the REST API envelope. Panels surface them through
:func:`format_timestamp`, which renders a human-readable local-time
string and degrades to an em dash for missing or unparseable values
rather than leaking raw ISO text into the UI.

The helper lives here, rather than inlined per panel, so the Planning
Items, Sessions, Decisions, and other timestamp-bearing panels can share
one rendering convention.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_DISPLAY_FORMAT = "%Y-%m-%d %H:%M"
_EMPTY = "—"  # em dash


def format_timestamp(value: Any) -> str:
    """Render an ISO-8601 timestamp (or ``datetime``) for display.

    :param value: An ISO-8601 string, a ``datetime``, or ``None`` as it
        arrives from the REST API envelope.
    :returns: ``"YYYY-MM-DD HH:MM"`` in the local timezone, or ``"—"``
        when *value* is missing or cannot be parsed. Naive inputs are
        assumed to be UTC, matching the storage convention (``_utcnow``
        in ``access/models.py`` stores ``datetime.now(UTC)``).
    """
    dt = _coerce(value)
    if dt is None:
        return _EMPTY
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone().strftime(_DISPLAY_FORMAT)


def _coerce(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
