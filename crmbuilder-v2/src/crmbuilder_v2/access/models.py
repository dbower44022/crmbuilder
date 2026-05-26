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
    CLOSE_OUT_PAYLOAD_STATUSES,
    CONVERSATION_STATUSES,
    CRM_CANDIDATE_STATUSES,
    DECISION_STATUSES,
    DEPOSIT_EVENT_OUTCOMES,
    DOMAIN_STATUSES,
    ENTITY_STATUSES,
    ENTITY_TYPES,
    FIELD_STATUSES,
    FIELD_TYPES,
    MANUAL_CONFIG_CATEGORIES,
    MANUAL_CONFIG_STATUSES,
    PERSONA_STATUSES,
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
    PROCESS_CLASSIFICATIONS,
    REFERENCE_BOOK_KINDS,
    REFERENCE_BOOK_STATUSES,
    REFERENCE_RELATIONSHIPS,
    REQUIREMENT_PRIORITIES,
    REQUIREMENT_STATUSES,
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
    SESSION_STATUSES,
    TEST_SPEC_RUN_OUTCOMES,
    TEST_SPEC_STATUSES,
    WORK_TICKET_KINDS,
    WORK_TICKET_STATUSES,
    WORKSTREAM_STATUSES,
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


class Domain(Base):
    """Methodology entity — one Phase 1 Domain Inventory member.

    First of the four methodology entity types (UI v0.4). Per
    ``domain.md`` the schema follows the parent-prefix field-naming
    convention: every column is prefixed ``domain_``. The primary key
    is the prefixed-string identifier ``domain_identifier`` (format
    ``DOM-NNN``) — there is no integer surrogate ``id`` column.
    """

    __tablename__ = "domains"

    domain_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    domain_name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    domain_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    domain_description: Mapped[str] = mapped_column(Text, nullable=False)
    domain_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    domain_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    domain_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^DOM-\d{3}$`` expressed as a SQLite GLOB pattern — GLOB
        # anchors the whole string, so this admits exactly ``DOM-`` plus
        # three digits.
        CheckConstraint(
            "domain_identifier GLOB 'DOM-[0-9][0-9][0-9]'",
            name="ck_domain_identifier_format",
        ),
        CheckConstraint(
            _check_in("domain_status", DOMAIN_STATUSES),
            name="ck_domain_status",
        ),
        Index("ix_domains_domain_status", "domain_status"),
        Index("ix_domains_domain_deleted_at", "domain_deleted_at"),
    )


class Entity(Base):
    """Methodology entity — one CRM-modeled noun the client uses.

    Second of the four methodology entity types (UI v0.4 slice C). Per
    ``entity.md`` the schema follows the parent-prefix field-naming
    convention: every column is prefixed ``entity_``. The primary key
    is the prefixed-string identifier ``entity_identifier`` (format
    ``ENT-NNN``) — there is no integer surrogate ``id`` column. Domain
    affiliations are NOT FK columns here; they live in the ``refs``
    table as ``entity_scopes_to_domain`` references.
    """

    __tablename__ = "entities"

    entity_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    entity_description: Mapped[str] = mapped_column(Text, nullable=False)
    entity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    entity_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    entity_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^ENT-\d{3}$`` expressed as a SQLite GLOB pattern — GLOB
        # anchors the whole string, so this admits exactly ``ENT-`` plus
        # three digits.
        CheckConstraint(
            "entity_identifier GLOB 'ENT-[0-9][0-9][0-9]'",
            name="ck_entity_identifier_format",
        ),
        CheckConstraint(
            _check_in("entity_status", ENTITY_STATUSES),
            name="ck_entity_status",
        ),
        Index("ix_entities_entity_status", "entity_status"),
        Index("ix_entities_entity_deleted_at", "entity_deleted_at"),
    )


