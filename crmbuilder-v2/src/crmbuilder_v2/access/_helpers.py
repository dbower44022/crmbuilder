"""Shared helpers for repository modules."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import select

from crmbuilder_v2.access.exceptions import FieldError, ValidationError

_PREFIXED_IDENTIFIER_RE = re.compile(r"^(?P<prefix>[A-Z]+)-(?P<num>\d+)$")


def get_by_identifier(session, model, id_column, identifier):
    """Fetch one row by its identifier column (engagement-scope aware).

    Behaviour-preserving replacement for ``session.get(model, identifier)`` on
    the identifier-as-PK governance/methodology tables (PI-123 cutover Stage 1).
    Equivalent today, while the ``<entity>_identifier`` column is the sole
    primary key; but it survives PI-123's composite-PK change because it queries
    by the identifier *column* rather than positionally by primary key, and the
    engagement-scope read filter (``access.engagement_scope``) isolates the
    active engagement — returning the row that belongs to it, or ``None``.

    ``id_column`` is the model's identifier column (e.g.
    ``SessionModel.session_identifier``). Returns the row or ``None``; raises
    ``MultipleResultsFound`` only if the identifier is non-unique within the
    active scope (impossible while the column is unique / the filter is active).
    """
    return session.execute(
        select(model).where(id_column == identifier)
    ).scalar_one_or_none()


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


def validate_optional_value_list(
    value: Any,
    *,
    field: str,
    allowed: frozenset[str],
) -> list[str] | None:
    """Return ``None`` for None; validate a non-empty list of allowed strings.

    Used by PI-076's ``area`` field on planning_items (a multi-valued
    vocabulary-checked JSON column). The column is nullable until PI-083
    backfills and tightens to NOT NULL; when the caller supplies a value
    it must be a list with at least one element, every element a string
    drawn from ``allowed``, with no duplicates. Element order is
    preserved on the way through. Duplicates are rejected rather than
    silently de-duplicated so authoring mistakes surface at the boundary.
    """
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise ValidationError(
            [FieldError(field, "invalid_type", "must be a list of strings or null")]
        )
    items = list(value)
    if not items:
        raise ValidationError(
            [FieldError(field, "empty_list", "must contain at least one value")]
        )
    bad_types = [v for v in items if not isinstance(v, str)]
    if bad_types:
        raise ValidationError(
            [FieldError(field, "invalid_type", "every element must be a string")]
        )
    seen: set[str] = set()
    duplicates = sorted({v for v in items if v in seen or seen.add(v)})
    if duplicates:
        raise ValidationError(
            [FieldError(field, "duplicate_value", f"duplicate values: {duplicates}")]
        )
    invalid = sorted(v for v in items if v not in allowed)
    if invalid:
        raise ValidationError(
            [
                FieldError(
                    field,
                    "invalid_value",
                    f"unknown values {invalid}; must be drawn from "
                    f"{sorted(allowed)}",
                )
            ]
        )
    return items


def validate_optional_length(
    value: Any,
    *,
    field: str,
    min_len: int,
    max_len: int,
) -> str | None:
    """Return ``None`` for None/empty; reject non-strings; reject out-of-range strings.

    Used by PI-074's ``executive_summary`` field on planning_items, decisions,
    and sessions. The column is nullable in the schema (until PI-075's
    backfill + NOT NULL); when the caller supplies a value, it must be a
    string whose length sits in ``[min_len, max_len]`` inclusive. Empty
    string and whitespace-only strings are coerced to ``None`` so callers
    can omit the field cleanly without tripping the length check.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError(
            [FieldError(field, "invalid_type", "must be a string or null")]
        )
    if value.strip() == "":
        return None
    n = len(value)
    if n < min_len or n > max_len:
        raise ValidationError(
            [
                FieldError(
                    field,
                    "invalid_length",
                    f"must be {min_len}-{max_len} characters (got {n})",
                )
            ]
        )
    return value


def validate_required_length(
    value: Any,
    *,
    field: str,
    min_len: int,
    max_len: int,
) -> str:
    """Require a non-empty string whose length sits in ``[min_len, max_len]``.

    The required counterpart to :func:`validate_optional_length`. Used by
    the create paths for ``executive_summary`` on planning_items,
    decisions, and sessions, which became NOT NULL in PI-075 (migration
    0023). ``None``, non-strings, and empty/whitespace-only strings are
    all rejected, giving callers a clean ``ValidationError`` (422 at the
    API) instead of a database ``IntegrityError`` (500) when the field is
    omitted.
    """
    if value is None:
        raise ValidationError(
            [FieldError(field, "required", "must not be null")]
        )
    if not isinstance(value, str):
        raise ValidationError(
            [FieldError(field, "invalid_type", "must be a string")]
        )
    if value.strip() == "":
        raise ValidationError(
            [FieldError(field, "required", "must not be empty")]
        )
    n = len(value)
    if n < min_len or n > max_len:
        raise ValidationError(
            [
                FieldError(
                    field,
                    "invalid_length",
                    f"must be {min_len}-{max_len} characters (got {n})",
                )
            ]
        )
    return value
