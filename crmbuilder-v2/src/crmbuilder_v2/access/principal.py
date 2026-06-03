"""Principal / API-token / role-assignment repository (PI-γ — PRJ-019 / PI-127).

The identity + RBAC access layer behind the ``resolve_principal`` chokepoint:

* ``create_principal`` / ``get_principal`` / ``list_principals`` — humans and
  service agents (system/shared table, not engagement-scoped).
* ``mint_token`` — create a token, returning the plaintext **once**; only the
  SHA-256 hash is stored. ``validate_token`` hashes a presented bearer and
  resolves it to a :class:`Principal` (active, unexpired, unrevoked), stamping
  ``last_used_at``. ``revoke_token`` stamps ``revoked_at``.
* ``assign_role`` — grant a principal a role on an engagement.
* ``mint_agent_principal`` — the ADO-orchestrator helper (PI-γ D-γ4): create a
  service-agent principal scoped to one engagement+role and a token in one go.

Tokens are high-entropy random secrets, so a single SHA-256 (not a stretched
KDF) is the correct, standard hash — it keeps token validation an O(1)
indexed lookup, and stretching buys nothing against a 256-bit random secret.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import (
    ApiTokenRow,
    PrincipalRow,
    RoleAssignmentRow,
)
from crmbuilder_v2.access.principal_scope import Principal
from crmbuilder_v2.access.vocab import (
    PRINCIPAL_KINDS,
    PRINCIPAL_STATUSES,
    RBAC_ROLES,
)

_TOKEN_PREFIX = "crmbv2"


# --------------------------------------------------------------------------
# Token hashing / generation
# --------------------------------------------------------------------------
def hash_token(plaintext: str) -> str:
    """Return the lowercase hex SHA-256 of a bearer token's plaintext."""
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_token() -> str:
    """Return a fresh high-entropy bearer token (the plaintext, shown once)."""
    return f"{_TOKEN_PREFIX}_{secrets.token_urlsafe(32)}"


@dataclass(frozen=True)
class MintedToken:
    """The result of :func:`mint_token`: the row's id plus the one-time plaintext."""

    token_id: str
    plaintext: str
    principal_id: str


# --------------------------------------------------------------------------
# Principals
# --------------------------------------------------------------------------
def next_principal_identifier(session: Session) -> str:
    rows = session.execute(select(PrincipalRow.principal_id)).scalars().all()
    return next_prefixed_identifier(rows, "PRN", width=3)


def create_principal(
    session: Session,
    *,
    kind: str,
    display_name: str,
    identity: str,
    status: str = "active",
    agent_tier: str | None = None,
    agent_area: str | None = None,
    principal_id: str | None = None,
) -> PrincipalRow:
    if kind not in PRINCIPAL_KINDS:
        raise UnprocessableError(
            [FieldError("kind", "invalid", f"kind must be one of {sorted(PRINCIPAL_KINDS)}")]
        )
    if status not in PRINCIPAL_STATUSES:
        raise UnprocessableError(
            [FieldError("status", "invalid", f"status must be one of {sorted(PRINCIPAL_STATUSES)}")]
        )
    if not display_name or not display_name.strip():
        raise UnprocessableError(
            [FieldError("display_name", "required", "display_name must be non-empty")]
        )
    if not identity or not identity.strip():
        raise UnprocessableError(
            [FieldError("identity", "required", "identity must be non-empty")]
        )
    pid = principal_id or next_principal_identifier(session)
    if session.get(PrincipalRow, pid) is not None:
        raise ConflictError(f"principal {pid!r} already exists")
    row = PrincipalRow(
        principal_id=pid,
        kind=kind,
        display_name=display_name.strip(),
        identity=identity.strip(),
        status=status,
        agent_tier=agent_tier,
        agent_area=agent_area,
    )
    session.add(row)
    session.flush()
    return row


def get_principal(session: Session, principal_id: str) -> PrincipalRow:
    row = session.get(PrincipalRow, principal_id)
    if row is None:
        raise NotFoundError("principal", principal_id)
    return row


def list_principals(session: Session) -> list[PrincipalRow]:
    return list(
        session.execute(
            select(PrincipalRow).order_by(PrincipalRow.principal_id)
        ).scalars()
    )


def disable_principal(session: Session, principal_id: str) -> PrincipalRow:
    row = get_principal(session, principal_id)
    row.status = "disabled"
    row.disabled_at = datetime.now(UTC)
    session.flush()
    return row


