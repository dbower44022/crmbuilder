"""Client Management request schemas (PI-508 / REQ-591): engagements,
participants, and the identity administration bodies.

The shared ``api.schemas`` module re-exports these names for the import
paths that predate the package.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Engagements (methodology entity, UI v0.5 slice B) ----------


class EngagementCreateIn(_Base):
    """POST /engagements body. ``engagement_identifier`` is server-assigned
    when omitted; ``engagement_status`` defaults to ``active`` server-side."""

    engagement_code: str
    engagement_name: str
    engagement_purpose: str
    engagement_status: str | None = None
    engagement_identifier: str | None = None


class EngagementReplaceIn(_Base):
    """PUT /engagements/{identifier} body — full record replace.

    ``engagement_identifier`` is optional; when present it must match
    the path (mismatch → 422). ``engagement_code`` is immutable: any
    value other than the current row's ``engagement_code`` raises 422
    with ``immutable_field``."""

    engagement_identifier: str | None = None
    engagement_code: str | None = None
    engagement_name: str
    engagement_purpose: str
    engagement_status: str


class EngagementPatchIn(_Base):
    """PATCH /engagements/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    omitted field is left unchanged. ``engagement_code`` is rejected if
    present and different from the current row."""

    engagement_name: str | None = None
    engagement_purpose: str | None = None
    engagement_status: str | None = None
    engagement_last_opened_at: str | None = None
    # Accepted but rejected by the repository if it differs from current.
    engagement_code: str | None = None


# ---------- Participants (methodology entity, REL-040 / PI-094) ----------


class ParticipantCreateIn(_Base):
    """POST /participants body. ``participant_identifier`` is
    server-assigned when omitted; ``participant_status`` defaults to
    ``active`` server-side.

    The persona-backing link is NOT inlined here — it attaches via a
    separate ``POST /references`` call with the
    ``persona_backed_by_participant`` relationship kind (source persona →
    target participant)."""

    participant_name: str
    participant_role_kind: str
    participant_affiliation: str | None = None
    participant_contact: str | None = None
    participant_notes: str | None = None
    participant_status: str | None = None
    participant_identifier: str | None = None


class ParticipantReplaceIn(_Base):
    """PUT /participants/{identifier} body — full record replace.

    ``participant_identifier`` is optional; when present it must match the
    path identifier (mismatch → 422). ``participant_status`` is required
    on a full replace."""

    participant_identifier: str | None = None
    participant_name: str
    participant_role_kind: str
    participant_affiliation: str | None = None
    participant_contact: str | None = None
    participant_notes: str | None = None
    participant_status: str


class ParticipantPatchIn(_Base):
    """PATCH /participants/{identifier} body — partial update.

    Routers consume this with ``model_dump(exclude_unset=True)`` so an
    explicit ``participant_notes: null`` (clear the field) is
    distinguished from an omitted ``participant_notes`` (leave
    unchanged)."""

    participant_name: str | None = None
    participant_role_kind: str | None = None
    participant_affiliation: str | None = None
    participant_contact: str | None = None
    participant_notes: str | None = None
    participant_status: str | None = None


# ---------- Identity / RBAC administration (PI-γ — PRJ-019 / PI-127) ----------


class PrincipalCreateIn(_Base):
    kind: str
    display_name: str
    identity: str
    status: str = "active"
    agent_tier: str | None = None
    agent_area: str | None = None
    principal_id: str | None = None


class RoleAssignIn(_Base):
    engagement_id: str
    role: str


class TokenMintIn(_Base):
    principal_id: str
    label: str = ""


class AgentMintIn(_Base):
    engagement_id: str
    role: str = "area_specialist"
    agent_tier: str | None = None
    agent_area: str | None = None
    display_name: str | None = None
    label: str = ""


# ---------- Clients (PI-512 / REQ-589, DEC-1092) ----------


class ClientCreateIn(_Base):
    """POST /clients body. ``client_identifier`` is server-assigned when
    omitted; ``client_status`` defaults to ``active`` server-side."""

    client_name: str
    client_notes: str | None = None
    client_status: str | None = None
    client_identifier: str | None = None


class ClientReplaceIn(_Base):
    """PUT /clients/{identifier} body, a full replace. ``client_identifier``
    is optional and must match the path when present."""

    client_identifier: str | None = None
    client_name: str
    client_notes: str | None = None
    client_status: str


class ClientPatchIn(_Base):
    """PATCH /clients/{identifier} body, a partial update; consumed with
    ``model_dump(exclude_unset=True)`` so an omitted field is unchanged."""

    client_name: str | None = None
    client_notes: str | None = None
    client_status: str | None = None


class EngagementClientsIn(_Base):
    """PUT /engagements/{identifier}/clients body: the whole set of clients
    the engagement serves, with one of them primary. An empty list means the
    engagement belongs to no client. ``primary`` must be one of ``clients``
    when the list is not empty; it defaults to the first."""

    clients: list[str]
    primary: str | None = None