class Field(Base):
    """Methodology entity — one attribute on one CRM-modeled entity.

    Sixth methodology entity type (v0.5+, PI-004 first slice). Per
    ``field.md`` §3.2 the schema follows the parent-prefix
    field-naming convention: every column is prefixed ``field_``. The
    primary key is the prefixed-string identifier ``field_identifier``
    (format ``FLD-NNN``) — there is no integer surrogate ``id`` column.

    Parent-entity affiliation is captured via the ``refs`` table as a
    ``field_belongs_to_entity`` edge, NOT an FK column on this table
    (per DEC-249). The 1:1-mandatory cardinality is enforced by the
    access layer rather than the schema layer.

    ``field_previous_parent_entity_identifier`` is the stash column
    supporting the §3.4.6 soft-delete/restore atomicity story: on
    DELETE the access layer hard-deletes the
    ``field_belongs_to_entity`` edge (refs has no ``deleted_at``
    column) and stashes the target entity's identifier here; on
    POST /restore the column value is read to recreate the edge
    atomically with clearing ``field_deleted_at``.
    """

    __tablename__ = "fields"

    field_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_description: Mapped[str] = mapped_column(Text, nullable=False)
    field_type: Mapped[str] = mapped_column(String(32), nullable=False)
    field_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    field_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    field_previous_parent_entity_identifier: Mapped[str | None] = (
        mapped_column(String(32), nullable=True)
    )
    field_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    field_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    field_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^FLD-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            "field_identifier GLOB 'FLD-[0-9][0-9][0-9]'",
            name="ck_field_identifier_format",
        ),
        CheckConstraint(
            _check_in("field_status", FIELD_STATUSES),
            name="ck_field_status",
        ),
        CheckConstraint(
            _check_in("field_type", FIELD_TYPES),
            name="ck_field_type",
        ),
        CheckConstraint(
            "field_required IN (0, 1)",
            name="ck_field_required_boolean",
        ),
        Index("ix_fields_field_status", "field_status"),
        Index("ix_fields_field_type", "field_type"),
        Index("ix_fields_field_deleted_at", "field_deleted_at"),
    )


class Requirement(Base):
    """Methodology entity — one testable statement of what the CRM must do.

    PI-004 cohort deliverable per ``requirement.md`` v1.0. Parent-prefix
    field naming; primary key is the prefixed-string identifier
    ``requirement_identifier`` (``REQ-NNN``). All five outbound
    relationships (domain affiliation, entity coverage, field coverage,
    process realization, test-spec verification) live in ``refs`` as
    distinct relationship kinds, not FK columns.

    Priority transitions are unconstrained — any of the four MoSCoW
    values may freely follow any other (spec §3.2.3 / §3.4.3). Status
    transitions use the one-way propose-verify gate inherited from
    ``domain`` and ``entity``.
    """

    __tablename__ = "requirements"

    requirement_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    requirement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requirement_description: Mapped[str] = mapped_column(Text, nullable=False)
    requirement_acceptance_summary: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    requirement_priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default="should"
    )
    requirement_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    requirement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    requirement_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    requirement_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^REQ-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            "requirement_identifier GLOB 'REQ-[0-9][0-9][0-9]'",
            name="ck_requirement_identifier_format",
        ),
        CheckConstraint(
            _check_in("requirement_status", REQUIREMENT_STATUSES),
            name="ck_requirement_status",
        ),
        CheckConstraint(
            _check_in("requirement_priority", REQUIREMENT_PRIORITIES),
            name="ck_requirement_priority",
        ),
        Index(
            "ix_requirements_requirement_status", "requirement_status"
        ),
        Index(
            "ix_requirements_requirement_priority", "requirement_priority"
        ),
        Index(
            "ix_requirements_requirement_deleted_at",
            "requirement_deleted_at",
        ),
    )


class Persona(Base):
    """Methodology entity — one human role or actor in the client's organization.

    Fifth methodology entity type (v0.5+, PI-003). Per ``persona.md``
    §3.2 the schema follows the parent-prefix field-naming convention:
    every column is prefixed ``persona_``. The primary key is the
    prefixed-string identifier ``persona_identifier`` (format
    ``PER-NNN``) — there is no integer surrogate ``id`` column.

    No FK column — ``persona_scopes_to_domain`` and
    ``persona_realized_as_entity`` live in the ``refs`` table.
    """

    __tablename__ = "personas"

    persona_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    persona_name: Mapped[str] = mapped_column(String(255), nullable=False)
    persona_role_summary: Mapped[str] = mapped_column(Text, nullable=False)
    persona_responsibilities: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    persona_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    persona_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    persona_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    persona_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    persona_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^PER-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            "persona_identifier GLOB 'PER-[0-9][0-9][0-9]'",
            name="ck_persona_identifier_format",
        ),
        CheckConstraint(
            _check_in("persona_status", PERSONA_STATUSES),
            name="ck_persona_status",
        ),
        Index("ix_personas_persona_status", "persona_status"),
        Index("ix_personas_persona_deleted_at", "persona_deleted_at"),
    )


