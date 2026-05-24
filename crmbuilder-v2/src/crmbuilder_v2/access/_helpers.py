"""Shared helpers for repository modules."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from crmbuilder_v2.access.exceptions import FieldError, ValidationError

_PREFIXED_IDENTIFIER_RE = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<num>\d+)$")


def next_prefixed_identifier(
    identifiers: Iterable[str | None],
    prefix: str,
    *,
    width: int = 3,
) -> str:
    """Compute the next ``PREFIX-NNN`` identifier from existing ones.

    Scans ``identifiers`` for values matching ``{prefix}-{digits}``,
    takes the highest numeric suffix, increments it, and zero-pads to
    ``width`` digits (default 3 for backward compatibility with v0.1-v0.7
    governance entity types; commits use width=4 per commit.md §3.5.3).
    Values that don't match the prefix pattern (or are
    ``None``/empty) are ignored. An empty or all-non-matching input
    yields ``{prefix}-001`` at width=3 or ``{prefix}-0001`` at width=4.

    Callers should pass *all* rows including soft-deleted ones so that
    a deleted record's identifier is never reused.
    """
    highest = 0
    for ident in identifiers:
        if not ident:
            continue
        match = _PREFIXED_IDENTIFIER_RE.match(ident)
        if match is None or match.group("prefix") != prefix:
            continue
        highest = max(highest, int(match.group("num")))
    return f"{prefix}-{highest + 1:0{width}d}"


def to_dict(row) -> dict:
    """Serialise a SQLAlchemy ORM row to a JSON-friendly dict."""
    out = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        out[col.name] = val
    return out


def require_string(value: Any, *, field: str) -> str:
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValidationError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value


def require_in(value: Any, allowed: frozenset[str], *, field: str) -> str:
    if value not in allowed:
        raise ValidationError(
            [
                FieldError(
                    field,
                    "invalid_value",
                    f"must be one of {sorted(allowed)}",
                )
            ]
        )
    return value
