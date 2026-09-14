"""Engagement dataclass and status enum (v0.5).

Sliced from the access layer so the desktop's ``ActiveEngagementContext``
and dogfood-migration code can consume the engagement shape without
pulling in the repository or REST router. Slice B fleshes out
``to_dict`` / ``from_row`` for envelope serialisation and hydration.

Per ``methodology-schema-specs/engagement.md`` §3.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any


class EngagementStatus(StrEnum):
    """Operational lifecycle status for an engagement record.

    Free transitions between all three values per engagement.md §3.4.
    Default starter status is ``active``.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


def _maybe_iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


@dataclass
class Engagement:
    """In-memory shape of a meta DB ``engagements`` row.

    The schema's §3.2 fields are represented (the vestigial
    ``engagement_export_dir`` was dropped in the PI-β follow-on pass).
    Timestamps are timezone-aware ``datetime`` objects. ``Engagement``
    is the access-layer's canonical shape; the REST API serialises it
    via ``to_dict()`` and hydrates it via ``from_row()``.
    """

    engagement_identifier: str
    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: EngagementStatus
    engagement_last_opened_at: datetime | None
    engagement_created_at: datetime
    engagement_updated_at: datetime
    engagement_deleted_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the API envelope's ``data`` payload shape.

        Status renders as its string value. Datetimes render as
        ISO 8601 strings. ``None`` values are preserved.
        """
        return {
            "engagement_identifier": self.engagement_identifier,
            "engagement_code": self.engagement_code,
            "engagement_name": self.engagement_name,
            "engagement_purpose": self.engagement_purpose,
            "engagement_status": (
                self.engagement_status.value
                if isinstance(self.engagement_status, EngagementStatus)
                else self.engagement_status
            ),
            "engagement_last_opened_at": _maybe_iso(
                self.engagement_last_opened_at
            ),
            "engagement_created_at": _maybe_iso(self.engagement_created_at),
            "engagement_updated_at": _maybe_iso(self.engagement_updated_at),
            "engagement_deleted_at": _maybe_iso(
                self.engagement_deleted_at
            ),
        }

    @classmethod
    def from_row(cls, row: Any) -> Engagement:
        """Hydrate from a SQLAlchemy ORM row (``EngagementRow``)."""
        status_value = row.engagement_status
        if isinstance(status_value, str):
            status = EngagementStatus(status_value)
        else:
            status = status_value
        return cls(
            engagement_identifier=row.engagement_identifier,
            engagement_code=row.engagement_code,
            engagement_name=row.engagement_name,
            engagement_purpose=row.engagement_purpose,
            engagement_status=status,
            engagement_last_opened_at=row.engagement_last_opened_at,
            engagement_created_at=row.engagement_created_at,
            engagement_updated_at=row.engagement_updated_at,
            engagement_deleted_at=row.engagement_deleted_at,
        )
