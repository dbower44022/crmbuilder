"""Engagement-area repository (PI-112; DEC-342, DEC-348).

The Engagement tier of the two-tier area model: per-engagement, user-defined
work-region labels stored in the ``engagement_areas`` table of each engagement
database. The System tier is the static ``vocab.SYSTEM_AREA_RANKS`` dict.

``valid_area_names`` returns the union (System ∪ this engagement's Engagement
areas) and is the single source of truth consulted wherever an ``area`` value
is validated (planning_items, orchestration). Validation is session-aware
because the Engagement tier lives in the database, not in code.

Engagement areas are a plain config table — not a governance entity (absent
from ``ENTITY_TYPES``), so no change-log emission or reference edges, and the
name is the natural primary key (no prefixed identifier).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import EngagementArea
from crmbuilder_v2.access.vocab import SYSTEM_AREAS

# Engagement-area names share the System-area label grammar: lowercase
# letters, digits, and single hyphens (e.g. ``mn``, ``services``). Keeping
# the grammar uniform lets the two tiers be validated against one rule.
_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _require_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_area_name",
                    "invalid_format",
                    "must be lowercase letters/digits with single hyphens "
                    "(e.g. 'mn', 'services')",
                )
            ]
        )
    if name in SYSTEM_AREAS:
        raise UnprocessableError(
            [
                FieldError(
                    "engagement_area_name",
                    "reserved",
                    f"'{name}' is a System area; Engagement areas must be "
                    "distinct from the global System tier",
                )
            ]
        )
    return name


def valid_area_names(session: Session) -> frozenset[str]:
    """Return System areas ∪ this engagement's Engagement areas.

    The authoritative set an ``area`` value is validated against. System
    areas come from code (immutable, DEC-006); Engagement areas from the
    per-engagement ``engagement_areas`` table.
    """
    engagement = session.scalars(
        select(EngagementArea.engagement_area_name)
    ).all()
    return SYSTEM_AREAS | frozenset(engagement)


def list_engagement_areas(session: Session) -> list[dict]:
    rows = session.scalars(
        select(EngagementArea).order_by(EngagementArea.engagement_area_name)
    ).all()
    return [to_dict(r) for r in rows]


def _get_row(session: Session, name: str) -> EngagementArea | None:
    # PI-123: the PK is composite ``(engagement_area_name, engagement_id)``, so
    # a single-value ``session.get`` no longer addresses a row. A filtered
    # select lets the central read-filter supply the active ``engagement_id``.
    return session.scalars(
        select(EngagementArea).where(
            EngagementArea.engagement_area_name == name
        )
    ).first()


def get_engagement_area(session: Session, name: str) -> dict:
    row = _get_row(session, name)
    if row is None:
        raise NotFoundError("engagement_area", name)
    return to_dict(row)


def create_engagement_area(
    session: Session, name: str, *, description: str | None = None
) -> dict:
    name = _require_name(name)
    row = EngagementArea(
        engagement_area_name=name,
        engagement_area_description=description,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError(
            f"engagement_area '{name}' already exists"
        ) from exc
    return to_dict(row)


def delete_engagement_area(session: Session, name: str) -> None:
    row = _get_row(session, name)
    if row is None:
        raise NotFoundError("engagement_area", name)
    session.delete(row)
    session.flush()
