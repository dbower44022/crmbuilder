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
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql.expression import ColumnElement

from crmbuilder_v2.access.vocab import (
    AGENT_PROFILE_TIERS,
    AREA_REOPEN_STATUSES,
    ASSOCIATION_CARDINALITIES,
    ASSOCIATION_STATUSES,
    AUTOMATION_STATUSES,
    AUTOMATION_TRIGGERS,
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
    CHANGE_LOG_ENTITY_TYPES,
    CHANGE_LOG_OPERATIONS,
    CLOSE_OUT_PAYLOAD_STATUSES,
    CONVERSATION_STATUSES,
    CRM_CANDIDATE_STATUSES,
    DECISION_STATUSES,
    DEDUP_ON_MATCH,
    DEDUP_RULE_STATUSES,
    DEPOSIT_EVENT_KINDS,
    DEPOSIT_EVENT_OUTCOMES,
    DOMAIN_STATUSES,
    ENTITY_KINDS,
    ENTITY_STATUSES,
    ENTITY_TYPES,
    EVIDENCE_SUBJECT_TYPES,
    EXECUTION_MODES,
    FIELD_STATUSES,
    FIELD_TYPES,
    FILTERED_TAB_STATUSES,
    FINDING_RESOLUTION_METHODS,
    FINDING_SEVERITIES,
    FINDING_STATUSES,
    FINDING_TYPES,
    INSTANCE_AUTH_METHODS,
    INSTANCE_MEMBERSHIP_MEMBER_TYPES,
    INSTANCE_MEMBERSHIP_STATES,
    INSTANCE_ROLES,
    INSTANCE_STATUSES,
    INSTANCE_VENDORS,
    LAYOUT_STATUSES,
    LAYOUT_TYPES,
    LEARNING_CATEGORIES,
    LEARNING_STATUSES,
    LEARNING_TIERS,
    MANUAL_CONFIG_CATEGORIES,
    MANUAL_CONFIG_STATUSES,
    MESSAGE_TEMPLATE_STATUSES,
    MIGRATION_MAPPING_DISPOSITIONS,
    MIGRATION_MAPPING_LEVELS,
    MIGRATION_MAPPING_STATUSES,
    OVERRIDE_SUBJECT_TYPES,
    PERSONA_STATUSES,
    PLANNING_ITEM_STATUSES,
    PLANNING_ITEM_TYPES,
    PROCESS_CLASSIFICATIONS,
    PROJECT_STATUSES,
    RECONCILIATION_CONFLICT_STATUSES,
    RECONCILIATION_CONFLICT_TYPES,
    REFERENCE_BOOK_KINDS,
    REFERENCE_BOOK_STATUSES,
    REFERENCE_RELATIONSHIPS,
    REGISTRY_STATUSES,
    RELEASE_STATUSES,
    REOPEN_APPROVAL_TIERS,
    REQUIREMENT_ORIGINS,
    REQUIREMENT_PRIORITIES,
    REQUIREMENT_REVIEW_STATES,
    REQUIREMENT_STATUSES,
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
    ROLE_STATUSES,
    RULE_EFFECTS,
    RULE_ENFORCEMENT_MODES,
    RULE_STATUSES,
    RULE_SUBJECT_TYPES,
    SERVICE_STATUSES,
    SESSION_MEDIUMS,
    SESSION_STATUSES,
    SKILL_KINDS,
    TARGET_ENGINES,
    TEAM_STATUSES,
    TERM_STATUSES,
    TEST_SPEC_RUN_OUTCOMES,
    TEST_SPEC_STATUSES,
    VERSIONED_ARTIFACT_TYPES,
    VIEW_STATUSES,
    WORK_TASK_STATUSES,
    WORK_TICKET_KINDS,
    WORK_TICKET_STATUSES,
    WORKSTREAM_PHASE_TYPES,
    WORKSTREAM_STATUSES,
    _check_in,
)

# PI-alpha (D1): JSON columns use JSONB on Postgres and plain JSON everywhere
# else (the still-SQLite meta DB, legacy SQLite installs, and the unified-DB
# migration source). A single shared ``TypeEngine`` instance per variant is
# safe — SQLAlchemy type objects are immutable descriptors reused across
# columns. ``none_as_null`` is load-bearing on the work-area-labels column (a
# Python ``None`` must persist as SQL NULL, not the JSON text ``'null'``); it is
# preserved on both sides of the variant.
JSONColumn = JSON().with_variant(JSONB(), "postgresql")
JSONColumnNoneAsNull = JSON(none_as_null=True).with_variant(
    JSONB(none_as_null=True), "postgresql"
)


# --- PI-alpha (D1): dialect-aware identifier-format CHECK constraints ---
#
# The identifier-format CHECKs were hand-written as SQLite ``GLOB`` predicates
# (e.g. ``session_identifier GLOB 'SES-[0-9][0-9][0-9]'``). ``GLOB`` is a
# SQLite-only operator — Postgres has no GLOB, so ``create_all`` against PG
# fails. These two custom constructs render the **byte-identical GLOB form on
# SQLite** (so create_all on SQLite is unchanged and existing SQLite DBs, whose
# CHECK text is already baked in, are untouched) and the equivalent **POSIX
# regex (``~``) form on Postgres**.


class _IdentifierFormatCheck(ColumnElement):
    """An identifier-format CHECK predicate, dialect-rendered.

    ``prefixes`` are OR'd together (the session/conversation rows admit two);
    ``digits`` is the trailing digit count (3 for most, 4 for ``CM-``/``REF-``).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(
        self, column_name: str, prefixes, digits: int = 3, allow_null: bool = False
    ) -> None:
        self.column_name = column_name
        self.prefixes = tuple(prefixes)
        self.digits = digits
        # ``allow_null`` prepends ``<col> IS NULL OR`` (e.g. server-assigned
        # REF-NNNN, NULL before assignment). Folded into the rendered predicate
        # — rather than wrapping the element in ``sql.or_`` — because nesting a
        # boolean custom element inside ``and_``/``or_`` makes SQLAlchemy's
        # SQLite compiler append a spurious ``= 1`` boolean coercion.
        self.allow_null = allow_null


@compiles(_IdentifierFormatCheck, "sqlite")
def _render_ident_sqlite(element, compiler, **kw) -> str:
    cls = "[0-9]" * element.digits
    pred = " OR ".join(
        f"{element.column_name} GLOB '{p}-{cls}'" for p in element.prefixes
    )
    if element.allow_null:
        pred = f"{element.column_name} IS NULL OR {pred}"
    return pred


@compiles(_IdentifierFormatCheck)
def _render_ident_default(element, compiler, **kw) -> str:
    # POSIX regex (Postgres ``~``): anchored, exact trailing digit count.
    pred = " OR ".join(
        f"{element.column_name} ~ '^{p}-[0-9]{{{element.digits}}}$'"
        for p in element.prefixes
    )
    if element.allow_null:
        pred = f"{element.column_name} IS NULL OR {pred}"
    return pred


class _LowerHexCheck(ColumnElement):
    """A "value is all lowercase hex (or empty)" CHECK, dialect-rendered.

    The git-commit-SHA guard: SQLite ``col NOT GLOB '*[^0-9a-f]*'`` (no char
    outside ``0-9a-f``) ⇔ Postgres ``col ~ '^[0-9a-f]*$'``. ``length`` prepends
    an exact-length predicate (``LENGTH`` is portable across both dialects).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str, length: int | None = None) -> None:
        self.column_name = column_name
        self.length = length


@compiles(_LowerHexCheck, "sqlite")
def _render_hex_sqlite(element, compiler, **kw) -> str:
    pred = f"{element.column_name} NOT GLOB '*[^0-9a-f]*'"
    if element.length is not None:
        pred = f"LENGTH({element.column_name}) = {element.length} AND {pred}"
    return pred


@compiles(_LowerHexCheck)
def _render_hex_default(element, compiler, **kw) -> str:
    pred = f"{element.column_name} ~ '^[0-9a-f]*$'"
    if element.length is not None:
        pred = f"LENGTH({element.column_name}) = {element.length} AND {pred}"
    return pred


