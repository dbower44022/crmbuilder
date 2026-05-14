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
    CATALOG_ATTRIBUTE_TYPES,
    CATALOG_DATA_MODEL_ROLES,
    CATALOG_ENTRY_KINDS,
    CATALOG_IS_STANDARD_VALUES,
    CATALOG_MECHANISMS,
    CATALOG_PRESENCE_STATUSES,
    CATALOG_RELATIONSHIP_CARDINALITIES,
    CATALOG_RELATIONSHIP_ROLES,
    CATALOG_SYSTEMS,
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


# ---------------------------------------------------------------------------
# Base entity catalog (catalog-ingestion-PRD-v0.1.md section 4).
#
# Ten tables holding the structured reference data for V2's three runtime
# use cases (reference library, cross-system mapper, gap checker). Catalog
# rows use V2's standard ``id INTEGER PK + identifier TEXT UNIQUE`` shape
# rather than UUID PKs; the stable string identifier on entities is
# ``catalog_id`` (e.g. ``"account"``, ``"donation-major-gift"``) and
# attributes are addressed by their parent ``catalog_id`` plus their
# ``name`` column.
# ---------------------------------------------------------------------------


class CatalogEntity(Base):
    __tablename__ = "catalog_entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    parent_entity_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("catalog_entity.id"), nullable=True
    )
    discriminator_attribute: Mapped[str | None] = mapped_column(String(128), nullable=True)
    discriminator_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    business_context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_model_role: Mapped[str] = mapped_column(String(32), nullable=False)
    typically_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    parent: Mapped[CatalogEntity | None] = relationship(
        "CatalogEntity", remote_side="CatalogEntity.id", foreign_keys=[parent_entity_id]
    )

    __table_args__ = (
        CheckConstraint("tier BETWEEN 1 AND 5", name="ck_catalog_entity_tier"),
        CheckConstraint(
            _check_in("entry_kind", CATALOG_ENTRY_KINDS),
            name="ck_catalog_entity_entry_kind",
        ),
        CheckConstraint(
            _check_in("data_model_role", CATALOG_DATA_MODEL_ROLES),
            name="ck_catalog_entity_data_model_role",
        ),
        Index("ix_catalog_entity_catalog_id", "catalog_id"),
        Index("ix_catalog_entity_tier_kind", "tier", "entry_kind"),
        Index("ix_catalog_entity_parent", "parent_entity_id"),
        Index("ix_catalog_entity_is_deleted", "is_deleted"),
    )


class CatalogEntitySynonym(Base):
    __tablename__ = "catalog_entity_synonym"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    synonym: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_catalog_entity_synonym_entity", "catalog_entity_id"),
        Index("ix_catalog_entity_synonym_text", "synonym"),
    )


class CatalogEntitySystem(Base):
    __tablename__ = "catalog_entity_system"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    system: Mapped[str] = mapped_column(String(32), nullable=False)
    system_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_standard: Mapped[str] = mapped_column(String(16), nullable=False)
    mechanism: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            _check_in("system", CATALOG_SYSTEMS), name="ck_catalog_entity_system_system"
        ),
        CheckConstraint(
            _check_in("is_standard", CATALOG_IS_STANDARD_VALUES),
            name="ck_catalog_entity_system_is_standard",
        ),
        CheckConstraint(
            "mechanism IS NULL OR " + _check_in("mechanism", CATALOG_MECHANISMS),
            name="ck_catalog_entity_system_mechanism",
        ),
        UniqueConstraint(
            "catalog_entity_id", "system", name="uq_catalog_entity_system"
        ),
        Index("ix_catalog_entity_system_entity", "catalog_entity_id"),
    )


class CatalogSource(Base):
    __tablename__ = "catalog_source"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (Index("ix_catalog_source_entity", "catalog_entity_id"),)


class CatalogAttribute(Base):
    __tablename__ = "catalog_attribute"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reference_target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    usage: Mapped[str] = mapped_column(Text, nullable=False, default="")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("type", CATALOG_ATTRIBUTE_TYPES), name="ck_catalog_attribute_type"
        ),
        UniqueConstraint("catalog_entity_id", "name", name="uq_catalog_attribute_entity_name"),
        Index("ix_catalog_attribute_entity", "catalog_entity_id"),
        Index("ix_catalog_attribute_name", "name"),
        Index("ix_catalog_attribute_is_deleted", "is_deleted"),
    )


class CatalogAttributeEnumValue(Base):
    __tablename__ = "catalog_attribute_enum_value"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_attribute_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_attribute.id", ondelete="CASCADE"),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_catalog_attribute_enum_value_attr", "catalog_attribute_id"),
    )


class CatalogAttributeSynonym(Base):
    __tablename__ = "catalog_attribute_synonym"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_attribute_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_attribute.id", ondelete="CASCADE"),
        nullable=False,
    )
    synonym: Mapped[str] = mapped_column(String(255), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_catalog_attribute_synonym_attr", "catalog_attribute_id"),
        Index("ix_catalog_attribute_synonym_text", "synonym"),
    )


class CatalogAttributePresence(Base):
    __tablename__ = "catalog_attribute_presence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_attribute_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_attribute.id", ondelete="CASCADE"),
        nullable=False,
    )
    system: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    api_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        CheckConstraint(
            _check_in("system", CATALOG_SYSTEMS), name="ck_catalog_attribute_presence_system"
        ),
        CheckConstraint(
            _check_in("status", CATALOG_PRESENCE_STATUSES),
            name="ck_catalog_attribute_presence_status",
        ),
        UniqueConstraint(
            "catalog_attribute_id", "system", name="uq_catalog_attribute_presence"
        ),
        Index("ix_catalog_attribute_presence_attr", "catalog_attribute_id"),
    )


class CatalogRelationship(Base):
    __tablename__ = "catalog_relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_entity_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_entity.id", ondelete="CASCADE"),
        nullable=False,
    )
    cardinality: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        CheckConstraint(
            _check_in("cardinality", CATALOG_RELATIONSHIP_CARDINALITIES),
            name="ck_catalog_relationship_cardinality",
        ),
        CheckConstraint(
            _check_in("role", CATALOG_RELATIONSHIP_ROLES),
            name="ck_catalog_relationship_role",
        ),
        Index("ix_catalog_relationship_source", "source_entity_id"),
        Index("ix_catalog_relationship_target", "target_entity_id"),
    )


class CatalogRelationshipPresence(Base):
    __tablename__ = "catalog_relationship_presence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_relationship_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("catalog_relationship.id", ondelete="CASCADE"),
        nullable=False,
    )
    system: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        CheckConstraint(
            _check_in("system", CATALOG_SYSTEMS),
            name="ck_catalog_relationship_presence_system",
        ),
        CheckConstraint(
            _check_in("status", CATALOG_PRESENCE_STATUSES),
            name="ck_catalog_relationship_presence_status",
        ),
        UniqueConstraint(
            "catalog_relationship_id",
            "system",
            name="uq_catalog_relationship_presence",
        ),
        Index(
            "ix_catalog_relationship_presence_rel", "catalog_relationship_id"
        ),
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
