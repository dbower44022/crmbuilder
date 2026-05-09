"""SQLAlchemy 2.0 ORM models for the v0.1 storage system.

Schema scope per ``storage-system-PRD-v0.1.md`` Section 5: project-management
entities only (charter, status, decisions, sessions, risks, planning items,
topics) plus the universal references table (DEC-006) and change log.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ACTORS,
    CHANGE_LOG_OPERATIONS,
    DECISION_STATUSES,
    ENTITY_TYPES,
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
    REFERENCE_RELATIONSHIPS,
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
    SESSION_STATUSES,
    _check_in,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Charter(Base):
    """Singleton document, versioned. ``is_current=True`` flags the latest row."""

    __tablename__ = "charter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("version", name="uq_charter_version"),
        Index("ix_charter_is_current", "is_current"),
    )


class Status(Base):
    """Singleton document, versioned. Same shape as ``Charter``."""

    __tablename__ = "status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("version", name="uq_status_version"),
        Index("ix_status_is_current", "is_current"),
    )


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    decision_date: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    alternatives_considered: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    consequences: Mapped[str] = mapped_column(Text, nullable=False, default="")
    supersedes_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("decisions.id"), nullable=True
    )
    superseded_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("decisions.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    supersedes: Mapped[Decision | None] = relationship(
        "Decision", remote_side="Decision.id", foreign_keys=[supersedes_id]
    )
    superseded_by: Mapped[Decision | None] = relationship(
        "Decision", remote_side="Decision.id", foreign_keys=[superseded_by_id]
    )

    __table_args__ = (
        CheckConstraint(_check_in("status", DECISION_STATUSES), name="ck_decision_status"),
        Index("ix_decisions_identifier", "identifier"),
    )


class Session(Base):
    """Append-only session record."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    session_date: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    conversation_reference: Mapped[str] = mapped_column(Text, nullable=False, default="")
    topics_covered: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    artifacts_produced: Mapped[str] = mapped_column(Text, nullable=False, default="")
    in_flight_at_end: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(_check_in("status", SESSION_STATUSES), name="ck_session_status"),
        Index("ix_sessions_identifier", "identifier"),
        Index("ix_sessions_session_date", "session_date"),
    )


class Risk(Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    probability: Mapped[str] = mapped_column(String(16), nullable=False)
    impact: Mapped[str] = mapped_column(String(16), nullable=False)
    response_plan: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("probability", RISK_PROBABILITIES), name="ck_risk_probability"
        ),
        CheckConstraint(_check_in("impact", RISK_IMPACTS), name="ck_risk_impact"),
        CheckConstraint(_check_in("status", RISK_STATUSES), name="ck_risk_status"),
    )


class PlanningItem(Base):
    __tablename__ = "planning_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("item_type", PLANNING_ITEM_TYPES), name="ck_planning_type"
        ),
        CheckConstraint(
            _check_in("status", PLANNING_ITEM_STATUSES), name="ck_planning_status"
        ),
    )


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    parent: Mapped[Topic | None] = relationship(
        "Topic", remote_side="Topic.id", foreign_keys=[parent_topic_id]
    )


class Reference(Base):
    """Universal polymorphic reference between two records (DEC-006)."""

    __tablename__ = "refs"  # avoid SQL reserved word "references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relationship_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("source_type", ENTITY_TYPES), name="ck_ref_source_type"
        ),
        CheckConstraint(
            _check_in("target_type", ENTITY_TYPES), name="ck_ref_target_type"
        ),
        CheckConstraint(
            _check_in("relationship_kind", REFERENCE_RELATIONSHIPS),
            name="ck_ref_relationship",
        ),
        UniqueConstraint(
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship_kind",
            name="uq_ref_full",
        ),
        Index("ix_refs_source", "source_type", "source_id"),
        Index("ix_refs_target", "target_type", "target_id"),
    )


class ChangeLog(Base):
    """Append-only change log emitted by every mutating access-layer call."""

    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(8), nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    before_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        CheckConstraint(
            _check_in("entity_type", ENTITY_TYPES | {"reference"}),
            name="ck_changelog_entity_type",
        ),
        CheckConstraint(
            _check_in("operation", CHANGE_LOG_OPERATIONS), name="ck_changelog_operation"
        ),
        CheckConstraint(_check_in("actor", CHANGE_LOG_ACTORS), name="ck_changelog_actor"),
        Index("ix_changelog_timestamp", "timestamp"),
        Index("ix_changelog_entity", "entity_type", "entity_identifier"),
    )
