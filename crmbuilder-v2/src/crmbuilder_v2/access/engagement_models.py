"""Engagement dataclass and status enum (v0.5 slice A stub).

Sliced from the access layer so slice A's ``ActiveEngagementContext``
and dogfood-migration code can consume the engagement shape without
pulling in the slice-B repository or REST router. Slice B fleshes out
the access-layer repository (``access/engagement.py``) against this
dataclass; this module's shape is stable from slice A onward.

Per ``methodology-schema-specs/engagement.md`` §3.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EngagementStatus(str, Enum):
    """Operational lifecycle status for an engagement record.

    Free transitions between all three values per engagement.md §3.4.
    Default starter status is ``active``.
    """

    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"


@dataclass
class Engagement:
    """In-memory shape of a meta DB ``engagements`` row.

    All ten fields from the schema's §3.2 are represented.
    Timestamps are timezone-aware ``datetime`` objects. ``Engagement``
    is the access-layer's canonical shape; the REST API serialises it
    via ``to_dict()`` and hydrates it via ``from_row()`` (slice B).
    """

    engagement_identifier: str
    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: EngagementStatus
    engagement_last_opened_at: datetime | None
    engagement_export_dir: str | None
    engagement_created_at: datetime
    engagement_updated_at: datetime
    engagement_deleted_at: datetime | None
