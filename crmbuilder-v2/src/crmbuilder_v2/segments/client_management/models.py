"""Client Management tables (PI-508 / REQ-591): the engagement registry row,
the principal, the access token, the role assignment and the participant.

Built on the one ``Base`` from ``access.base``; the shared ``access.models``
module re-exports these names and loads this module last so the tables
register on ``Base.metadata`` for Alembic and ``create_all``. This module
never imports ``access.models``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from crmbuilder_v2.access.base import (
    Base,
    EngagementScopedPKMixin,
    _IdentifierFormatCheck,
    _LowerHexCheck,
    _utcnow,
)
from crmbuilder_v2.access.vocab import _check_in
from crmbuilder_v2.segments.client_management.vocab import (
    CLIENT_STATUSES,
    PARTICIPANT_STATUSES,
)

__all__ = [
    "ApiTokenRow",
    "ClientRow",
    "EngagementClientRow",
    "EngagementRow",
    "Participant",
    "PrincipalRow",
    "RoleAssignmentRow",
]


class Participant(EngagementScopedPKMixin, Base):
    """Methodology entity — the real engagement participant a Persona backs.

    REL-040 / PI-094 (REQ-412). Domain discovery surfaces real engagement
    participants (Implementation Consultant, Client Administrator, Client
    SME, Technical Administrator, Methodology Author, CRM Researcher,
    Custom Developer, …) that a methodology ``Persona`` (the abstract role
    in requirements) can be *backed by*. This is distinct from a
    ``principal`` (an authenticated actor with tokens/RBAC) and a ``role``
    (an engine-neutral CRM security role) — a participant is a governance-
    layer record of the person/role in the engagement.

    Follows the parent-prefix field-naming convention: every column is
    prefixed ``participant_``. The primary key is the prefixed-string
    identifier ``participant_identifier`` (format ``PTC-NNN``) with the
    engagement discriminator, per :class:`EngagementScopedPKMixin`.

    The persona-backing link lives in the ``refs`` table as
    ``persona_backed_by_participant`` (source persona → target
    participant); there is no FK column here.
    """

    __tablename__ = "participants"

    participant_identifier: Mapped[str] = mapped_column(
        String(32), primary_key=True
    )
    participant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    participant_role_kind: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    participant_affiliation: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    participant_contact: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    participant_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    participant_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active"
    )
    participant_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    participant_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    participant_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # ``^PTC-\d{3}$`` expressed as a SQLite GLOB pattern.
        CheckConstraint(
            _IdentifierFormatCheck("participant_identifier", ["PTC"]),
            name="ck_participant_identifier_format",
        ),
        CheckConstraint(
            _check_in("participant_status", PARTICIPANT_STATUSES),
            name="ck_participant_status",
        ),
        Index("ix_participants_participant_status", "participant_status"),
        Index(
            "ix_participants_participant_deleted_at", "participant_deleted_at"
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
# Client (PI-512 / REQ-589, DEC-1092): the organisation above the engagement.
#
# System-wide like the principal: the table is not engagement-scoped and the
# scope filter (which acts only on ``EngagementScopedMixin`` tables) leaves it
# alone. One client holds many engagements; a chapter engagement serves
# several clients. The link is one table, ``engagement_clients``, with one
# primary row per engagement (design note, shape A). The client repository
# emits no change-log rows in this planning item, matching the engagement
# record (DEC-1092, question 4).
# ---------------------------------------------------------------------------


class ClientRow(Base):
    """Row in the system-wide ``clients`` table."""

    __tablename__ = "clients"

    client_identifier: Mapped[str] = mapped_column(String(32), primary_key=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_status: Mapped[str] = mapped_column(String(16), nullable=False)
    client_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    client_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )
    client_deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            _IdentifierFormatCheck("client_identifier", ["CLI"]),
            name="ck_client_identifier_format",
        ),
        CheckConstraint(
            _check_in("client_status", CLIENT_STATUSES),
            name="ck_client_status",
        ),
        Index("ux_clients_name_lower", text("LOWER(client_name)"), unique=True),
        Index("ix_clients_status", "client_status"),
        Index("ix_clients_deleted_at", "client_deleted_at"),
    )


class EngagementClientRow(Base):
    """One row per (engagement, client) pair in ``engagement_clients``.

    An ordinary engagement has one row, marked primary. A chapter engagement
    has one row per member client, one of them primary for display. An
    engagement with no client has no rows.
    """

    __tablename__ = "engagement_clients"

    engagement_id: Mapped[str] = mapped_column(
        ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
        primary_key=True,
    )
    client_id: Mapped[str] = mapped_column(
        ForeignKey("clients.client_identifier", ondelete="RESTRICT"),
        primary_key=True,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index(
            "ux_engagement_clients_one_primary",
            "engagement_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary"),
        ),
        Index("ix_engagement_clients_client", "client_id"),
    )