class Process(Base):
    """Methodology entity — one Phase 1 Prioritized Backbone member.

    Third of the four methodology entity types (UI v0.4 slice D). Per
    ``process.md`` the schema follows the parent-prefix field-naming
    convention: every column is prefixed ``process_``. The primary key
    is the prefixed-string identifier ``process_identifier`` (format
    ``PROC-NNN``) — there is no integer surrogate ``id`` column.

    Two structural deviations from ``domain`` / ``entity``: there is no
    ``process_status`` field (the four-value ``process_classification``
    enum carries the lifecycle per DEC-056), and ``process`` carries a
    direct scalar FK column ``process_domain_identifier`` (each process
    belongs to exactly one domain — FK existence is validated at the
    access layer, not via a SQL FOREIGN KEY constraint, matching v2's
    soft-FK convention). Process-to-process handoffs live in the
    ``refs`` table as ``process_hands_off_to_process`` references.

    As of v0.8 (PI-005, ``process-v2.md`` §3.2.2) the schema also
    carries six Phase 3 content fields — ``process_steps``,
    ``process_triggers``, ``process_outcomes``, ``process_edge_cases``,
    ``process_frequency``, ``process_duration_estimate``. All six are
    plain TEXT, nullable, default NULL; existing v0.4 records acquired
    NULL on migration. No CHECK constraints — the methodology defers
    structured representations to v0.7+ per spec §3.2.2.
    """

    __tablename__ = "processes"

    process_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    process_name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_domain_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    process_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    process_classification: Mapped[str] = mapped_column(
        String(20), nullable=False, default="unclassified"
    )
    process_classification_rationale: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    process_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 3 content fields (v0.8, PI-005, process-v2.md §3.2.2). All
    # six are plain TEXT, nullable, default NULL; existing v0.4 records
    # acquired NULL on migration. No CHECK constraints — the
    # methodology defers structured representations to v0.7+.
    process_steps: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_triggers: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_outcomes: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_edge_cases: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_frequency: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_duration_estimate: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    process_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    process_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    process_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^PROC-\d{3}$`` and ``^DOM-\d{3}$`` expressed as SQLite GLOB
        # patterns — GLOB anchors the whole string.
        CheckConstraint(
            "process_identifier GLOB 'PROC-[0-9][0-9][0-9]'",
            name="ck_process_identifier_format",
        ),
        CheckConstraint(
            "process_domain_identifier GLOB 'DOM-[0-9][0-9][0-9]'",
            name="ck_process_domain_identifier_format",
        ),
        CheckConstraint(
            _check_in("process_classification", PROCESS_CLASSIFICATIONS),
            name="ck_process_classification",
        ),
        Index("ix_processes_process_classification", "process_classification"),
        Index(
            "ix_processes_process_domain_identifier",
            "process_domain_identifier",
        ),
        Index("ix_processes_process_deleted_at", "process_deleted_at"),
    )


