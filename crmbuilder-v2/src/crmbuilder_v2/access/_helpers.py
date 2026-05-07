"""Shared helpers for repository modules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from crmbuilder_v2.access.exceptions import FieldError, ValidationError


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
