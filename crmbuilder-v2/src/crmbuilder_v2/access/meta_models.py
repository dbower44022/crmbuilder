"""SQLAlchemy ORM model for the meta DB (v0.5 slice A).

Separate from ``access/models.py`` (per-engagement DB models) because
the meta DB has its own Alembic chain and connection pool. See
``multi-engagement-architecture.md`` §3.1 and §3.10.

Slice A defines just the ``Engagement`` ORM row; slice B's access-layer
repository consumes it. The shape mirrors the dataclass in
``engagement_models.py`` exactly so hydration is a trivial copy.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# PI-alpha: share the dialect-aware identifier-format CHECK so the meta DB's
# ``engagements`` table stays byte-identical (and in parity, per
# test_engagements_model_parity) with the main one. The meta DB itself stays
# SQLite through PI-alpha — this construct still renders GLOB there — but the
# parity check compiles both with the default dialect, so both must use the same
# construct. (Temporary coupling: PI-beta deletes the meta layer entirely.)
from crmbuilder_v2.access.models import _IdentifierFormatCheck


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MetaBase(DeclarativeBase):
    """Declarative base for the meta DB."""

    pass


class EngagementRow(MetaBase):
    """Row in the meta DB's ``engagements`` table.

    Named ``EngagementRow`` to keep distinct from the dataclass
    ``Engagement`` in ``engagement_models.py`` — both refer to the same
    storage shape; the dataclass is the public access-layer hand-off,
    the ORM row is the SQLAlchemy mapping.
    """

    __tablename__ = "engagements"

    engagement_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    engagement_code: Mapped[str] = mapped_column(String(16), nullable=False)
    engagement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    engagement_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    engagement_status: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    engagement_last_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    engagement_export_dir: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    engagement_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    engagement_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    engagement_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("engagement_identifier", ["ENG"]),
            name="ck_engagement_identifier_format",
        ),
        CheckConstraint(
            "engagement_status IN ('active', 'paused', 'archived')",
            name="ck_engagement_status",
        ),
        Index(
            "ux_engagements_code_lower",
            text("LOWER(engagement_code)"),
            unique=True,
        ),
        Index(
            "ux_engagements_name_lower",
            text("LOWER(engagement_name)"),
            unique=True,
        ),
        Index("ix_engagements_status", "engagement_status"),
        Index("ix_engagements_last_opened_at", "engagement_last_opened_at"),
        Index("ix_engagements_deleted_at", "engagement_deleted_at"),
    )
