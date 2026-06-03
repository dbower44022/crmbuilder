"""Shared helpers for the Agent Profile Registry repositories (PI-122).

The registry entities are system/shared rows with a **nullable
``engagement_id``** (D-δ2): ``NULL`` = a system (universal) row, a set value = an
engagement overlay. The public ``scope`` field on every registry record maps to
that column: ``"system"`` ⇔ ``NULL``, otherwise an engagement identifier
(``ENG-NNN``). These helpers translate between the two and surface ``scope`` on
serialized records.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import FieldError, ValidationError
from crmbuilder_v2.access.models import EngagementRow

SYSTEM_SCOPE = "system"


def resolve_scope(session: Session, scope: str | None) -> str | None:
    """Translate a ``scope`` value to an ``engagement_id`` column value.

    ``None`` / ``"system"`` → ``None`` (a system row). Any other value must be an
    existing engagement identifier (``ENG-NNN``); returns it unchanged.
    """
    if scope is None or scope == SYSTEM_SCOPE:
        return None
    row = session.scalar(
        select(EngagementRow).where(
            EngagementRow.engagement_identifier == scope
        )
    )
    if row is None:
        raise ValidationError(
            [
                FieldError(
                    "scope",
                    "unknown_engagement",
                    f"scope must be 'system' or an existing engagement "
                    f"identifier; {scope!r} does not exist",
                )
            ]
        )
    return scope


def scope_of(engagement_id: str | None) -> str:
    """Return the public ``scope`` value for an ``engagement_id`` column value."""
    return SYSTEM_SCOPE if engagement_id is None else engagement_id


def with_scope(record: dict, engagement_id: str | None) -> dict:
    """Add the derived ``scope`` field to a serialized registry record."""
    record["scope"] = scope_of(engagement_id)
    return record