class ManualConfig(Base):
    """Methodology entity — one discrete CRM-config item the deploy cannot apply.

    Eighth methodology entity type (v0.5+, PI-004 cohort) per
    ``manual_config.md`` v1.0. Captures the items the operator must
    configure by hand in the live CRM after deploy (saved views,
    duplicate checks, workflows, deferred-options enums, role
    permissions, dynamic logic, other). Parent-prefix field naming
    convention (DEC-046); primary key is the prefixed-string
    identifier ``manual_config_identifier`` (``MCF-NNN``) — no integer
    surrogate ``id`` column.

    **Four-status lifecycle, not three.** Spec §3.4 deviates from the
    cross-spec `candidate / confirmed / deferred` default by adding a
    terminal `completed` reachable only from `confirmed`. Completion-
    field nullability is conditional on status, enforced at the access
    layer per spec §3.5.3 (cross-field invariant: both
    ``manual_config_completed_at`` and ``manual_config_completed_by``
    required when status transitions into ``completed``; storage
    permits null on either to keep the conditional out of SQLite).

    The four outbound relationship kinds (``manual_config_scopes_to_domain``,
    ``manual_config_touches_entity``, ``manual_config_touches_field``,
    ``manual_config_realizes_requirement``) live in the ``refs`` table
    per §3.3.1 — no FK columns on this table.
    """

    __tablename__ = "manual_configs"

    manual_config_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    manual_config_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    manual_config_category: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    manual_config_description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    manual_config_instructions: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    manual_config_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    manual_config_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    manual_config_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    manual_config_completed_by: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    manual_config_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    manual_config_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    manual_config_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^MCF-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            "manual_config_identifier GLOB 'MCF-[0-9][0-9][0-9]'",
            name="ck_manual_config_identifier_format",
        ),
        CheckConstraint(
            _check_in("manual_config_status", MANUAL_CONFIG_STATUSES),
            name="ck_manual_config_status",
        ),
        CheckConstraint(
            _check_in("manual_config_category", MANUAL_CONFIG_CATEGORIES),
            name="ck_manual_config_category",
        ),
        Index(
            "ix_manual_configs_manual_config_status",
            "manual_config_status",
        ),
        Index(
            "ix_manual_configs_manual_config_category",
            "manual_config_category",
        ),
        Index(
            "ix_manual_configs_manual_config_deleted_at",
            "manual_config_deleted_at",
        ),
    )


class TestSpec(Base):
    """Methodology entity — one verification specification (test).

    Ninth methodology entity type (v0.5+, PI-004 cohort closer) per
    ``test_spec.md`` v1.0. Hosts the verification-spec content (setup
    / steps / expected) plus a snapshot of the most recent execution
    outcome. Parent-prefix field naming convention (DEC-046); primary
    key is the prefixed-string identifier ``test_spec_identifier``
    (``TST-NNN``) — no integer surrogate ``id`` column.

    **Dual-axis state per §3.4.3 — two enums on this row, not one.**

    * ``test_spec_status`` ∈ ``{candidate, confirmed, deferred}`` — the
      methodology lifecycle. Restricted transitions per
      :data:`TEST_SPEC_STATUS_TRANSITIONS` (one-way propose-verify gate;
      same shape as ``domain`` and ``entity``).
    * ``test_spec_last_run_outcome`` ∈ ``{not_run, passing, failing,
      skipped}`` — the snapshot of the most recent execution result.
      **Unrestricted transitions** — outcomes are observational, not
      decisional; any value may move to any other. The §3.4.4
      cross-field invariant (``last_run_at`` populated whenever outcome
      is a run state; cleared back to null when outcome resets to
      ``not_run``) is enforced at the access layer, not in SQL.

    **Snapshot-only execution shape (§3.8.3 deferred).** Only the most
    recent run's outcome / timestamp / notes are captured on this row.
    Full historical execution log is a v0.6+ planning item (separate
    ``test_run`` entity type with a ``test_run_executes_test_spec``
    edge or FK pointer).

    The three outbound relationship kinds (``test_spec_touches_entity``,
    ``test_spec_touches_field``, ``test_spec_exercises_process``) live
    in the ``refs`` table per §3.3.1 — no FK columns on this table. The
    inbound ``requirement_verified_by_test_spec`` kind is registered by
    ``requirement.md``, not here, per the once-per-kind rule
    (CLAUDE.md line 48).
    """

    __tablename__ = "test_specs"

    test_spec_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    test_spec_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    test_spec_description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    test_spec_setup: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    test_spec_steps: Mapped[str] = mapped_column(Text, nullable=False)
    test_spec_expected: Mapped[str] = mapped_column(Text, nullable=False)
    test_spec_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    test_spec_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    test_spec_last_run_outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default="not_run"
    )
    test_spec_last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    test_spec_last_run_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    test_spec_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    test_spec_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    test_spec_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^TST-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            "test_spec_identifier GLOB 'TST-[0-9][0-9][0-9]'",
            name="ck_test_spec_identifier_format",
        ),
        CheckConstraint(
            _check_in("test_spec_status", TEST_SPEC_STATUSES),
            name="ck_test_spec_status",
        ),
        CheckConstraint(
            _check_in(
                "test_spec_last_run_outcome", TEST_SPEC_RUN_OUTCOMES
            ),
            name="ck_test_spec_last_run_outcome",
        ),
        Index(
            "ix_test_specs_test_spec_status",
            "test_spec_status",
        ),
        Index(
            "ix_test_specs_test_spec_last_run_outcome",
            "test_spec_last_run_outcome",
        ),
        Index(
            "ix_test_specs_test_spec_deleted_at",
            "test_spec_deleted_at",
        ),
    )