class _NonEmptyJsonArrayCheck(ColumnElement):
    """A "column is NULL or a non-empty JSON array" CHECK, dialect-rendered.

    SQLite uses ``json_valid``/``json_type``/``json_array_length``; Postgres
    JSONB uses ``jsonb_typeof``/``jsonb_array_length`` (and is always valid
    JSON, so no validity guard is needed).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str) -> None:
        self.column_name = column_name


@compiles(_NonEmptyJsonArrayCheck, "sqlite")
def _render_jsonarr_sqlite(element, compiler, **kw) -> str:
    c = element.column_name
    return (
        f"{c} IS NULL OR (json_valid({c}) AND json_type({c}) = 'array' "
        f"AND json_array_length({c}) >= 1)"
    )


@compiles(_NonEmptyJsonArrayCheck)
def _render_jsonarr_default(element, compiler, **kw) -> str:
    c = element.column_name
    return (
        f"{c} IS NULL OR (jsonb_typeof({c}) = 'array' "
        f"AND jsonb_array_length({c}) >= 1)"
    )


class _BooleanDomainCheck(ColumnElement):
    """A boolean-domain CHECK, dialect-rendered.

    SQLite stores Boolean as the integers ``0``/``1`` (``IN (0, 1)``); Postgres
    has a native boolean type, so the literals are ``true``/``false``. NULL
    satisfies the CHECK on both (``NULL IN (...)`` is unknown ⇒ passes).
    """

    inherit_cache = True
    type = Boolean()

    def __init__(self, column_name: str) -> None:
        self.column_name = column_name


@compiles(_BooleanDomainCheck, "sqlite")
def _render_booldomain_sqlite(element, compiler, **kw) -> str:
    return f"{element.column_name} IN (0, 1)"


@compiles(_BooleanDomainCheck)
def _render_booldomain_default(element, compiler, **kw) -> str:
    return f"{element.column_name} IN (true, false)"



def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class EngagementScopedMixin:
    """Row-level tenant discriminator for the unified multi-engagement DB.

    PI-123 Slice 2 (DEC-375 / D2, D5). ``engagement_id`` holds the owning
    engagement's **stable identifier** (``engagements.engagement_identifier``,
    ``ENG-NNN``) — the durable key (never renamed, unlike ``engagement_code``),
    so no separate integer surrogate is needed and the discriminator stays
    consistent with v2's identifier-keyed model (refs, etc.).

    **Strict (cutover) schema** — PI-123 Stage 2. ``engagement_id`` is now
    ``NOT NULL`` with a FK to ``engagements.engagement_identifier``. Every
    scoped row belongs to exactly one engagement. Identifier uniqueness is
    composite ``(engagement_id, <identifier>)`` per the three constraint classes
    in ``pi-123-slice3-enforce-plan.md`` §1: identifier-as-PK tables (Class A)
    make ``engagement_id`` a PK member (redeclared per-class with
    ``primary_key=True``); surrogate-PK tables (Class B) swap
    ``UNIQUE(identifier)`` for ``UNIQUE(engagement_id, identifier)``; the two
    un-keyed tables (Class C) take only NOT NULL + FK + an index.

    This is the *target* schema that ``Base.metadata.create_all`` materialises
    for the unified DB (D9 builds fresh + copies rows in). The central
    read-filter (``do_orm_execute`` → ``with_loader_criteria``) and the
    write-stamp (``before_flush``) in ``engagement_scope.py`` key on this column
    and are activated at the cutover (and in the test fixtures, which seed an
    engagement and set it active so the stamp fills every insert).
    """

    engagement_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("engagements.engagement_identifier"),
        nullable=False,
    )


class EngagementScopedPKMixin(EngagementScopedMixin):
    """Class A scoping: ``engagement_id`` is also part of the composite PK.

    The 19 identifier-as-PK governance/methodology tables (plus
    ``engagement_areas``, whose PK is a name) make ``engagement_id`` the leading
    member of a composite primary key ``(engagement_id, <entity>_identifier)``,
    so the same prefixed identifier can coexist across engagements while an
    intra-engagement duplicate is still rejected (DEC-375 / D3). Subclasses keep
    their existing ``<entity>_identifier`` / name column with
    ``primary_key=True``; this override supplies the second PK column.
    ``isinstance(obj, EngagementScopedMixin)`` still holds, so the central
    read-filter / write-stamp cover these tables unchanged.
    """

    engagement_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("engagements.engagement_identifier"),
        primary_key=True,
        nullable=False,
    )


class Charter(EngagementScopedMixin, Base):
    """Singleton document, versioned. ``is_current=True`` flags the latest row."""

    __tablename__ = "charter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("engagement_id", "version", name="uq_charter_version"),
        Index("ix_charter_is_current", "is_current"),
    )


class Status(EngagementScopedMixin, Base):
    """Singleton document, versioned. Same shape as ``Charter``."""

    __tablename__ = "status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("engagement_id", "version", name="uq_status_version"),
        Index("ix_status_is_current", "is_current"),
    )


class Decision(EngagementScopedMixin, Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    # PI-alpha: Text, not VARCHAR(255) — governance titles run long in practice
    # (decisions/PIs exceed 255), and SQLite never enforced the cap while
    # Postgres does. Free text, no length limit.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    decision_date: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decision: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    alternatives_considered: Mapped[str] = mapped_column(
        Text, nullable=False, default=""
    )
    consequences: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # NOT NULL since PI-075 (migration 0023). PI-074 added the column as
    # nullable; PI-096/097/098 backfilled every live row and migration
    # 0023 tightened it to NOT NULL with a no-NULL-arm length CHECK. This
    # model now matches the live schema.
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
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
        CheckConstraint(
            "length(executive_summary) >= 200 AND length(executive_summary) <= 800",
            name="ck_decision_executive_summary_length",
        ),
        UniqueConstraint(
            "engagement_id", "identifier", name="uq_decision_engagement_identifier"
        ),
        Index("ix_decisions_identifier", "engagement_id", "identifier"),
    )


class Session(EngagementScopedPKMixin, Base):
    """Governance entity — one discrete unit of communication in any medium.

    Redesigned in PI-073 / DEC-314 (supersedes DEC-013's append-only rule).
    A session represents one Claude.ai chat, one email, one phone call,
    one Zoom meeting, one in-person meeting, or one Slack thread.
    Schedulable and stateful through a six-status lifecycle. Carries
    universal columns (medium, started_at, ended_at, participants) and a
    JSON ``session_medium_metadata`` column for per-medium extras.
    Conversations (topical sub-units) belong to a session via the
    ``conversation_belongs_to_session`` reference edge.
    """

    __tablename__ = "sessions"

    session_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    session_title: Mapped[str] = mapped_column(String(255), nullable=False)
    session_description: Mapped[str] = mapped_column(Text, nullable=False)
    session_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )
    session_medium: Mapped[str] = mapped_column(String(20), nullable=False)
    # PI-074 carry-over field. Reconciles with PI-073's redesign:
    # legacy_sessions retains executive_summary post-migration; the new
    # sessions entity exposes session_executive_summary for the same
    # audience-readable purpose. NOT NULL since PI-075 (migration 0023);
    # this model now matches the live schema.
    session_executive_summary: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    session_scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_participants: Mapped[list] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    session_medium_metadata: Mapped[dict] = mapped_column(
        JSONColumn, nullable=False, default=dict
    )
    session_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    session_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        onupdate=_utcnow,
    )
    session_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_in_flight_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_not_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    session_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Identifier-prefix asymmetry per session-v2.md §6: existing
        # CONV-NNN rows migrate INTO this table (becoming sessions);
        # new sessions use SES-NNN. Both prefixes admitted.
        CheckConstraint(
            _IdentifierFormatCheck("session_identifier", ["SES", "CONV"]),
            name="ck_session_identifier_format",
        ),
        CheckConstraint(
            _check_in("session_status", SESSION_STATUSES),
            name="ck_session_status",
        ),
        CheckConstraint(
            _check_in("session_medium", SESSION_MEDIUMS),
            name="ck_session_medium",
        ),
        # PI-074 CHECK on executive_summary length (200..800 inclusive).
        # PI-075 (migration 0023) backfilled all rows and dropped the
        # IS NULL arm when tightening the column to NOT NULL.
        CheckConstraint(
            "length(session_executive_summary) >= 200 "
            "AND length(session_executive_summary) <= 800",
            name="ck_session_executive_summary_length",
        ),
        Index("ix_sessions_session_status", "session_status"),
        Index("ix_sessions_session_medium", "session_medium"),
        Index("ix_sessions_session_deleted_at", "session_deleted_at"),
    )


class Risk(EngagementScopedMixin, Base):
    __tablename__ = "risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    # PI-alpha: Text, not VARCHAR(255) — governance titles run long in practice
    # (decisions/PIs exceed 255), and SQLite never enforced the cap while
    # Postgres does. Free text, no length limit.
    title: Mapped[str] = mapped_column(Text, nullable=False)
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
        UniqueConstraint(
            "engagement_id", "identifier", name="uq_risk_engagement_identifier"
        ),
    )


class PlanningItem(EngagementScopedMixin, Base):
    __tablename__ = "planning_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    # PI-alpha: Text, not VARCHAR(255) — governance titles run long in practice
    # (decisions/PIs exceed 255), and SQLite never enforced the cap while
    # Postgres does. Free text, no length limit.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    resolution_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # NOT NULL since PI-075 (migration 0023); see Decision.executive_summary.
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    # PI-076: multi-valued work-area labels (JSON array) driving the
    # parallel-agent orchestrator's file-disjoint partitioning. Nullable
    # until PI-083 backfills open items and tightens to NOT NULL. The
    # CHECK enforces structure only (valid non-empty array); element-level
    # AREAS membership is enforced at the access layer because SQLite
    # CHECK constraints cannot iterate array elements.
    #
    # ``none_as_null=True`` is load-bearing: without it SQLAlchemy's JSON
    # type stores Python ``None`` as the JSON text ``'null'`` rather than
    # SQL NULL, which fails the ``area IS NULL`` arm of the CHECK
    # (``json_type('null')`` is ``'null'``, not ``'array'``).
    area: Mapped[list | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    # PI-183 / DEC-423: the ADO risk gate on this item. NOT NULL, defaults to
    # ``ado``. A PI can only make itself *more* restrictive than its Project;
    # its effective mode is the more restrictive of this value and its parent
    # Project's ``project_execution_mode`` (resolved in the access layer).
    execution_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ado", server_default="ado"
    )
    # PI-183 / DEC-424: human approval signal for an ``ado_with_approval`` item.
    # The dispatcher treats such an item as eligible only when this is True.
    # The only write path is POST /planning-items/{id}/approve-dispatch (DEC-424
    # / REQ-155) — not a general field update. NOT NULL, defaults to False.
    dispatch_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # PI-077: orchestrator claim. ``claimed_by`` holds the conversation
    # identifier (CONV-NNN) of the agent working the item; both columns
    # are NULL when the item is unclaimed and both set when claimed. The
    # atomic claim/release transitions live in the access layer.
    claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        CheckConstraint(
            "length(executive_summary) >= 200 AND length(executive_summary) <= 800",
            name="ck_planning_executive_summary_length",
        ),
        CheckConstraint(
            _NonEmptyJsonArrayCheck("area"),
            name="ck_planning_area_nonempty_array",
        ),
        CheckConstraint(
            "(claimed_by IS NULL AND claimed_at IS NULL) OR "
            "(claimed_by IS NOT NULL AND claimed_at IS NOT NULL)",
            name="ck_planning_claim_pairing",
        ),
        CheckConstraint(
            _check_in("execution_mode", EXECUTION_MODES),
            name="ck_planning_execution_mode",
        ),
        CheckConstraint(
            _BooleanDomainCheck("dispatch_approved"),
            name="ck_planning_dispatch_approved",
        ),
        UniqueConstraint(
            "engagement_id", "identifier", name="uq_planning_engagement_identifier"
        ),
    )


class EngagementArea(EngagementScopedPKMixin, Base):
    """Per-engagement, user-defined work area (PI-112; DEC-342, DEC-348).

    The Engagement tier of the two-tier area model. Each engagement
    database holds its own set of area names, defined by the user at
    engagement initialization. Deliberately standalone — no foreign key
    or reference to ``domain`` records (DEC-348); an Engagement area is a
    work-routing label, not a methodology discovery artifact. The System
    tier lives in ``vocab.SYSTEM_AREA_RANKS``; a value is valid iff it is
    a System area or one of these. Engagement areas are unranked (DEC-347).
    """

    __tablename__ = "engagement_areas"

    engagement_area_name: Mapped[str] = mapped_column(String(64), primary_key=True)
    engagement_area_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    engagement_area_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )


class Topic(EngagementScopedMixin, Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    identifier: Mapped[str] = mapped_column(String(64), nullable=False)
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

    __table_args__ = (
        UniqueConstraint(
            "engagement_id", "identifier", name="uq_topic_engagement_identifier"
        ),
    )


class Domain(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("domain_identifier", ["DOM"]),
            name="ck_domain_identifier_format",
        ),
        CheckConstraint(
            _check_in("domain_status", DOMAIN_STATUSES),
            name="ck_domain_status",
        ),
        Index("ix_domains_domain_status", "domain_status"),
        Index("ix_domains_domain_deleted_at", "domain_deleted_at"),
    )


class Entity(EngagementScopedPKMixin, Base):
    """Methodology entity — one CRM-modeled noun the client uses.

    Second of the four methodology entity types (UI v0.4 slice C). Per
    ``entity.md`` the schema follows the parent-prefix field-naming
    convention: every column is prefixed ``entity_``. The primary key
    is the prefixed-string identifier ``entity_identifier`` (format
    ``ENT-NNN``) — there is no integer surrogate ``id`` column. Domain
    affiliations are NOT FK columns here; they live in the ``refs``
    table as ``entity_scopes_to_domain`` references.

    v0.5+ PI-010 grows the schema by one classification column
    (``entity_kind``, TEXT NULL, five-value enum + NULL — see
    ``entity.md`` v1.1 §3.2.3 and DEC-292). Entity variants are
    expressed via the references-table ``entity_variant_of_entity``
    edge (PI-010 / DEC-291); no FK column on this table.
    """

    __tablename__ = "entities"

    entity_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    entity_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_description: Mapped[str] = mapped_column(Text, nullable=False)
    entity_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PRJ-025 PI-182 — intrinsic engine-neutral design intent (§6).
    # ``entity_default_sort_field`` names the field the entity sorts by;
    # ``entity_default_sort_direction`` is asc/desc (validated against
    # ENTITY_SORT_DIRECTIONS at the access layer when present).
    # ``entity_track_activity`` is the neutral "track activity feed"
    # intent (EspoCRM ``settings.stream``; HubSpot timeline always-on).
    entity_default_sort_field: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    entity_default_sort_direction: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    entity_track_activity: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
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
            _IdentifierFormatCheck("entity_identifier", ["ENT"]),
            name="ck_entity_identifier_format",
        ),
        CheckConstraint(
            _check_in("entity_status", ENTITY_STATUSES),
            name="ck_entity_status",
        ),
        # PI-010 / DEC-292: entity_kind admits NULL (deferred
        # classification) or any of the five enum values.
        CheckConstraint(
            f"entity_kind IS NULL OR {_check_in('entity_kind', ENTITY_KINDS)}",
            name="ck_entity_kind",
        ),
        # PRJ-025 PI-182 — neutral track-activity flag domain CHECK.
        CheckConstraint(
            _BooleanDomainCheck("entity_track_activity"),
            name="ck_entity_track_activity_boolean",
        ),
        Index("ix_entities_entity_status", "entity_status"),
        Index("ix_entities_entity_deleted_at", "entity_deleted_at"),
    )


class Field(EngagementScopedPKMixin, Base):
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
    # PRJ-025 PI-182 — intrinsic engine-neutral design intent (§7). All
    # neutral: no EspoCRM/HubSpot specifics. Free-text bound/default
    # values are stored as the authored string (adapters coerce per
    # engine). ``field_format`` / ``field_numeric_scale`` are validated
    # against FIELD_FORMATS / FIELD_NUMERIC_SCALES at the access layer
    # when present. Enum/multi_enum option values live in the
    # ``field_options`` child collection, not here.
    field_tooltip: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_usage_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_format: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_numeric_scale: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_max_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    field_min: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_max: Mapped[str | None] = mapped_column(Text, nullable=True)
    field_read_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    field_unique: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    field_externally_populated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # PRJ-025 PI-197 (design §7/§9, DEC-438) — derived/formula intent.
    # ``field_derived_result_type`` is the value-type the formula yields
    # (validated against DERIVED_RESULT_TYPES, required when ``field_type``
    # is ``derived`` and NULL otherwise — enforced at the access layer).
    # ``field_formula`` is the neutral structured-formula AST
    # (``access.formulas`` shape), validated when present. Both nullable.
    field_derived_result_type: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    field_formula: Mapped[dict | None] = mapped_column(
        JSONColumn, nullable=True
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
            _IdentifierFormatCheck("field_identifier", ["FLD"]),
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
            _BooleanDomainCheck("field_required"),
            name="ck_field_required_boolean",
        ),
        # PRJ-025 PI-182 — the three new neutral boolean flags share the
        # same dialect-rendering domain CHECK as ``field_required``.
        CheckConstraint(
            _BooleanDomainCheck("field_read_only"),
            name="ck_field_read_only_boolean",
        ),
        CheckConstraint(
            _BooleanDomainCheck("field_unique"),
            name="ck_field_unique_boolean",
        ),
        CheckConstraint(
            _BooleanDomainCheck("field_externally_populated"),
            name="ck_field_externally_populated_boolean",
        ),
        Index("ix_fields_field_status", "field_status"),
        Index("ix_fields_field_type", "field_type"),
        Index("ix_fields_field_deleted_at", "field_deleted_at"),
    )


class FieldOption(EngagementScopedMixin, Base):
    """Child of ``fields`` — one allowed enum/multi_enum option value.

    PRJ-025 PI-182 (design §7 "allowed values (enum)" / §8 ``field_option``).
    A plain child collection of ``field``, **not** a prefixed-identifier
    governance entity and **not** a ``change_log`` entity type — its
    contents are captured in the parent field's change-log payload. Option
    rows are engagement-scoped exactly like their parent field
    (``EngagementScopedMixin`` supplies ``engagement_id`` + the
    write-stamp / read-filter coverage); the composite FK to the parent's
    ``(engagement_id, field_identifier)`` PK is declared in
    ``__table_args__`` (the parent PK is composite under PI-123), mirroring
    ``ReferenceBookVersion``.

    Ordering is explicit via ``option_order`` (the business display order,
    which both EspoCRM ``options:`` and HubSpot enumeration ``options``
    consume). ``option_label`` is the optional human label; ``option_value``
    is the stored value and is unique within a field (per engagement).
    """

    __tablename__ = "field_options"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # FK to the parent's composite PK ``(engagement_id, field_identifier)``
    # is declared as a ForeignKeyConstraint in __table_args__; the column
    # itself carries no single-column FK.
    field_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    option_value: Mapped[str] = mapped_column(Text, nullable=False)
    option_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    option_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "field_identifier"],
            ["fields.engagement_id", "fields.field_identifier"],
            ondelete="CASCADE",
            name="fk_field_options_parent",
        ),
        UniqueConstraint(
            "engagement_id",
            "field_identifier",
            "option_value",
            name="uq_field_option_value",
        ),
        Index(
            "ix_field_options_parent",
            "engagement_id",
            "field_identifier",
        ),
    )


class Requirement(EngagementScopedPKMixin, Base):
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
    # Requirements-provenance model (Phase 1). ``origin`` records how the
    # requirement came to be (NULL for legacy rows predating the model);
    # ``review_state`` is the living-drift flag; ``approved_at`` stamps the
    # human approval that takes it active. The parent edge, provenance edge,
    # topic edge, and decision-outcome edges all live in ``refs`` as
    # relationship kinds, not FK columns.
    requirement_origin: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    requirement_review_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="current"
    )
    requirement_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^REQ-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            _IdentifierFormatCheck("requirement_identifier", ["REQ"]),
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
        CheckConstraint(
            _check_in("requirement_origin", REQUIREMENT_ORIGINS),
            name="ck_requirement_origin",
        ),
        CheckConstraint(
            _check_in("requirement_review_state", REQUIREMENT_REVIEW_STATES),
            name="ck_requirement_review_state",
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


class Persona(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("persona_identifier", ["PER"]),
            name="ck_persona_identifier_format",
        ),
        CheckConstraint(
            _check_in("persona_status", PERSONA_STATUSES),
            name="ck_persona_status",
        ),
        Index("ix_personas_persona_status", "persona_status"),
        Index("ix_personas_persona_deleted_at", "persona_deleted_at"),
    )


class Process(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("process_identifier", ["PROC"]),
            name="ck_process_identifier_format",
        ),
        CheckConstraint(
            _IdentifierFormatCheck("process_domain_identifier", ["DOM"]),
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


class ManualConfig(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("manual_config_identifier", ["MCF"]),
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


class TestSpec(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("test_spec_identifier", ["TST"]),
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


class MigrationMapping(EngagementScopedPKMixin, Base):
    """Methodology entity — one keep/transform disposition's migration obligation.

    WTK-106 storage layer per the WTK-104 design spec
    (``methodology-schema-specs/migration_mapping.md`` §3.2): records and
    values from one source entity/field land in target entity/field(s),
    transformed by the §4 rule list. Parent-prefix field naming; primary
    key is the prefixed-string identifier ``migration_mapping_identifier``
    (``MIG-NNN``). No name column — documented deviation (spec §3.2.1):
    the natural label *is* the source → target pair, derived from the
    edges.

    Both linkages live in ``refs`` as references-entity edges, not FK
    columns (DEC-006, DEC-249): ``migration_mapping_migrates_from_record``
    (exactly one — the disposed baseline candidate; at most one live
    inbound per candidate encodes "one mapping per disposition") and
    ``migration_mapping_migrates_to_record`` (≥1 — the confirmed target
    record(s); >1 only with a ``split`` rule). Edge cardinality, target
    liveness/status, level agreement, and the keep/split shape rules are
    access-layer enforcement (spec invariants I1–I8); this table carries
    the I11 CHECK (``source_attribute_name`` present iff
    ``level = 'field'``).

    The literal source-system coordinates (system label, entity name,
    attribute name) are denormalized deliberately at triage time so the
    future compiler extracts data by the names the audit observed,
    independent of later methodology-record renames (spec §6.2) — this is
    what lets confirmed mappings compile mechanically into import batches
    for ``espo_impl/core/import_manager.py``.
    """

    __tablename__ = "migration_mappings"

    migration_mapping_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    migration_mapping_level: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    migration_mapping_disposition: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    migration_mapping_source_system_label: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    migration_mapping_source_entity_name: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    migration_mapping_source_attribute_name: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    # Ordered list of §4 rule objects (rule_kind ∈
    # MIGRATION_TRANSFORM_RULE_KINDS); per-kind schema validation is the
    # repository layer's invariant I9. NULL (or empty) is valid for a
    # rename-only transform and mandatory for a keep (spec §3.2.2).
    migration_mapping_transform_rules: Mapped[list | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    migration_mapping_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    migration_mapping_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    migration_mapping_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    migration_mapping_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    migration_mapping_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^MIG-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            _IdentifierFormatCheck("migration_mapping_identifier", ["MIG"]),
            name="ck_migration_mapping_identifier_format",
        ),
        CheckConstraint(
            _check_in("migration_mapping_status", MIGRATION_MAPPING_STATUSES),
            name="ck_migration_mapping_status",
        ),
        CheckConstraint(
            _check_in("migration_mapping_level", MIGRATION_MAPPING_LEVELS),
            name="ck_migration_mapping_level",
        ),
        CheckConstraint(
            _check_in(
                "migration_mapping_disposition", MIGRATION_MAPPING_DISPOSITIONS
            ),
            name="ck_migration_mapping_disposition",
        ),
        # I11: the attribute coordinate is present iff the mapping is
        # field-level (non-empty-trimmed is repository-layer validation).
        CheckConstraint(
            "(migration_mapping_level = 'field' "
            "AND migration_mapping_source_attribute_name IS NOT NULL) "
            "OR (migration_mapping_level = 'entity' "
            "AND migration_mapping_source_attribute_name IS NULL)",
            name="ck_migration_mapping_attribute_per_level",
        ),
        Index(
            "ix_migration_mappings_migration_mapping_status",
            "migration_mapping_status",
        ),
        Index(
            "ix_migration_mappings_migration_mapping_level",
            "migration_mapping_level",
        ),
        Index(
            "ix_migration_mappings_migration_mapping_deleted_at",
            "migration_mapping_deleted_at",
        ),
    )


class Service(EngagementScopedPKMixin, Base):
    """Methodology entity — one cross-domain service in the target system.

    PI-161 storage layer per the WTK-132 design spec
    (``methodology-schema-specs/service.md`` §3.2). A cross-domain service is
    a capability the CRM system provides that is not owned by any single
    business domain (document storage, notifications, user accounts, AI agent
    orchestration — the four surfaced by the first dogfood run, SES-166).
    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``service_identifier`` (format ``SVC-NNN``) —
    no integer surrogate ``id`` column, matching ``persona`` /
    ``migration_mapping``.

    No FK column. Both relationship kinds live in ``refs`` as references-entity
    edges (DEC-006), mirroring ``persona`` exactly: inbound
    ``process_consumes_service`` (process → service — which business processes
    depend on the service, the empirical content of "cross-domain") and
    outbound ``service_owns_entity`` (service → entity — the entities the
    service owns, per the PRD's Phase 1 capture item). Neither edge is
    mandatory, so a plain create suffices — no atomic row+edges POST machinery.
    Deliberately there is **no** ``service_scopes_to_domain`` kind (spec
    §3.3.2): a cross-domain service is not domain-bound and its effective
    domain coverage is derivable by joining its consuming processes to their
    parent domains.

    "Any entities it may own" is relational data, not prose — there is no
    ``service_owned_entities`` text column. At Phase 1 capture time, before
    any entity records exist, ownership intent is prose in ``service_notes``;
    the ``service_owns_entity`` edge is attached when Phase 2/3 surfaces the
    candidate entity (spec §3.2.2).
    """

    __tablename__ = "services"

    service_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    service_capabilities: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    service_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    service_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    service_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^SVC-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("service_identifier", ["SVC"]),
            name="ck_service_identifier_format",
        ),
        CheckConstraint(
            _check_in("service_status", SERVICE_STATUSES),
            name="ck_service_status",
        ),
        Index("ix_services_service_status", "service_status"),
        Index("ix_services_service_deleted_at", "service_deleted_at"),
    )


class Association(EngagementScopedPKMixin, Base):
    """Composite design record — one engine-neutral entity-to-entity link.

    PRJ-025 PI-189 slice 1, per ``engine-neutral-design-model-and-adapters.md``
    §8. An association is the engine-neutral description of a relationship
    between two design ``entity`` records; it is the construct the EspoCRM
    adapter renders into the ``relationships:`` block (the biggest YAML gap)
    and a HubSpot adapter renders into an association definition.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``association_identifier`` (format ``ASN-NNN``)
    — no integer surrogate, matching ``entity`` / ``field`` / ``service``.
    The source and target entities are carried as plain ``ENT-NNN`` string
    columns (not ``refs`` edges) — the association *is* the relationship, so
    the access layer validates both endpoints exist and are live at write
    time rather than holding an FK. The standard four-status propose-verify
    lifecycle gates the record exactly as ``entity`` does.
    """

    __tablename__ = "associations"

    association_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    association_name: Mapped[str] = mapped_column(String(255), nullable=False)
    association_source_entity: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    association_target_entity: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    association_cardinality: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    association_source_role: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    association_target_role: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    association_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    association_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    association_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    association_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    association_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    association_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^ASN-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("association_identifier", ["ASN"]),
            name="ck_association_identifier_format",
        ),
        CheckConstraint(
            _check_in("association_cardinality", ASSOCIATION_CARDINALITIES),
            name="ck_association_cardinality",
        ),
        CheckConstraint(
            _check_in("association_status", ASSOCIATION_STATUSES),
            name="ck_association_status",
        ),
        Index("ix_associations_association_status", "association_status"),
        Index(
            "ix_associations_association_source_entity",
            "association_source_entity",
        ),
        Index(
            "ix_associations_association_target_entity",
            "association_target_entity",
        ),
        Index(
            "ix_associations_association_deleted_at", "association_deleted_at"
        ),
    )


class EngineOverride(EngagementScopedPKMixin, Base):
    """Composite design record — one sparse per-engine override.

    PRJ-025 PI-189 slice 1, per ``engine-neutral-design-model-and-adapters.md``
    §9. The engine-neutral model is authoritative; an ``engine_override`` is
    the thin escape hatch that adjusts how one design construct
    (``entity`` / ``field`` / ``association``) renders for one target engine —
    e.g. pinning an EspoCRM ``internal_name``, a ``formula`` body, or an enum
    rendering style. The adapter consumes the override layer when rendering;
    absent an override the neutral default applies.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``override_identifier`` (format ``OVR-NNN``).
    There is **no status lifecycle** — an override either exists or it does
    not. The ``(engagement_id, target_engine, subject_type, subject_identifier,
    attribute)`` tuple is unique: one override per engine per construct per
    attribute. ``override_value`` is dialect-portable JSON (``JSONColumn``),
    so a scalar, list, or object value renders as JSONB on Postgres.
    """

    __tablename__ = "engine_overrides"

    override_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    override_target_engine: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    override_subject_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    override_subject_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    override_attribute: Mapped[str] = mapped_column(String(64), nullable=False)
    override_value: Mapped[object | None] = mapped_column(
        JSONColumn, nullable=True
    )
    override_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    override_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    override_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^OVR-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("override_identifier", ["OVR"]),
            name="ck_engine_override_identifier_format",
        ),
        CheckConstraint(
            _check_in("override_target_engine", TARGET_ENGINES),
            name="ck_engine_override_target_engine",
        ),
        CheckConstraint(
            _check_in("override_subject_type", OVERRIDE_SUBJECT_TYPES),
            name="ck_engine_override_subject_type",
        ),
        UniqueConstraint(
            "engagement_id",
            "override_target_engine",
            "override_subject_type",
            "override_subject_identifier",
            "override_attribute",
            name="uq_engine_override_target",
        ),
        Index(
            "ix_engine_overrides_override_subject",
            "override_subject_type",
            "override_subject_identifier",
        ),
        Index(
            "ix_engine_overrides_override_target_engine",
            "override_target_engine",
        ),
        Index(
            "ix_engine_overrides_override_deleted_at", "override_deleted_at"
        ),
    )


class Rule(EngagementScopedPKMixin, Base):
    """Condition-carrying design record — one required/visible/valid gate.

    PRJ-025 PI-189 slice 2, per ``engine-neutral-design-model-and-adapters.md``
    §8. A ``rule`` (``RUL-NNN``) governs one design construct — a ``field``
    (its required-when / visible-when gate) or an ``entity`` (a valid-when
    invariant). ``rule_condition`` is a neutral condition AST (validated at the
    access layer by ``conditions.validate_condition``); ``rule_message`` is the
    user-facing validation message a ``valid_when`` rule surfaces on failure.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``rule_identifier``. The subject is carried as a
    plain ``FLD-NNN`` / ``ENT-NNN`` string column (not a ``refs`` edge) — the
    access layer validates it exists, is live, and matches ``rule_subject_type``
    at write time. The standard four-status propose-verify lifecycle gates the
    record exactly as ``entity`` / ``association`` does.
    """

    __tablename__ = "rules"

    rule_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    rule_subject_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    rule_effect: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_condition: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    rule_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    rule_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    rule_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    rule_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^RUL-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("rule_identifier", ["RUL"]),
            name="ck_rule_identifier_format",
        ),
        CheckConstraint(
            _check_in("rule_subject_type", RULE_SUBJECT_TYPES),
            name="ck_rule_subject_type",
        ),
        CheckConstraint(
            _check_in("rule_effect", RULE_EFFECTS),
            name="ck_rule_effect",
        ),
        CheckConstraint(
            _check_in("rule_status", RULE_STATUSES),
            name="ck_rule_status",
        ),
        Index("ix_rules_rule_status", "rule_status"),
        Index(
            "ix_rules_rule_subject",
            "rule_subject_type",
            "rule_subject_identifier",
        ),
        Index("ix_rules_rule_deleted_at", "rule_deleted_at"),
    )


class View(EngagementScopedPKMixin, Base):
    """Condition-carrying design record — one list view of an entity.

    PRJ-025 PI-189 slice 2, per ``engine-neutral-design-model-and-adapters.md``
    §8. A ``view`` (``VEW-NNN``) is the engine-neutral description of a list
    view: ``view_columns`` is a non-empty ordered list of field references
    (field names or ``FLD-NNN``), ``view_filter`` an optional neutral condition
    AST, and ``view_sort_field`` / ``view_sort_direction`` the default sort. It
    renders into an EspoCRM saved-list / layout and a HubSpot list/view.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``view_identifier``. ``view_entity`` is a plain
    ``ENT-NNN`` string column validated to exist and be live at write time.
    The standard four-status propose-verify lifecycle gates the record.
    """

    __tablename__ = "views"

    view_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    view_name: Mapped[str] = mapped_column(String(255), nullable=False)
    view_entity: Mapped[str] = mapped_column(String(32), nullable=False)
    view_columns: Mapped[list] = mapped_column(JSONColumn, nullable=False)
    view_filter: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    view_sort_field: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    view_sort_direction: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    view_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    view_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    view_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    view_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    view_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^VEW-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("view_identifier", ["VEW"]),
            name="ck_view_identifier_format",
        ),
        # ``view_columns`` is NOT NULL and must be a non-empty JSON array.
        CheckConstraint(
            _NonEmptyJsonArrayCheck("view_columns"),
            name="ck_view_columns_nonempty",
        ),
        CheckConstraint(
            _check_in("view_status", VIEW_STATUSES),
            name="ck_view_status",
        ),
        Index("ix_views_view_status", "view_status"),
        Index("ix_views_view_entity", "view_entity"),
        Index("ix_views_view_deleted_at", "view_deleted_at"),
    )


class Automation(EngagementScopedPKMixin, Base):
    """Condition-carrying design record — one trigger/condition/action rule.

    PRJ-025 PI-189 slice 2, per ``engine-neutral-design-model-and-adapters.md``
    §8. An ``automation`` (``AUT-NNN``) is the engine-neutral description of a
    workflow on one entity: ``automation_trigger`` is the firing event, the
    optional ``automation_condition`` a neutral condition AST that further
    gates it, and ``automation_actions`` a non-empty ordered list of action
    objects (each with a ``"type"`` in ``AUTOMATION_ACTION_TYPES``). It renders
    into an EspoCRM Workflow / BPM flow and a HubSpot workflow.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``automation_identifier``. ``automation_entity``
    is a plain ``ENT-NNN`` string column validated to exist and be live at
    write time. The standard four-status propose-verify lifecycle gates it.
    """

    __tablename__ = "automations"

    automation_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    automation_name: Mapped[str] = mapped_column(String(255), nullable=False)
    automation_entity: Mapped[str] = mapped_column(String(32), nullable=False)
    automation_trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    automation_condition: Mapped[dict | None] = mapped_column(
        JSONColumn, nullable=True
    )
    automation_actions: Mapped[list] = mapped_column(
        JSONColumn, nullable=False
    )
    automation_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    automation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    automation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    automation_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    automation_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    automation_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^AUT-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("automation_identifier", ["AUT"]),
            name="ck_automation_identifier_format",
        ),
        CheckConstraint(
            _check_in("automation_trigger", AUTOMATION_TRIGGERS),
            name="ck_automation_trigger",
        ),
        # ``automation_actions`` is NOT NULL and must be a non-empty JSON
        # array (per-action ``type`` membership is access-layer enforced).
        CheckConstraint(
            _NonEmptyJsonArrayCheck("automation_actions"),
            name="ck_automation_actions_nonempty",
        ),
        CheckConstraint(
            _check_in("automation_status", AUTOMATION_STATUSES),
            name="ck_automation_status",
        ),
        Index("ix_automations_automation_status", "automation_status"),
        Index("ix_automations_automation_entity", "automation_entity"),
        Index(
            "ix_automations_automation_deleted_at", "automation_deleted_at"
        ),
    )


class DedupRule(EngagementScopedPKMixin, Base):
    """Dedup-and-template design record — one duplicate-detection rule.

    PRJ-025 PI-189 slice 3, per ``engine-neutral-design-model-and-adapters.md``
    §8. A ``dedup_rule`` (``DUP-NNN``) describes how to detect a duplicate of
    one entity: ``dedup_rule_match_fields`` is a non-empty ordered list of
    field references (field names or ``FLD-NNN``) compared across records,
    ``dedup_rule_normalize`` an optional object mapping a field reference to a
    normalization token (``NORMALIZE_TOKENS``) applied before comparison, and
    ``dedup_rule_on_match`` the action (``block`` / ``warn``) taken when a
    duplicate is found. It renders into an EspoCRM duplicate-check rule and a
    HubSpot dedupe key.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``dedup_rule_identifier``. ``dedup_rule_entity``
    is a plain ``ENT-NNN`` string column validated to exist and be live at
    write time. The standard four-status propose-verify lifecycle gates it.
    """

    __tablename__ = "dedup_rules"

    dedup_rule_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    dedup_rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dedup_rule_entity: Mapped[str] = mapped_column(String(32), nullable=False)
    dedup_rule_match_fields: Mapped[list] = mapped_column(
        JSONColumn, nullable=False
    )
    dedup_rule_normalize: Mapped[dict | None] = mapped_column(
        JSONColumn, nullable=True
    )
    dedup_rule_on_match: Mapped[str] = mapped_column(
        String(16), nullable=False
    )
    dedup_rule_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_rule_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    dedup_rule_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    dedup_rule_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    dedup_rule_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    dedup_rule_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    dedup_rule_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^DUP-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("dedup_rule_identifier", ["DUP"]),
            name="ck_dedup_rule_identifier_format",
        ),
        # ``dedup_rule_match_fields`` is NOT NULL and must be a non-empty JSON
        # array (per-element field-reference shape is access-layer enforced).
        CheckConstraint(
            _NonEmptyJsonArrayCheck("dedup_rule_match_fields"),
            name="ck_dedup_rule_match_fields_nonempty",
        ),
        CheckConstraint(
            _check_in("dedup_rule_on_match", DEDUP_ON_MATCH),
            name="ck_dedup_rule_on_match",
        ),
        CheckConstraint(
            _check_in("dedup_rule_status", DEDUP_RULE_STATUSES),
            name="ck_dedup_rule_status",
        ),
        Index("ix_dedup_rules_dedup_rule_status", "dedup_rule_status"),
        Index("ix_dedup_rules_dedup_rule_entity", "dedup_rule_entity"),
        Index(
            "ix_dedup_rules_dedup_rule_deleted_at", "dedup_rule_deleted_at"
        ),
    )


class MessageTemplate(EngagementScopedPKMixin, Base):
    """Dedup-and-template design record — one notification/message template.

    PRJ-025 PI-189 slice 3, per ``engine-neutral-design-model-and-adapters.md``
    §8. A ``message_template`` (``MSG-NNN``) is the engine-neutral description
    of a communication: ``message_template_body`` (required) carries the body
    content/intent and ``message_template_subject`` the subject line, both of
    which may contain merge-field placeholders; ``message_template_merge_fields``
    is an optional list of merge-field reference strings;
    ``message_template_channel`` (``MESSAGE_CHANNELS``) and
    ``message_template_audience`` (free text) are optional descriptors. The
    optional ``message_template_entity`` names the ``ENT-NNN`` the template is
    about. It renders into an EspoCRM email template / notification and a
    HubSpot email / template.

    Parent-prefix field naming (DEC-046); the primary key is the
    prefixed-string identifier ``message_template_identifier``. When present,
    ``message_template_entity`` is validated to exist and be live at write
    time. The standard four-status propose-verify lifecycle gates it.
    """

    __tablename__ = "message_templates"

    message_template_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    message_template_name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    message_template_entity: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    message_template_channel: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    message_template_subject: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    message_template_body: Mapped[str] = mapped_column(Text, nullable=False)
    message_template_merge_fields: Mapped[list | None] = mapped_column(
        JSONColumn, nullable=True
    )
    message_template_audience: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    message_template_description: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    message_template_notes: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    message_template_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    message_template_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    message_template_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    message_template_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^MSG-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("message_template_identifier", ["MSG"]),
            name="ck_message_template_identifier_format",
        ),
        CheckConstraint(
            _check_in("message_template_status", MESSAGE_TEMPLATE_STATUSES),
            name="ck_message_template_status",
        ),
        Index(
            "ix_message_templates_message_template_status",
            "message_template_status",
        ),
        Index(
            "ix_message_templates_message_template_entity",
            "message_template_entity",
        ),
        Index(
            "ix_message_templates_message_template_deleted_at",
            "message_template_deleted_at",
        ),
    )


class Instance(EngagementScopedPKMixin, Base):
    """PI-186 entity (PRJ-027) — one engagement-scoped connection to a live CRM.

    An engagement defines one or more instances (identifier ``INST-NNN``), each
    pointing at a real CRM system. Audit (pull) reverse-engineers a source
    instance's structure into the canonical engine-neutral inventory; publish
    (push, PRJ-025) writes design to a target instance. See
    ``prj-027-multi-instance-audit-inventory-architecture.md`` §3.

    Parent-prefix field naming (DEC-046); the prefixed-string identifier is the
    primary key (no integer surrogate), matching the methodology/governance
    entity precedent. ``instance_vendor`` selects the introspection/adapter
    driver. ``instance_role`` mirrors the V1 ``InstanceRole``: a ``source`` to
    read from, a ``target`` to write to, or ``both``.

    **Secrets are never stored on this row** (REQ-157). The two ``*_secret_ref``
    columns hold only opaque ``crmbuilder:{uuid}`` keyring references resolved at
    connection time via :mod:`crmbuilder_v2.secrets`; the plaintext values live
    in the OS keyring. ``instance_secret_ref`` carries the API key or password;
    ``instance_secret_key_ref`` carries the HMAC secret key when
    ``instance_auth_method`` is ``hmac``.
    """

    __tablename__ = "instances"

    instance_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    instance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_vendor: Mapped[str] = mapped_column(
        String(16), nullable=False, default="espocrm"
    )
    instance_url: Mapped[str] = mapped_column(Text, nullable=False)
    instance_role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="both"
    )
    instance_auth_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="api_key"
    )
    instance_secret_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instance_secret_key_ref: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    instance_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    instance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    instance_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    instance_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    instance_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^INST-\d{3}$`` expressed as a SQLite GLOB / PG regex pattern.
        CheckConstraint(
            _IdentifierFormatCheck("instance_identifier", ["INST"]),
            name="ck_instance_identifier_format",
        ),
        CheckConstraint(
            _check_in("instance_vendor", INSTANCE_VENDORS),
            name="ck_instance_vendor",
        ),
        CheckConstraint(
            _check_in("instance_role", INSTANCE_ROLES),
            name="ck_instance_role",
        ),
        CheckConstraint(
            _check_in("instance_auth_method", INSTANCE_AUTH_METHODS),
            name="ck_instance_auth_method",
        ),
        CheckConstraint(
            _check_in("instance_status", INSTANCE_STATUSES),
            name="ck_instance_status",
        ),
        Index("ix_instances_instance_status", "instance_status"),
        Index("ix_instances_instance_deleted_at", "instance_deleted_at"),
    )


class InstanceMembership(EngagementScopedMixin, Base):
    """PI-185 (PRJ-027) — the per-(canonical design object, instance) join.

    A lightweight engagement-scoped child table (integer PK, **not** a
    prefixed-identifier governance entity — no ``change_log`` / ``refs``
    participation), mirroring ``FieldOption``. One row records whether a
    canonical design object (``member_type`` ∈ {entity, field, association},
    DEC-433) identified by ``member_identifier`` is ``present`` / ``drifted`` /
    ``absent`` in a given ``instance`` (DEC-427), with a sparse per-attribute
    ``override`` JSON capturing only the attributes whose audited value differs
    from the canonical record (DEC-432). ``last_audited_at`` stamps when the
    state was last observed. Reconcile upserts these rows idempotently
    (uniqueness on engagement + instance + member). See §5 of
    ``prj-027-multi-instance-audit-inventory-architecture.md``.
    """

    __tablename__ = "instance_memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    member_type: Mapped[str] = mapped_column(String(16), nullable=False)
    member_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    override: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    last_audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "instance_identifier"],
            ["instances.engagement_id", "instances.instance_identifier"],
            ondelete="CASCADE",
            name="fk_instance_memberships_instance",
        ),
        UniqueConstraint(
            "engagement_id",
            "instance_identifier",
            "member_type",
            "member_identifier",
            name="uq_instance_membership",
        ),
        CheckConstraint(
            _check_in("member_type", INSTANCE_MEMBERSHIP_MEMBER_TYPES),
            name="ck_instance_membership_member_type",
        ),
        CheckConstraint(
            _check_in("state", INSTANCE_MEMBERSHIP_STATES),
            name="ck_instance_membership_state",
        ),
        Index(
            "ix_instance_memberships_instance",
            "engagement_id",
            "instance_identifier",
        ),
        Index(
            "ix_instance_memberships_member",
            "engagement_id",
            "member_type",
            "member_identifier",
        ),
    )


class Layout(EngagementScopedPKMixin, Base):
    """PI-193 (PRJ-027) — one engine-neutral layout of an entity (``LAY-NNN``).

    A net-new design family: a detail/list/etc. layout captured by audit and
    publishable. ``layout_entity_identifier`` is the parent canonical entity
    (soft reference, no FK — reconcile manages it); ``layout_content`` is the
    neutral layout structure (panels/rows/columns) as JSON. Reconcile matches by
    (entity, type) and records drift as a sparse override on the membership row.
    """

    __tablename__ = "layouts"

    layout_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    layout_entity_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    layout_type: Mapped[str] = mapped_column(String(32), nullable=False)
    layout_content: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    layout_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    layout_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    layout_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    layout_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("layout_identifier", ["LAY"]),
            name="ck_layout_identifier_format",
        ),
        CheckConstraint(
            _check_in("layout_type", LAYOUT_TYPES), name="ck_layout_type"
        ),
        CheckConstraint(
            _check_in("layout_status", LAYOUT_STATUSES), name="ck_layout_status"
        ),
        Index("ix_layouts_layout_entity", "layout_entity_identifier"),
        Index("ix_layouts_layout_status", "layout_status"),
        Index("ix_layouts_layout_deleted_at", "layout_deleted_at"),
    )


class Role(EngagementScopedPKMixin, Base):
    """PI-194 (PRJ-027) — one engine-neutral security role (``ROL-NNN``).

    A net-new design family: a role's scope-access matrix and system permissions
    captured by audit and publishable. ``role_scope_access`` / ``role_system_
    permissions`` are JSON. Reconcile matches by name and records drift as a
    sparse override on the membership row.
    """

    __tablename__ = "roles"

    role_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_scope_access: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    role_system_permissions: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    role_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    role_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    role_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    role_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("role_identifier", ["ROL"]),
            name="ck_role_identifier_format",
        ),
        CheckConstraint(
            _check_in("role_status", ROLE_STATUSES), name="ck_role_status"
        ),
        Index("ix_roles_role_status", "role_status"),
        Index("ix_roles_role_deleted_at", "role_deleted_at"),
    )


class Team(EngagementScopedPKMixin, Base):
    """PI-194 (PRJ-027) — one engine-neutral security team (``TM-NNN``).

    A net-new design family: a team name + description captured by audit and
    publishable. Reconcile matches by name and records drift as a sparse
    override on the membership row.
    """

    __tablename__ = "teams"

    team_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    team_name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    team_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    team_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    team_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    team_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("team_identifier", ["TM"]),
            name="ck_team_identifier_format",
        ),
        CheckConstraint(
            _check_in("team_status", TEAM_STATUSES), name="ck_team_status"
        ),
        Index("ix_teams_team_status", "team_status"),
        Index("ix_teams_team_deleted_at", "team_deleted_at"),
    )


class FilteredTab(EngagementScopedPKMixin, Base):
    """PI-195 (PRJ-027) — one engine-neutral filtered tab (``FTB-NNN``).

    A net-new design family: an entity-bound report-filter view (a filtered
    navigation tab) captured by audit and publishable.
    ``filtered_tab_entity_identifier`` is the parent canonical entity (soft
    reference, reconcile-managed); ``filtered_tab_filter`` is the neutral
    condition expression as JSON. Reconcile matches by (entity, label) and
    records drift as a sparse override on the membership row.
    """

    __tablename__ = "filtered_tabs"

    filtered_tab_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    filtered_tab_entity_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    filtered_tab_label: Mapped[str] = mapped_column(String(255), nullable=False)
    filtered_tab_filter: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    filtered_tab_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate"
    )
    filtered_tab_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    filtered_tab_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    filtered_tab_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    filtered_tab_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("filtered_tab_identifier", ["FTB"]),
            name="ck_filtered_tab_identifier_format",
        ),
        CheckConstraint(
            _check_in("filtered_tab_status", FILTERED_TAB_STATUSES),
            name="ck_filtered_tab_status",
        ),
        Index(
            "ix_filtered_tabs_filtered_tab_entity",
            "filtered_tab_entity_identifier",
        ),
        Index("ix_filtered_tabs_filtered_tab_status", "filtered_tab_status"),
        Index(
            "ix_filtered_tabs_filtered_tab_deleted_at", "filtered_tab_deleted_at"
        ),
    )


class CrmCandidate(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("crm_candidate_identifier", ["CRM"]),
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


class Project(EngagementScopedPKMixin, Base):
    """Governance entity — one coherent line of related conversations.

    First of six governance entity types (UI v0.7). Five-status workflow
    lifecycle with truly-terminal terminals; four per-status lifecycle
    timestamps. Parent-child relationships to conversations and the
    master-plan reference book live in ``refs``, not as FK columns.
    """

    __tablename__ = "projects"

    project_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="planned"
    )
    project_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    project_description: Mapped[str] = mapped_column(Text, nullable=False)
    project_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PI-183 / DEC-423: the ADO risk gate. Controls whether the ADO Project
    # Manager dispatcher may dispatch this Project's Planning Items. A PI may
    # override with a more restrictive value; its effective mode is resolved in
    # the access layer. NOT NULL, defaults to ``ado`` (free dispatch).
    project_execution_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ado", server_default="ado"
    )
    project_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    project_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    project_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    project_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("project_identifier", ["PRJ"]),
            name="ck_project_identifier_format",
        ),
        CheckConstraint(
            _check_in("project_status", PROJECT_STATUSES),
            name="ck_project_status",
        ),
        CheckConstraint(
            _check_in("project_execution_mode", EXECUTION_MODES),
            name="ck_project_execution_mode",
        ),
        Index("ix_projects_project_status", "project_status"),
        Index("ix_projects_project_deleted_at", "project_deleted_at"),
    )


class Workstream(EngagementScopedPKMixin, Base):
    """Governance entity — a single delivery phase of one Planning Item.

    PI-112 Phase 4 (DEC-343/DEC-349). The NEW meaning of "Workstream" (the
    old thematic container was renamed Project). Belongs to exactly one
    Planning Item via a ``workstream_belongs_to_planning_item`` edge in
    ``refs`` (not an FK). ``WSK-NNN`` identifier. Phase type is a controlled
    vocabulary; lifecycle is the ADO gate model
    Planned → Scoping → Ready → In Progress → Complete | Not Applicable |
    Blocked (WTK-001, design §5). ``needs_attention`` is an orthogonal
    human-escape flag (DEC-359) overlaying the status: it can be raised at any
    lifecycle point without erasing the underlying progress state, is set by
    the Lead/PM, and is cleared by a human after resolving so the lifecycle
    resumes from where it was.
    """

    __tablename__ = "workstreams"

    workstream_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    workstream_phase_type: Mapped[str] = mapped_column(String(32), nullable=False)
    workstream_title: Mapped[str] = mapped_column(String(255), nullable=False)
    workstream_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    workstream_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="Planned"
    )
    workstream_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    workstream_needs_attention: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    workstream_needs_attention_reason: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
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

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("workstream_identifier", ["WSK"]),
            name="ck_workstream_identifier_format",
        ),
        CheckConstraint(
            _check_in("workstream_phase_type", WORKSTREAM_PHASE_TYPES),
            name="ck_workstream_phase_type",
        ),
        CheckConstraint(
            _check_in("workstream_status", WORKSTREAM_STATUSES),
            name="ck_workstream_status",
        ),
        Index("ix_workstreams_workstream_status", "workstream_status"),
        Index("ix_workstreams_workstream_deleted_at", "workstream_deleted_at"),
    )


class WorkTask(EngagementScopedPKMixin, Base):
    """Governance entity — a single-area unit of execution within a Workstream.

    PI-112 Phase 4b (DEC-342). Carries exactly one ``area`` (the field
    relocated off the Planning Item, validated at the access layer against
    System ∪ Engagement areas) and is agent-claimable via ``claimed_by`` /
    ``claimed_at``. Belongs to exactly one Workstream via a
    ``work_task_belongs_to_workstream`` edge in ``refs``. ``WTK-NNN`` identifier.
    """

    __tablename__ = "work_tasks"

    work_task_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    work_task_title: Mapped[str] = mapped_column(String(255), nullable=False)
    work_task_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_task_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="Planned"
    )
    # Single area (hard constraint, DEC-342). Membership in System ∪ Engagement
    # areas is enforced at the access layer (a CHECK cannot consult the
    # per-engagement engagement_areas table).
    work_task_area: Mapped[str] = mapped_column(String(64), nullable=False)
    work_task_claimed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    work_task_claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_task_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_task_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    work_task_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    work_task_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_task_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    work_task_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("work_task_identifier", ["WTK"]),
            name="ck_work_task_identifier_format",
        ),
        CheckConstraint(
            _check_in("work_task_status", WORK_TASK_STATUSES),
            name="ck_work_task_status",
        ),
        CheckConstraint(
            "(work_task_claimed_by IS NULL AND work_task_claimed_at IS NULL) OR "
            "(work_task_claimed_by IS NOT NULL AND work_task_claimed_at IS NOT NULL)",
            name="ck_work_task_claim_pairing",
        ),
        Index("ix_work_tasks_work_task_status", "work_task_status"),
        Index("ix_work_tasks_work_task_area", "work_task_area"),
        Index("ix_work_tasks_work_task_deleted_at", "work_task_deleted_at"),
    )


class Release(EngagementScopedPKMixin, Base):
    """Governance entity — the multi-agent release pipeline keystone (PI-205).

    PRJ-031. A born-early forming container (REQ-209) whose ``release_status``
    *is* its pipeline stage over the 12-value lifecycle
    preliminary_planning → development_planning → reconciliation →
    architecture_planning → ready → development → qa → testing → deployment →
    shipped (+ cancelled / superseded). The four lane states
    (development..deployment) are the exclusive development lane held by one
    release until it ships (REQ-189) — enforced by the access-layer occupancy
    check at ``ready → development`` and, as a concurrency-safe structural
    backstop, the ``uq_releases_one_in_lane`` partial unique index. Three gated
    transitions: freeze (→ reconciliation; stamps ``release_frozen_at``),
    planned-completely (→ ready; stamps ``release_planned_completely_at``), and
    single-occupancy (→ development). Lane entry is by ``release_lane_order`` +
    ``blocked_by`` (REQ-210). Composition (release-scoped Projects, lane order)
    lives in ``refs``, not FK columns. See
    pi-205-release-entity-architecture.md.
    """

    __tablename__ = "releases"

    release_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    release_title: Mapped[str] = mapped_column(String(255), nullable=False)
    release_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="preliminary_planning"
    )
    release_description: Mapped[str] = mapped_column(Text, nullable=False)
    release_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The human-set lane-entry sequence (REQ-210); NULL until ordered.
    release_lane_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # The freeze stamp (§9A/§16.7) — also the boundary marking post-freeze
    # versions as frozen drafts (read by PI-208).
    release_frozen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_planned_completely_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # PI-206: release-level QA/test gate stamps (§8). qa_passed gates
    # qa→testing; test_passed gates testing→deployment; both cleared on a rework
    # bounce-back to development.
    release_qa_passed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_test_passed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_shipped_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    release_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    release_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    release_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("release_identifier", ["REL"]),
            name="ck_release_identifier_format",
        ),
        CheckConstraint(
            _check_in("release_status", RELEASE_STATUSES),
            name="ck_release_status",
        ),
        Index("ix_releases_release_status", "release_status"),
        Index("ix_releases_release_deleted_at", "release_deleted_at"),
        # Single-occupancy of the development lane (REQ-189): at most one live
        # release per engagement in a lane state. Partial unique on both
        # dialects; the primary enforcement is the access-layer check, this is
        # the concurrency-safe backstop under BEGIN IMMEDIATE.
        Index(
            "uq_releases_one_in_lane",
            "engagement_id",
            unique=True,
            sqlite_where=text(
                "release_status IN ('development','qa','testing','deployment') "
                "AND release_deleted_at IS NULL"
            ),
            postgresql_where=text(
                "release_status IN ('development','qa','testing','deployment') "
                "AND release_deleted_at IS NULL"
            ),
        ),
    )


class ArtifactVersion(EngagementScopedMixin, Base):
    """The versioned, release-tied change spine (PI-208 / PRJ-031, DEC-503).

    One generic version store (§16.4 refined by DEC-503): each row is a complete
    JSON ``snapshot`` of one versioned artifact at one ``version_number``, tied to
    the ``release_identifier`` that introduced it. Numbering is per-artifact
    monotonic (the UNIQUE constraint guards it); the live/current definition is
    the highest version whose release has shipped (computed in the repository, not
    stored). Outside the refs/change_log discipline — the version rows are the
    audit trail. See pi-208-versioning-spine-architecture.md.
    """

    __tablename__ = "artifact_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    release_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "release_identifier"],
            ["releases.engagement_id", "releases.release_identifier"],
            name="fk_artifact_versions_release",
        ),
        UniqueConstraint(
            "engagement_id",
            "artifact_type",
            "artifact_identifier",
            "version_number",
            name="uq_artifact_versions_number",
        ),
        CheckConstraint(
            _check_in("artifact_type", VERSIONED_ARTIFACT_TYPES),
            name="ck_artifact_version_type",
        ),
        CheckConstraint(
            "version_number >= 1", name="ck_artifact_version_number_positive"
        ),
        Index(
            "ix_artifact_versions_artifact",
            "engagement_id",
            "artifact_type",
            "artifact_identifier",
        ),
    )


class ReconciliationConflict(EngagementScopedMixin, Base):
    """A same-facet contradiction between requirements' demands (PI-215, §5.4).

    PRJ-031, §16.5 (RC-4). The reconciliation engine emits one row per
    unresolved same-facet contradiction on a shared artifact; it is settled by a
    governed decision (``resolving_decision_identifier``), never by the reconciler
    itself. Keyed UNIQUE per (release, artifact, facet) so re-runs upsert.
    Engagement-scoped satellite, surrogate PK, composite FK to ``releases``;
    outside the refs/change_log discipline. See
    pi-215-reconciliation-engine-architecture.md.
    """

    __tablename__ = "reconciliation_conflicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    facet: Mapped[str] = mapped_column(String(128), nullable=False)
    conflict_type: Mapped[str] = mapped_column(String(24), nullable=False)
    competing: Mapped[list] = mapped_column(JSONColumn, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )
    resolved_value: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    resolving_decision_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "release_identifier"],
            ["releases.engagement_id", "releases.release_identifier"],
            name="fk_reconciliation_conflicts_release",
        ),
        UniqueConstraint(
            "engagement_id",
            "release_identifier",
            "artifact_type",
            "artifact_identifier",
            "facet",
            name="uq_reconciliation_conflicts_locus",
        ),
        CheckConstraint(
            _check_in("status", RECONCILIATION_CONFLICT_STATUSES),
            name="ck_reconciliation_conflict_status",
        ),
        CheckConstraint(
            _check_in("conflict_type", RECONCILIATION_CONFLICT_TYPES),
            name="ck_reconciliation_conflict_type",
        ),
        Index(
            "ix_reconciliation_conflicts_release_status",
            "engagement_id",
            "release_identifier",
            "status",
        ),
    )


class AreaReopen(EngagementScopedMixin, Base):
    """An in-lane reopen of a frozen area (PI-212 / PRJ-034, RW2/RW3).

    While ``open`` the area is thawing and its downstream areas (higher
    SYSTEM_AREA_RANKS rank) are paused; ``resolved`` re-freezes it and the
    downstream resumes. Engagement-scoped satellite, surrogate PK, composite FK to
    ``releases``; outside the refs/change_log discipline. See
    pi-212-area-reopen-architecture.md.
    """

    __tablename__ = "area_reopens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )
    # PI-213 (RW4): the full downstream cascade required to re-validate, and the
    # subset that has re-passed. Set at reopen; the release cannot ship until
    # cascade_areas ⊆ revalidated_areas (no exemption).
    cascade_areas: Mapped[list] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    revalidated_areas: Mapped[list] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    # PI-214 (RW5): the blast-radius-derived approval tier, the approving decision
    # (null only for lead_auto), and the triggering finding.
    approval_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="lead_auto"
    )
    approval_decision_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    triggering_finding_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "release_identifier"],
            ["releases.engagement_id", "releases.release_identifier"],
            name="fk_area_reopens_release",
        ),
        CheckConstraint(
            _check_in("status", AREA_REOPEN_STATUSES),
            name="ck_area_reopen_status",
        ),
        CheckConstraint(
            _check_in("approval_tier", REOPEN_APPROVAL_TIERS),
            name="ck_area_reopen_approval_tier",
        ),
        Index(
            "ix_area_reopens_release_status",
            "engagement_id",
            "release_identifier",
            "status",
        ),
    )


class PlanningAreaClaim(EngagementScopedMixin, Base):
    """Single-threaded-by-area planning claim (PI-207 / PRJ-031, DEC-505).

    The committed-temperature substrate (§5.1, §11.8 / REQ-195): within a frozen
    release's planning window (reconciliation / architecture_planning), each area's
    planning work is owned by one agent. ``UNIQUE(engagement_id,
    release_identifier, area)`` enforces single-threaded-by-area; the access layer
    additionally gates that the release is in the committed planning window.
    Outside the refs/change_log discipline. See
    pi-207-two-temperature-planning-architecture.md.
    """

    __tablename__ = "planning_area_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_identifier: Mapped[str] = mapped_column(String(32), nullable=False)
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["engagement_id", "release_identifier"],
            ["releases.engagement_id", "releases.release_identifier"],
            name="fk_planning_area_claims_release",
        ),
        UniqueConstraint(
            "engagement_id",
            "release_identifier",
            "area",
            name="uq_planning_area_claims_one_owner",
        ),
        Index(
            "ix_planning_area_claims_release",
            "engagement_id",
            "release_identifier",
        ),
    )


class Finding(EngagementScopedPKMixin, Base):
    """Governance entity — a cross-area coherence finding (PI-134, DEC-400).

    REQ-031..036 / TOP-010: at the end of Design, the area specifications for a
    Planning Item are checked against each other; each problem found is recorded
    as a finding naming its kind and the specifications it involves. ``FND-NNN``
    identifier. Four ``finding_type`` values (REQ-032), two ``finding_severity``
    values (REQ-033), and a three-state ``finding_status`` lifecycle
    open → referred → resolved (REQ-034/035) — only ``resolved`` is terminal and
    opens the Develop gate; ``open`` and ``referred`` both hold it. The
    specifications a finding involves and what resolved it are ``refs`` edges
    (``finding_relates_to`` / ``finding_resolved_by``), not FKs.
    """

    __tablename__ = "findings"

    finding_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    finding_type: Mapped[str] = mapped_column(String(16), nullable=False)
    finding_severity: Mapped[str] = mapped_column(String(16), nullable=False)
    finding_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="open"
    )
    finding_summary: Mapped[str] = mapped_column(String(255), nullable=False)
    finding_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # How a blocking finding was settled (REQ-034) — recorded at resolution.
    finding_resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_resolution_method: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    finding_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    finding_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    finding_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    finding_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finding_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("finding_identifier", ["FND"]),
            name="ck_finding_identifier_format",
        ),
        CheckConstraint(
            _check_in("finding_type", FINDING_TYPES), name="ck_finding_type"
        ),
        CheckConstraint(
            _check_in("finding_severity", FINDING_SEVERITIES),
            name="ck_finding_severity",
        ),
        CheckConstraint(
            _check_in("finding_status", FINDING_STATUSES), name="ck_finding_status"
        ),
        CheckConstraint(
            "finding_resolution_method IS NULL OR "
            + _check_in("finding_resolution_method", FINDING_RESOLUTION_METHODS),
            name="ck_finding_resolution_method",
        ),
        Index("ix_findings_finding_status", "finding_status"),
        Index("ix_findings_finding_severity", "finding_severity"),
        Index("ix_findings_finding_deleted_at", "finding_deleted_at"),
    )


class Conversation(EngagementScopedPKMixin, Base):
    """Governance entity — one focused topical discussion within a session.

    Redesigned in PI-073 / DEC-314. A conversation is a topical sub-unit
    of a session — one session contains one or more conversations. Each
    has its own six-status lifecycle including the ``not_started``
    terminal for conversations planned within a session that never opened.
    Identifier prefix is ``CNV-NNN`` (distinct from the legacy ``CONV-NNN``
    sessions, which are migrated separately by Phase F). Session
    membership, cross-session continuity (follows_from/relates_to), and
    supersession all live in ``refs``.
    """

    __tablename__ = "conversations"

    conversation_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    # PI-alpha: Text (conversation titles reach ~1.2k chars in real data).
    conversation_title: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_description: Mapped[str] = mapped_column(Text, nullable=False)
    conversation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conversation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # PI-074 carry-over field. Old SES-NNN rows under v0.7 carried
    # executive_summary; they become conversations under PI-073's
    # redesign. The CHECK length budget (200–800) parallels session_*.
    conversation_executive_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    conversation_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="planned"
    )
    conversation_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    conversation_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        onupdate=_utcnow,
    )
    conversation_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_in_flight_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_not_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    conversation_superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Identifier-prefix asymmetry per conversation-v2.md §3.1:
        # legacy SES-NNN rows migrate INTO this table as conversations,
        # retaining their identifier; new conversations use CNV-NNN.
        CheckConstraint(
            _IdentifierFormatCheck("conversation_identifier", ["CNV", "SES"]),
            name="ck_conversation_identifier_format",
        ),
        CheckConstraint(
            _check_in("conversation_status", CONVERSATION_STATUSES),
            name="ck_conversation_status",
        ),
        # PI-074 CHECK on executive_summary length.
        CheckConstraint(
            "conversation_executive_summary IS NULL OR "
            "(length(conversation_executive_summary) >= 200 "
            "AND length(conversation_executive_summary) <= 800)",
            name="ck_conversation_executive_summary_length",
        ),
        Index("ix_conversations_conversation_status", "conversation_status"),
        Index(
            "ix_conversations_conversation_deleted_at",
            "conversation_deleted_at",
        ),
    )


class ReferenceBook(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("reference_book_identifier", ["RB"]),
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


class ReferenceBookVersion(EngagementScopedMixin, Base):
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
    # FK to the parent's composite PK ``(engagement_id, reference_book_identifier)``
    # is declared as a ForeignKeyConstraint in __table_args__ (the parent PK is
    # composite under PI-123); the column itself carries no single-column FK.
    reference_book_identifier: Mapped[str] = mapped_column(
        String(32),
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
        ForeignKeyConstraint(
            ["engagement_id", "reference_book_identifier"],
            [
                "reference_books.engagement_id",
                "reference_books.reference_book_identifier",
            ],
            ondelete="CASCADE",
            name="fk_reference_book_versions_parent",
        ),
        UniqueConstraint(
            "engagement_id",
            "reference_book_identifier",
            "reference_book_version_label",
            name="uq_reference_book_version",
        ),
        Index(
            "ix_reference_book_versions_parent",
            "engagement_id",
            "reference_book_identifier",
        ),
    )


class WorkTicket(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("work_ticket_identifier", ["WT"]),
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


class CloseOutPayload(EngagementScopedPKMixin, Base):
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
            _IdentifierFormatCheck("close_out_payload_identifier", ["COP"]),
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


class DepositEvent(EngagementScopedPKMixin, Base):
    """Governance entity — one durable record of a close_out_payload apply.

    Sixth of six governance entity types (UI v0.7). Born-terminal
    append-only: no ``_updated_at``, no ``_deleted_at``, one ``_created_at``
    timestamp. Carries an ``_outcome`` enum (``success`` | ``failure``)
    rather than a transitioning ``_status``. Three diagnostic JSON fields.
    Created exclusively via POST; never updated or deleted.

    ``deposit_event_kind`` (WTK-089 §4.1, D3) discriminates the
    close-out-payload apply shape from the Phase 1.5 ``audit_deposit``
    shape — set at POST, never changed. The kind-conditional rules
    (parent-edge requirement vs prohibition, ``apply_context`` required
    keys) are enforced at the repository layer; the ``DEP-NNN``
    identifier sequence is shared across kinds.
    """

    __tablename__ = "deposit_events"

    deposit_event_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    deposit_event_title: Mapped[str] = mapped_column(String(255), nullable=False)
    deposit_event_description: Mapped[str] = mapped_column(Text, nullable=False)
    deposit_event_kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="close_out_apply"
    )
    deposit_event_outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    deposit_event_records_summary: Mapped[dict] = mapped_column(
        JSONColumn, nullable=False
    )
    deposit_event_error_info: Mapped[dict | None] = mapped_column(
        JSONColumn, nullable=True
    )
    deposit_event_apply_context: Mapped[dict] = mapped_column(JSONColumn, nullable=False)
    deposit_event_log_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    deposit_event_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("deposit_event_identifier", ["DEP"]),
            name="ck_deposit_event_identifier_format",
        ),
        CheckConstraint(
            _check_in("deposit_event_outcome", DEPOSIT_EVENT_OUTCOMES),
            name="ck_deposit_event_outcome",
        ),
        CheckConstraint(
            _check_in("deposit_event_kind", DEPOSIT_EVENT_KINDS),
            name="ck_deposit_event_kind",
        ),
        Index("ix_deposit_events_deposit_event_outcome", "deposit_event_outcome"),
        Index("ix_deposit_events_deposit_event_kind", "deposit_event_kind"),
        Index(
            "ix_deposit_events_deposit_event_created_at",
            "deposit_event_created_at",
        ),
    )


class Commit(EngagementScopedPKMixin, Base):
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
        String(64), nullable=False
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
        JSONColumn, nullable=False, default=list
    )
    commit_files_changed_count: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    # Soft FK to conversations.conversation_identifier — access-layer
    # validated, not SQL-level FK per V2 convention. Direct FK column on
    # this dense entity per DEC-199's frequency-justified deviation from
    # DEC-124's references-edge precedent.
    commit_session_id: Mapped[str] = mapped_column(
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
            _IdentifierFormatCheck("commit_identifier", ["CM"], 4),
            name="ck_commit_identifier_format",
        ),
        # Lowercase 40-char hex SHA-1. SHA-256 widening anticipated in
        # commit.md §3.8.2.
        CheckConstraint(
            _LowerHexCheck("commit_sha", length=40),
            name="ck_commit_sha_format",
        ),
        CheckConstraint(
            "commit_files_changed_count >= 0",
            name="ck_commit_files_changed_count_nonneg",
        ),
        UniqueConstraint(
            "engagement_id", "commit_sha", name="uq_commit_engagement_sha"
        ),
        Index("ix_commits_commit_session_id", "commit_session_id"),
        Index("ix_commits_commit_repository", "commit_repository"),
        Index("ix_commits_commit_committed_at", "commit_committed_at"),
        Index("ix_commits_commit_deleted_at", "commit_deleted_at"),
    )


class Reference(EngagementScopedMixin, Base):
    """Universal polymorphic reference between two records (DEC-006)."""

    __tablename__ = "refs"  # avoid SQL reserved word "references"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # v0.7: prefixed external identifier (REF-NNNN) so individual reference
    # rows can be targeted by deposit_event `deposit_event_wrote_record`
    # back-references. Server-assigned on insert; back-filled by id order for
    # existing rows (migration 0011). Nullable at the column level because the
    # back-fill runs after the column is added; the access layer always sets it.
    reference_identifier: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # PI-alpha: String(64) — the longest vocab kind is 42 chars
    # (close_out_payload_produced_by_conversation); String(32) under-sized it.
    relationship_kind: Mapped[str] = mapped_column(String(64), nullable=False)
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
            # REF-NNNN is nullable before server assignment.
            _IdentifierFormatCheck(
                "reference_identifier", ["REF"], 4, allow_null=True
            ),
            name="ck_ref_reference_identifier_format",
        ),
        # REF-NNNN is server-assigned per engagement → composite unique (D3).
        UniqueConstraint(
            "engagement_id",
            "reference_identifier",
            name="uq_ref_reference_identifier",
        ),
        # The same edge may exist independently in two engagements (D4).
        UniqueConstraint(
            "engagement_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            "relationship_kind",
            name="uq_ref_full",
        ),
        Index("ix_refs_source", "engagement_id", "source_type", "source_id"),
        Index("ix_refs_target", "engagement_id", "target_type", "target_id"),
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


class ChangeLog(EngagementScopedMixin, Base):
    """Append-only change log emitted by every mutating access-layer call."""

    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # PI-alpha: Text — for reference rows this holds the long composite edge
    # descriptor (e.g. "deposit_event:DEP-148 -[...]-> decision:DEC-376"), which
    # exceeds 64 chars; SQLite ignored the cap, Postgres enforces it.
    entity_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[str] = mapped_column(String(8), nullable=False)
    actor: Mapped[str] = mapped_column(String(32), nullable=False)
    # PI-γ: which principal made the change (soft reference — a plain string,
    # not a FK, so the append-only audit log outlives a deleted principal row).
    # NULL for pre-PI-γ rows and for changes made with no active principal.
    principal_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    before_payload: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    after_payload: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)

    __table_args__ = (
        CheckConstraint(
            _check_in("entity_type", CHANGE_LOG_ENTITY_TYPES),
            name="ck_changelog_entity_type",
        ),
        CheckConstraint(
            _check_in("operation", CHANGE_LOG_OPERATIONS), name="ck_changelog_operation"
        ),
        CheckConstraint(_check_in("actor", CHANGE_LOG_ACTORS), name="ck_changelog_actor"),
        Index("ix_changelog_timestamp", "timestamp"),
        Index("ix_changelog_entity", "entity_type", "entity_identifier"),
        Index("ix_changelog_engagement", "engagement_id"),
    )


class ReviewSignoff(EngagementScopedMixin, Base):
    """Recorded review attestation (requirements-provenance Phase 6).

    "Reviewed, not reviewable": a PM's dated, on-the-record statement that a
    topic's requirement set matched intent at review time. Append-only — an
    attestation is history, never edited — so it joins the mechanical/append-only
    family alongside ``utilization_evidence`` (integer surrogate PK, no prefixed
    identifier, no ``_updated_at`` / ``_deleted_at``).
    ``signoff_reviewed_requirements`` snapshots the (identifier, status) pairs
    attested, so later drift away from that snapshot is detectable.
    """

    __tablename__ = "review_signoffs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signoff_topic_identifier: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    signoff_reviewer: Mapped[str] = mapped_column(Text, nullable=False)
    signoff_attestation: Mapped[str] = mapped_column(Text, nullable=False)
    signoff_reviewed_requirements: Mapped[list] = mapped_column(
        JSONColumn, nullable=False, default=list
    )
    signoff_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_review_signoffs_topic", "signoff_topic_identifier"),
    )


class UtilizationEvidence(EngagementScopedMixin, Base):
    """Append-only utilization-evidence snapshot for one baseline candidate.

    PI-153 / WTK-088 design spec §4 (D2). One row = one profiling
    measurement of one Phase 1.5 capture record (entity, field, persona,
    process, manual_config) at one source snapshot, written mechanically
    by the audit deposit path (or a standalone re-profile). Joins the
    mechanical-table family (``change_log``, ``identifier_reservations``):
    integer surrogate PK, no prefixed identifier, polymorphic soft subject
    reference (``evidence_subject_type`` + ``evidence_subject_identifier``)
    outside the refs discipline. Append-only — no ``_updated_at`` /
    ``_deleted_at``; re-profiles append new rows and history accumulates by
    design (the drift-detection input). Subject existence/liveness/type-match
    is validated at the repository layer (invariant I9); the typed metric
    columns are nullable because evidence is shape-heterogeneous (entity
    rows use the record-count pair, field rows the population trio, enum
    fields additionally the option pair) — everything else lives in
    ``evidence_detail`` until a triage query needs it indexed.
    """

    __tablename__ = "utilization_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    evidence_subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_subject_identifier: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    # Snapshot timestamp of the *source data* — when the profiler read the
    # source system, not when this row was written (WTK-088 §4.3).
    evidence_profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # Denormalized human-readable source identity, e.g.
    # "espocrm @ crm.cbmentors.org"; the depositing event's apply_context
    # carries the authoritative identity (WTK-089 invariant I5).
    evidence_source_label: Mapped[str] = mapped_column(Text, nullable=False)
    # Soft reference to the depositing deposit_event — nullable because a
    # standalone re-profile (drift check) may run outside a deposit.
    evidence_deposit_event_identifier: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    evidence_catalog_class: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    evidence_record_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    evidence_last_record_created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_populated_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    # Stored (not derived at query time) so the headline triage query
    # ("all fields under 5% population") is a flat indexed comparison.
    evidence_population_rate: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    evidence_last_populated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    evidence_distinct_value_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    evidence_declared_option_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    evidence_used_option_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    evidence_detail: Mapped[dict | None] = mapped_column(
        JSONColumnNoneAsNull, nullable=True
    )
    evidence_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _check_in("evidence_subject_type", EVIDENCE_SUBJECT_TYPES),
            name="ck_evidence_subject_type",
        ),
        CheckConstraint(
            _IdentifierFormatCheck(
                "evidence_deposit_event_identifier", ["DEP"], allow_null=True
            ),
            name="ck_evidence_deposit_event_identifier_format",
        ),
        CheckConstraint(
            "evidence_catalog_class IS NULL OR "
            + _check_in("evidence_catalog_class", frozenset({"standard", "custom"})),
            name="ck_evidence_catalog_class",
        ),
        CheckConstraint(
            "evidence_record_count >= 0", name="ck_evidence_record_count_nonneg"
        ),
        CheckConstraint(
            "evidence_populated_count >= 0",
            name="ck_evidence_populated_count_nonneg",
        ),
        CheckConstraint(
            "evidence_population_rate >= 0.0 AND evidence_population_rate <= 1.0",
            name="ck_evidence_population_rate_range",
        ),
        CheckConstraint(
            "evidence_distinct_value_count >= 0",
            name="ck_evidence_distinct_value_count_nonneg",
        ),
        CheckConstraint(
            "evidence_declared_option_count >= 0",
            name="ck_evidence_declared_option_count_nonneg",
        ),
        CheckConstraint(
            "evidence_used_option_count >= 0",
            name="ck_evidence_used_option_count_nonneg",
        ),
        # The latest-snapshot lookup (WTK-088 §4.4): greatest profiled_at
        # per (subject_type, subject_identifier, source_label).
        Index(
            "ix_utilization_evidence_subject",
            "evidence_subject_type",
            "evidence_subject_identifier",
            "evidence_profiled_at",
        ),
        Index(
            "ix_utilization_evidence_population_rate", "evidence_population_rate"
        ),
        Index(
            "ix_utilization_evidence_deposit_event",
            "evidence_deposit_event_identifier",
        ),
        Index("ix_utilization_evidence_engagement", "engagement_id"),
    )


class IdentifierReservation(EngagementScopedMixin, Base):
    """A server-side hold on a block of prefixed identifiers (PI-078).

    The parallel-agent orchestrator reserves a block of identifiers (e.g.
    the next five ``SES-NNN``) at the start of a run so concurrent child
    agents never race on next-available numbers. Each row is one reserved
    block for one ``entity_type``. ``max_number`` is the highest numeric
    suffix in the block; the reservation logic treats an *unexpired* block
    as "taken" when computing the next free number, so two reservations
    never overlap. Expired blocks are ignored (and garbage-collected),
    which is the TTL auto-release. Reservations are ephemeral runtime
    state — not governance records — so they are not exported to the JSON
    snapshots.
    """

    __tablename__ = "identifier_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reserved_identifiers: Mapped[list] = mapped_column(JSONColumn, nullable=False)
    max_number: Mapped[int] = mapped_column(Integer, nullable=False)
    reserved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index(
            "ix_identifier_reservations_lookup",
            "engagement_id",
            "entity_type",
            "expires_at",
        ),
    )


# ---------------------------------------------------------------------------
# Engagement registry — the tenant table (PI-123 Slice 1, DEC-375 / D1).
#
# The unified multi-engagement DB holds the engagements registry as an in-DB
# table on this one ``Base`` so the scoped tables' ``engagement_id`` columns
# can FK to it. The ``/engagements`` REST API serves this table directly (PI-β
# removed the former separate "meta DB" and its parallel ``EngagementRow`` /
# Alembic chain). It is what ``Base.metadata.create_all`` and the main Alembic
# chain (migration ``0037``) materialise.
# ---------------------------------------------------------------------------


class EngagementRow(Base):
    """Row in the unified DB's ``engagements`` tenant table.

    Named ``EngagementRow`` to stay distinct from the access-layer dataclass
    ``Engagement`` in ``engagement_models.py``.
    """

    __tablename__ = "engagements"

    engagement_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    engagement_code: Mapped[str] = mapped_column(String(16), nullable=False)
    engagement_name: Mapped[str] = mapped_column(String(255), nullable=False)
    engagement_purpose: Mapped[str] = mapped_column(Text, nullable=False)
    engagement_status: Mapped[str] = mapped_column(String(16), nullable=False)
    engagement_last_opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


# ---------------------------------------------------------------------------
# Identity / authentication / RBAC (PI-γ — PRJ-019 / PI-127).
#
# System/shared tables (NOT engagement-scoped): a principal spans engagements,
# and its per-engagement rights live in ``role_assignments``. These plain
# ``Base`` tables carry no ``engagement_id`` discriminator, so the row-level
# scope filter/stamp never touches them.
# ---------------------------------------------------------------------------


class PrincipalRow(Base):
    """An authenticated actor — a human user or an AI service agent (PI-γ D-γ1)."""

    __tablename__ = "principals"

    principal_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    # Email for humans / agent label for service agents.
    identity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    # Service agents note their ADO tier/area for the registry (PI-122).
    agent_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    agent_area: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("principal_id", ["PRN"]),
            name="ck_principal_identifier_format",
        ),
        CheckConstraint(
            "kind IN ('human', 'service_agent')",
            name="ck_principal_kind",
        ),
        CheckConstraint(
            "status IN ('active', 'disabled')",
            name="ck_principal_status",
        ),
        Index("ix_principals_status", "status"),
        Index("ix_principals_kind", "kind"),
    )


class ApiTokenRow(Base):
    """A hashed bearer token for a principal (PI-γ D-γ1).

    Only the SHA-256 hash of the high-entropy token is stored; the plaintext is
    shown once at mint time. Lookup hashes the presented bearer and matches on
    ``token_hash`` (deterministic, O(1) — appropriate for high-entropy machine
    tokens; KDF stretching would break the lookup and buys nothing here).
    """

    __tablename__ = "api_tokens"

    token_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.principal_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("token_id", ["TOK"], digits=4),
            name="ck_api_token_identifier_format",
        ),
        CheckConstraint(
            _LowerHexCheck("token_hash", length=64),
            name="ck_api_token_hash_hex",
        ),
        UniqueConstraint("token_hash", name="ux_api_tokens_hash"),
        Index("ix_api_tokens_principal", "principal_id"),
    )


class RoleAssignmentRow(Base):
    """A principal's role on one engagement (PI-γ D-γ3).

    Rights are per-engagement: ``(principal_id, engagement_id, role)`` is unique.
    ``role`` is CHECK-constrained to ``RBAC_ROLES``.
    """

    __tablename__ = "role_assignments"

    role_assignment_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    principal_id: Mapped[str] = mapped_column(
        ForeignKey("principals.principal_id", ondelete="CASCADE"),
        nullable=False,
    )
    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('owner', 'editor', 'viewer', 'orchestrator', "
            "'pi_lead', 'phase_specialist', 'area_specialist')",
            name="ck_role_assignment_role",
        ),
        UniqueConstraint(
            "principal_id",
            "engagement_id",
            "role",
            name="ux_role_assignments_principal_engagement_role",
        ),
        Index("ix_role_assignments_principal", "principal_id"),
        Index("ix_role_assignments_engagement", "engagement_id"),
    )


# ---------------------------------------------------------------------------
# Agent Profile Registry (PI-122 — the ADO §10 follow-on).
#
# System/shared tables with a NULLABLE engagement_id (D-δ2): NULL = a system
# (universal) row, set = an engagement overlay. Plain Base, NOT
# EngagementScopedMixin — the resolver does the scope merge explicitly, so
# system rows stay visible and the engagement_id discriminator is not
# overloaded (mirrors PI-γ's role_assignments).
# ---------------------------------------------------------------------------


class AgentProfileRow(Base):
    """An ADO agent profile, keyed to an (area × tier) cell (PI-122 D-δ1/D-δ3)."""

    __tablename__ = "agent_profiles"

    identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    engagement_id: Mapped[str | None] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=True,
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("identifier", ["AGP"]),
            name="ck_agent_profile_identifier_format",
        ),
        CheckConstraint(_check_in("tier", AGENT_PROFILE_TIERS), name="ck_agent_profile_tier"),
        CheckConstraint(_check_in("status", REGISTRY_STATUSES), name="ck_agent_profile_status"),
        Index("ix_agent_profiles_engagement", "engagement_id"),
        Index("ix_agent_profiles_area_tier", "area", "tier"),
    )


class SkillRow(Base):
    """A shared, reusable capability definition (PI-122 D-δ1; PRD §4/§7.2)."""

    __tablename__ = "skills"

    identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    engagement_id: Mapped[str | None] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # I/O contract (JSON schema) for tool-backed skills; backing callable pointer.
    io_contract: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    backing_callable: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("identifier", ["SKL"]),
            name="ck_skill_identifier_format",
        ),
        CheckConstraint(_check_in("kind", SKILL_KINDS), name="ck_skill_kind"),
        CheckConstraint(_check_in("status", REGISTRY_STATUSES), name="ck_skill_status"),
        Index("ix_skills_engagement", "engagement_id"),
    )


class GovernanceRuleRow(Base):
    """A shared, reusable governance rule (PI-122 D-δ1; PRD §4/§5)."""

    __tablename__ = "governance_rules"

    identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    engagement_id: Mapped[str | None] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=True,
    )
    rule_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enforcement: Mapped[str] = mapped_column(String(24), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured predicate for enforced rules (the access layer largely enforces).
    predicate: Mapped[dict | None] = mapped_column(JSONColumn, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("identifier", ["GVR"]),
            name="ck_governance_rule_identifier_format",
        ),
        CheckConstraint(
            _check_in("enforcement", RULE_ENFORCEMENT_MODES),
            name="ck_governance_rule_enforcement",
        ),
        CheckConstraint(_check_in("status", REGISTRY_STATUSES), name="ck_governance_rule_status"),
        Index("ix_governance_rules_engagement", "engagement_id"),
    )


class LearningRow(Base):
    """An accumulated, evidence-tagged learning (PI-122 slice 3; PRD §13.2).

    The table lands with the catalog migration so the change_log/refs CHECK
    rebuild happens once; its repository, edges, and write-back lifecycle are
    built in PI-122 slice 3.
    """

    __tablename__ = "learnings"

    identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    engagement_id: Mapped[str | None] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=True,
    )
    area: Mapped[str] = mapped_column(String(64), nullable=False)
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    # Derived from evidence count/spread (PRD §13.2); 0 until evidence links.
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("identifier", ["LRN"]),
            name="ck_learning_identifier_format",
        ),
        CheckConstraint(_check_in("tier", LEARNING_TIERS), name="ck_learning_tier"),
        CheckConstraint(_check_in("category", LEARNING_CATEGORIES), name="ck_learning_category"),
        CheckConstraint(_check_in("status", LEARNING_STATUSES), name="ck_learning_status"),
        Index("ix_learnings_engagement", "engagement_id"),
        Index("ix_learnings_area_tier", "area", "tier"),
    )


# ---------------------------------------------------------------------------
# Glossary term (PI-061 — DEC-403/DEC-390).
#
# One glossary definition. System/shared with a NULLABLE engagement_id: NULL =
# a system (universal) term visible to every engagement, set = an engagement
# overlay seen only by that engagement. Plain Base, NOT EngagementScopedMixin —
# the repository merges the scope explicitly, the same pattern the Agent Profile
# Registry uses. Definitions live only here. See methodology-schema-specs/term.md.
# ---------------------------------------------------------------------------


class TermRow(Base):
    """One glossary term definition (PI-061)."""

    __tablename__ = "terms"

    identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    engagement_id: Mapped[str | None] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    # The glossary "Scope" field (where the term applies); named usage_scope so
    # it does not collide with the system/engagement scope discriminator (DEC-404).
    usage_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    examples: Mapped[str | None] = mapped_column(Text, nullable=True)
    distinguishing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Names of related terms, plain text mirroring the markdown glossary (DEC-404).
    related_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("identifier", ["TERM"]),
            name="ck_term_identifier_format",
        ),
        CheckConstraint(_check_in("status", TERM_STATUSES), name="ck_term_status"),
        Index("ix_terms_engagement", "engagement_id"),
        Index("ix_terms_name", "name"),
    )
