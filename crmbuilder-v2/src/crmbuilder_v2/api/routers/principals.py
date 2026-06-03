"""Identity / RBAC admin endpoints (PI-γ — PRJ-019 / PI-127).

The owner-only management surface for principals, role assignments, and bearer
tokens, plus the ADO orchestrator's agent-minting endpoint (D-γ4). All routes
are gated by ``require_permission("admin")`` — a no-op when
``principal_auth_enabled`` is off (so the localhost flow can provision the first
owner + token), owner-only once auth is on.

Minted token plaintext is returned **once** at creation; only its hash is
stored. There is no endpoint to read a token's plaintext back.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from crmbuilder_v2.access import principal as principal_repo
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.principal_deps import require_permission

router = APIRouter(prefix="/admin", tags=["meta"])

_admin = Depends(require_permission("admin"))


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


def _principal_dict(row) -> dict:
    return {
        "principal_id": row.principal_id,
        "kind": row.kind,
        "display_name": row.display_name,
        "identity": row.identity,
        "status": row.status,
        "agent_tier": row.agent_tier,
        "agent_area": row.agent_area,
    }


def _token_dict(row) -> dict:
    return {
        "token_id": row.token_id,
        "principal_id": row.principal_id,
        "label": row.label,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
        "last_used_at": (
            row.last_used_at.isoformat() if row.last_used_at else None
        ),
    }


# --------------------------------------------------------------------------
# Principals
# --------------------------------------------------------------------------
@router.get("/principals", dependencies=[_admin])
def list_principals():
    with readonly_session() as s:
        return ok([_principal_dict(p) for p in principal_repo.list_principals(s)])


@router.post("/principals", status_code=201, dependencies=[_admin])
def create_principal(body: PrincipalCreateIn):
    with writable_session() as s:
        row = principal_repo.create_principal(
            s,
            kind=body.kind,
            display_name=body.display_name,
            identity=body.identity,
            status=body.status,
            agent_tier=body.agent_tier,
            agent_area=body.agent_area,
            principal_id=body.principal_id,
        )
        return ok(_principal_dict(row))


@router.post(
    "/principals/{principal_id}/roles", status_code=201, dependencies=[_admin]
)
def assign_role(principal_id: str, body: RoleAssignIn):
    with writable_session() as s:
        row = principal_repo.assign_role(
            s,
            principal_id=principal_id,
            engagement_id=body.engagement_id,
            role=body.role,
        )
        return ok(
            {
                "role_assignment_id": row.role_assignment_id,
                "principal_id": row.principal_id,
                "engagement_id": row.engagement_id,
                "role": row.role,
            }
        )


@router.post("/principals/{principal_id}/disable", dependencies=[_admin])
def disable_principal(principal_id: str):
    with writable_session() as s:
        return ok(_principal_dict(principal_repo.disable_principal(s, principal_id)))


# --------------------------------------------------------------------------
# Tokens
# --------------------------------------------------------------------------
@router.get("/tokens", dependencies=[_admin])
def list_tokens(principal_id: str | None = None):
    with readonly_session() as s:
        return ok(
            [_token_dict(t) for t in principal_repo.list_tokens(s, principal_id=principal_id)]
        )


@router.post("/tokens", status_code=201, dependencies=[_admin])
def mint_token(body: TokenMintIn):
    with writable_session() as s:
        minted = principal_repo.mint_token(
            s, principal_id=body.principal_id, label=body.label
        )
        # Plaintext returned ONCE — never retrievable again.
        return ok(
            {
                "token_id": minted.token_id,
                "principal_id": minted.principal_id,
                "token": minted.plaintext,
            }
        )


@router.delete("/tokens/{token_id}", dependencies=[_admin])
def revoke_token(token_id: str):
    with writable_session() as s:
        return ok(_token_dict(principal_repo.revoke_token(s, token_id)))


# --------------------------------------------------------------------------
# Agents (ADO orchestrator — D-γ4)
# --------------------------------------------------------------------------
@router.post("/agents", status_code=201, dependencies=[_admin])
def mint_agent(body: AgentMintIn):
    """Mint an engagement-scoped service-agent principal + token in one call.

    Returns the principal record plus the one-time token plaintext for injection
    into the agent's contract.
    """
    with writable_session() as s:
        agent_row, minted = principal_repo.mint_agent_principal(
            s,
            engagement_id=body.engagement_id,
            role=body.role,
            agent_tier=body.agent_tier,
            agent_area=body.agent_area,
            display_name=body.display_name,
            label=body.label,
        )
        return ok(
            {
                "principal": _principal_dict(agent_row),
                "token_id": minted.token_id,
                "token": minted.plaintext,
            }
        )