class CrmCandidate(Base):
    """Methodology entity — one Phase 1 Initial CRM Candidate Set member.

    Fourth and final of the four methodology entity types (UI v0.4
    slice E). Per ``crm_candidate.md`` the schema follows the
    parent-prefix field-naming convention: every column is prefixed
    ``crm_candidate_``. The primary key is the prefixed-string
    identifier ``crm_candidate_identifier`` (format ``CRM-NNN``) —
    there is no integer surrogate ``id`` column. The four-status
    enum (``active`` / ``selected`` / ``declined`` / ``removed``)
    has three terminal states; the singleton-``selected`` constraint
    per spec section 3.4.3 is enforced exclusively at the access layer.
    """

    __tablename__ = "crm_candidates"

    crm_candidate_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    crm_candidate_name: Mapped[str] = mapped_column(String(255), nullable=False)
    crm_candidate_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    crm_candidate_fit_reason: Mapped[str] = mapped_column(Text, nullable=False)
    crm_candidate_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    crm_candidate_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    crm_candidate_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    crm_candidate_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^CRM-\d{3}$`` expressed as a SQLite GLOB pattern — GLOB
        # anchors the whole string, so this admits exactly ``CRM-`` plus
        # three digits.
        CheckConstraint(
            "crm_candidate_identifier GLOB 'CRM-[0-9][0-9][0-9]'",
            name="ck_crm_candidate_identifier_format",
        ),
        CheckConstraint(
            _check_in("crm_candidate_status", CRM_CANDIDATE_STATUSES),
            name="ck_crm_candidate_status",
        ),
        Index(
            "ix_crm_candidates_crm_candidate_status",
            "crm_candidate_status",
        ),
        Index(
            "ix_crm_candidates_crm_candidate_deleted_at",
            "crm_candidate_deleted_at",
        ),
    )


# ---------------------------------------------------------------------------
# Governance entities (UI v0.7). Six new entity types making the project's
# organizing units, workflow files, and apply events queryable as governance
# objects. Each follows the parent-prefix field-naming convention (DEC-046)
# and uses its prefixed-string identifier as the primary key (no integer
# surrogate), matching the v0.4 methodology-entity precedent. See the
# per-entity schema specifications under governance-schema-specs/.
# ---------------------------------------------------------------------------


class Workstream(Base):
    """Governance entity — one coherent line of related conversations.

    First of six governance entity types (UI v0.7). Five-status workflow
    lifecycle with truly-terminal terminals; four per-status lifecycle
    timestamps. Parent-child relationships to conversations and the
    master-plan reference book live in ``refs``, not as FK columns.
    """

    __tablename__ = "workstreams"

    workstream_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    workstream_name: Mapped[str] = mapped_column(String(255), nullable=False)
    workstream_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="planned"
    )
    workstream_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    workstream_description: Mapped[str] = mapped_column(Text, nullable=False)
    workstream_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workstream_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    workstream_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    workstream_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workstream_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workstream_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workstream_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workstream_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "workstream_identifier GLOB 'WS-[0-9][0-9][0-9]'",
            name="ck_workstream_identifier_format",
        ),
        CheckConstraint(
            _check_in("workstream_status", WORKSTREAM_STATUSES),
            name="ck_workstream_status",
        ),
        Index("ix_workstreams_workstream_status", "workstream_status"),
        Index("ix_workstreams_workstream_deleted_at", "workstream_deleted_at"),
    )