# --------------------------------------------------------------------------
# Role assignments
# --------------------------------------------------------------------------
def assign_role(
    session: Session,
    *,
    principal_id: str,
    engagement_id: str,
    role: str,
) -> RoleAssignmentRow:
    if role not in RBAC_ROLES:
        raise UnprocessableError(
            [FieldError("role", "invalid", f"role must be one of {sorted(RBAC_ROLES)}")]
        )
    # Principal must exist; engagement existence is enforced by the FK.
    get_principal(session, principal_id)
    existing = session.execute(
        select(RoleAssignmentRow).where(
            RoleAssignmentRow.principal_id == principal_id,
            RoleAssignmentRow.engagement_id == engagement_id,
            RoleAssignmentRow.role == role,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    row = RoleAssignmentRow(
        principal_id=principal_id,
        engagement_id=engagement_id,
        role=role,
    )
    session.add(row)
    session.flush()
    return row


def assignments_for(
    session: Session, principal_id: str
) -> list[RoleAssignmentRow]:
    return list(
        session.execute(
            select(RoleAssignmentRow).where(
                RoleAssignmentRow.principal_id == principal_id
            )
        ).scalars()
    )


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
def next_token_identifier(session: Session) -> str:
    rows = session.execute(select(ApiTokenRow.token_id)).scalars().all()
    return next_prefixed_identifier(rows, "TOK", width=4)


def mint_token(
    session: Session,
    *,
    principal_id: str,
    label: str = "",
    expires_at: datetime | None = None,
    plaintext: str | None = None,
    token_id: str | None = None,
) -> MintedToken:
    """Create a token for ``principal_id`` and return its one-time plaintext.

    ``plaintext`` may be supplied (e.g. an orchestrator injecting a known
    secret into an agent's contract); otherwise a fresh one is generated.
    """
    get_principal(session, principal_id)
    secret_plaintext = plaintext or generate_token()
    tid = token_id or next_token_identifier(session)
    if session.get(ApiTokenRow, tid) is not None:
        raise ConflictError(f"token {tid!r} already exists")
    row = ApiTokenRow(
        token_id=tid,
        principal_id=principal_id,
        token_hash=hash_token(secret_plaintext),
        label=label or "",
        expires_at=expires_at,
    )
    session.add(row)
    session.flush()
    return MintedToken(token_id=tid, plaintext=secret_plaintext, principal_id=principal_id)


def revoke_token(session: Session, token_id: str) -> ApiTokenRow:
    row = session.get(ApiTokenRow, token_id)
    if row is None:
        raise NotFoundError("api_token", token_id)
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.flush()
    return row


def list_tokens(
    session: Session, *, principal_id: str | None = None
) -> list[ApiTokenRow]:
    stmt = select(ApiTokenRow).order_by(ApiTokenRow.token_id)
    if principal_id is not None:
        stmt = stmt.where(ApiTokenRow.principal_id == principal_id)
    return list(session.execute(stmt).scalars())


def _build_principal(
    session: Session, row: PrincipalRow
) -> Principal:
    """Compose a :class:`Principal` value from a principal row + its assignments."""
    assignments = assignments_for(session, row.principal_id)
    roles_by_engagement: dict[str, set[str]] = {}
    all_roles: set[str] = set()
    for a in assignments:
        roles_by_engagement.setdefault(a.engagement_id, set()).add(a.role)
        all_roles.add(a.role)
    return Principal(
        principal_id=row.principal_id,
        kind=row.kind,
        roles=frozenset(all_roles),
        roles_by_engagement={
            eng: frozenset(roles) for eng, roles in roles_by_engagement.items()
        },
        allowed_engagements=frozenset(roles_by_engagement),
        # A principal granted ``owner`` on any engagement is treated as a
        # system owner (allowed on every engagement + the admin gate).
        all_engagements="owner" in all_roles,
    )


def validate_token(session: Session, plaintext: str) -> Principal | None:
    """Resolve a presented bearer-token plaintext to a :class:`Principal`.

    Returns ``None`` when the token is unknown, revoked, expired, or its
    principal is disabled. Stamps ``last_used_at`` on a successful match.
    """
    if not plaintext:
        return None
    token_hash = hash_token(plaintext.strip())
    row = session.execute(
        select(ApiTokenRow).where(ApiTokenRow.token_hash == token_hash)
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if row.expires_at is not None:
        # SQLite reads tz-aware columns back as naive; treat naive as UTC so the
        # comparison is dialect-safe (Postgres returns aware datetimes).
        expires = row.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= now:
            return None
    principal_row = session.get(PrincipalRow, row.principal_id)
    if principal_row is None or principal_row.status != "active":
        return None
    row.last_used_at = now
    session.flush()
    return _build_principal(session, principal_row)


# --------------------------------------------------------------------------
# Bootstrap / orchestrator helpers
# --------------------------------------------------------------------------
def get_or_create_owner(
    session: Session,
    *,
    identity: str,
    display_name: str | None = None,
) -> PrincipalRow:
    """Return the human owner principal with ``identity``, creating it if absent."""
    existing = session.execute(
        select(PrincipalRow).where(
            PrincipalRow.kind == "human",
            PrincipalRow.identity == identity,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return create_principal(
        session,
        kind="human",
        display_name=display_name or identity,
        identity=identity,
    )


def mint_agent_principal(
    session: Session,
    *,
    engagement_id: str,
    role: str,
    agent_tier: str | None = None,
    agent_area: str | None = None,
    display_name: str | None = None,
    label: str = "",
) -> tuple[PrincipalRow, MintedToken]:
    """Create an engagement-scoped service-agent principal + token (PI-γ D-γ4).

    The ADO orchestrator calls this at agent spawn: a service-agent principal
    with a single ``role`` assignment on ``engagement_id`` only, plus a token
    injected into the agent's contract. Returns ``(principal_row, minted_token)``.
    """
    if role not in RBAC_ROLES:
        raise UnprocessableError(
            [FieldError("role", "invalid", f"role must be one of {sorted(RBAC_ROLES)}")]
        )
    name = display_name or f"{role} agent on {engagement_id}"
    principal = create_principal(
        session,
        kind="service_agent",
        display_name=name,
        identity=name,
        agent_tier=agent_tier,
        agent_area=agent_area,
    )
    assign_role(
        session,
        principal_id=principal.principal_id,
        engagement_id=engagement_id,
        role=role,
    )
    minted = mint_token(
        session,
        principal_id=principal.principal_id,
        label=label or f"agent token for {principal.principal_id}",
    )
    return principal, minted