class Conversation(Base):
    """Governance entity — one unit of conversational work through its lifecycle.

    Second of six governance entity types (UI v0.7). Seven-status workflow
    lifecycle (forward-only planning line plus three terminals); six
    per-status lifecycle timestamps. Workstream membership, session linkage,
    kickoff linkage, sequencing, and supersession all live in ``refs``.
    """

    __tablename__ = "conversations"

    conversation_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    conversation_title: Mapped[str] = mapped_column(String(255), nullable=False)
    conversation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )
    conversation_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_description: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    conversation_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    conversation_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_kickoff_drafted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "conversation_identifier GLOB 'CONV-[0-9][0-9][0-9]'",
            name="ck_conversation_identifier_format",
        ),
        CheckConstraint(
            _check_in("conversation_status", CONVERSATION_STATUSES),
            name="ck_conversation_status",
        ),
        Index("ix_conversations_conversation_status", "conversation_status"),
        Index(
            "ix_conversations_conversation_deleted_at",
            "conversation_deleted_at",
        ),
    )


class ReferenceBook(Base):
    """Governance entity — one long-lived versioned reference document.

    Third of six governance entity types (UI v0.7). Documentary-shaped
    three-status lifecycle with base timestamps only (no per-status
    timestamps, per DEC-137). Carries denormalized current-version pointer
    fields kept in sync with the ``reference_book_versions`` child table.
    """

    __tablename__ = "reference_books"

    reference_book_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    reference_book_title: Mapped[str] = mapped_column(String(255), nullable=False)
    reference_book_description: Mapped[str] = mapped_column(Text, nullable=False)
    reference_book_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_book_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    reference_book_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    reference_book_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    reference_book_current_version_label: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    reference_book_current_version_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reference_book_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    reference_book_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    reference_book_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    versions: Mapped[list[ReferenceBookVersion]] = relationship(
        "ReferenceBookVersion",
        back_populates="reference_book",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "reference_book_identifier GLOB 'RB-[0-9][0-9][0-9]'",
            name="ck_reference_book_identifier_format",
        ),
        CheckConstraint(
            _check_in("reference_book_kind", REFERENCE_BOOK_KINDS),
            name="ck_reference_book_kind",
        ),
        CheckConstraint(
            _check_in("reference_book_status", REFERENCE_BOOK_STATUSES),
            name="ck_reference_book_status",
        ),
        Index("ix_reference_books_reference_book_kind", "reference_book_kind"),
        Index(
            "ix_reference_books_reference_book_status", "reference_book_status"
        ),
        Index(
            "ix_reference_books_reference_book_deleted_at",
            "reference_book_deleted_at",
        ),
    )


class ReferenceBookVersion(Base):
    """Child of ``reference_books`` — one known version of a reference book.

    Per ``reference_book.md`` section 3.2.7. Version rows are addressed by
    ``(reference_book_identifier, reference_book_version_label)``, not by a
    prefixed identifier. The parent's denormalized current-version pointers
    track the row with the newest ``reference_book_version_date``. The FK
    references the parent's prefixed-string PK (the v0.4 PK convention has
    no integer surrogate on governance tables) with ON DELETE CASCADE.
    """

    __tablename__ = "reference_book_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reference_book_identifier: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("reference_books.reference_book_identifier", ondelete="CASCADE"),
        nullable=False,
    )
    reference_book_version_label: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    reference_book_version_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reference_book_version_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    reference_book_version_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    reference_book: Mapped[ReferenceBook] = relationship(
        "ReferenceBook", back_populates="versions"
    )

    __table_args__ = (
        UniqueConstraint(
            "reference_book_identifier",
            "reference_book_version_label",
            name="uq_reference_book_version",
        ),
        Index(
            "ix_reference_book_versions_parent", "reference_book_identifier"
        ),
    )


class WorkTicket(Base):
    """Governance entity — one single-use seed document (kickoff/prompt).

    Fourth of six governance entity types (UI v0.7). Five-status workflow
    lifecycle (drafted → ready → consumed plus two terminals); four
    per-status timestamps. The defining inbound consumption edge from a
    conversation lives in ``refs`` and is single-use (at most one).
    """

    __tablename__ = "work_tickets"

    work_ticket_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    work_ticket_title: Mapped[str] = mapped_column(String(255), nullable=False)
    work_ticket_description: Mapped[str] = mapped_column(Text, nullable=False)
    work_ticket_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_ticket_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    work_ticket_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="drafted"
    )
    work_ticket_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    work_ticket_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    work_ticket_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    work_ticket_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_ticket_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_ticket_consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_ticket_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_ticket_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "work_ticket_identifier GLOB 'WT-[0-9][0-9][0-9]'",
            name="ck_work_ticket_identifier_format",
        ),
        CheckConstraint(
            _check_in("work_ticket_kind", WORK_TICKET_KINDS),
            name="ck_work_ticket_kind",
        ),
        CheckConstraint(
            _check_in("work_ticket_status", WORK_TICKET_STATUSES),
            name="ck_work_ticket_status",
        ),
        Index("ix_work_tickets_work_ticket_kind", "work_ticket_kind"),
        Index("ix_work_tickets_work_ticket_status", "work_ticket_status"),
        Index(
            "ix_work_tickets_work_ticket_deleted_at", "work_ticket_deleted_at"
        ),
    )


class CloseOutPayload(Base):
    """Governance entity — one single-use state-write package.

    Fifth of six governance entity types (UI v0.7). Five-status workflow
    lifecycle (drafted → ready → applied plus two terminals); four
    per-status timestamps. Must carry exactly one outbound
    ``close_out_payload_produced_by_conversation`` edge at all statuses.
    The ``ready → applied`` transition fires on the first inbound success
    ``deposit_event_applies_close_out_payload`` edge (DEC-158).
    """

    __tablename__ = "close_out_payloads"

    close_out_payload_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    close_out_payload_title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    close_out_payload_description: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    close_out_payload_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    close_out_payload_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="drafted"
    )
    close_out_payload_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    close_out_payload_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    close_out_payload_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    close_out_payload_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_out_payload_ready_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_out_payload_applied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_out_payload_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    close_out_payload_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "close_out_payload_identifier GLOB 'COP-[0-9][0-9][0-9]'",
            name="ck_close_out_payload_identifier_format",
        ),
        CheckConstraint(
            _check_in("close_out_payload_status", CLOSE_OUT_PAYLOAD_STATUSES),
            name="ck_close_out_payload_status",
        ),
        Index(
            "ix_close_out_payloads_close_out_payload_status",
            "close_out_payload_status",
        ),
        Index(
            "ix_close_out_payloads_close_out_payload_deleted_at",
            "close_out_payload_deleted_at",
        ),
    )


class DepositEvent(Base):
    """Governance entity — one durable record of a close_out_payload apply.

    Sixth of six governance entity types (UI v0.7). Born-terminal
    append-only: no ``_updated_at``, no ``_deleted_at``, one ``_created_at``
    timestamp. Carries an ``_outcome`` enum (``success`` | ``failure``)
    rather than a transitioning ``_status``. Three diagnostic JSON fields.
    Created exclusively via POST; never updated or deleted.
    """

    __tablename__ = "deposit_events"

    deposit_event_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    deposit_event_title: Mapped[str] = mapped_column(String(255), nullable=False)
    deposit_event_description: Mapped[str] = mapped_column(Text, nullable=False)
    deposit_event_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    deposit_event_records_summary: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )
    deposit_event_error_info: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )
    deposit_event_apply_context: Mapped[dict] = mapped_column(JSON, nullable=False)
    deposit_event_log_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    deposit_event_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "deposit_event_identifier GLOB 'DEP-[0-9][0-9][0-9]'",
            name="ck_deposit_event_identifier_format",
        ),
        CheckConstraint(
            _check_in("deposit_event_outcome", DEPOSIT_EVENT_OUTCOMES),
            name="ck_deposit_event_outcome",
        ),
        Index("ix_deposit_events_deposit_event_outcome", "deposit_event_outcome"),
        Index(
            "ix_deposit_events_deposit_event_created_at",
            "deposit_event_created_at",
        ),
    )


class Commit(Base):
    """Governance entity — one git-commit-as-governance-record (v0.8, PI-029).

    Seventh governance entity type, the first under the Code Change Lifecycle
    methodology workstream. Captures one commit produced by a conversation,
    attributed to that conversation via ``commit_conversation_id`` (FK
    deviation from DEC-124 on frequency-justified-denormalization grounds;
    see DEC-199 and commit.md §3.2.4 / §3.3).

    Documentary-shaped lifecycle, **status-free** — refines DEC-137 per
    DEC-198. No ``commit_status``, no transitions; soft-delete-with-restore
    is the only state-change mechanism.

    ``commit_committed_at`` is TEXT (not DateTime) so the ISO 8601 offset
    is preserved verbatim — commit.md §3.2.5.
    ``commit_parent_shas`` is a JSON-array column (0/1/2 SHA strings) — the
    first such column on a governance entity table; commit.md §1 establishes
    the cross-spec precedent for variable-cardinality scalar lists.
    """

    __tablename__ = "commits"

    commit_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    commit_sha: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    commit_message_first_line: Mapped[str] = mapped_column(Text, nullable=False)
    commit_message_full: Mapped[str] = mapped_column(Text, nullable=False)
    commit_author_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_author_email: Mapped[str] = mapped_column(String(255), nullable=False)
    # ISO 8601 with explicit offset preserved verbatim (committer-local
    # time). NOT normalized to UTC.
    commit_committed_at: Mapped[str] = mapped_column(Text, nullable=False)
    commit_repository: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_branch: Mapped[str] = mapped_column(
        String(255), nullable=False, default="main"
    )
    # JSON array of 0/1/2 SHA strings — empty for initial commit, single
    # for normal commit, two for merge commit. Per commit.md §3.2.4.
    commit_parent_shas: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    commit_files_changed_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    # Soft FK to conversations.conversation_identifier — access-layer
    # validated, not SQL-level FK per V2 convention. Direct FK column on
    # this dense entity per DEC-199's frequency-justified deviation from
    # DEC-124's references-edge precedent.
    commit_conversation_id: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    commit_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    commit_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    commit_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            "commit_identifier GLOB 'CM-[0-9][0-9][0-9][0-9]'",
            name="ck_commit_identifier_format",
        ),
        # Lowercase 40-char hex SHA-1. SHA-256 widening anticipated in
        # commit.md §3.8.2.
        CheckConstraint(
            "LENGTH(commit_sha) = 40 AND "
            "commit_sha NOT GLOB '*[^0-9a-f]*'",
            name="ck_commit_sha_format",
        ),
        CheckConstraint(
            "commit_files_changed_count >= 0",
            name="ck_commit_files_changed_count_nonneg",
        ),
        Index("ix_commits_commit_conversation_id", "commit_conversation_id"),
        Index("ix_commits_commit_repository", "commit_repository"),
        Index("ix_commits_commit_committed_at", "commit_committed_at"),
        Index("ix_commits_commit_deleted_at", "commit_deleted_at"),
    )


class Reference(Base):
    """Universal polymorphic reference between two records (DEC-006)."""

    __tablename__ = "refs"  # avoid SQL reserved word "references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # v0.7: prefixed external identifier (REF-NNNN) so individual reference
    # rows can be targeted by deposit_event `deposit_event_wrote_record`
    # back-references. Server-assigned on insert; back-filled by id order for
    # existing rows (migration 0011). Nullable at the column level because the
    # back-fill runs after the column is added; the access layer always sets it.
    reference_identifier: Mapped[str | None] = mapped_column(
        String(16), nullable=True, unique=True
    )
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
        CheckConstraint(
            "reference_identifier IS NULL OR "
            "reference_identifier GLOB 'REF-[0-9][0-9][0-9][0-9]'",
            name="ck_ref_reference_identifier_format",
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
