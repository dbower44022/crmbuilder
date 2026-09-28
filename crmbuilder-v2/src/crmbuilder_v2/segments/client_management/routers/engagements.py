"""Engagement-registry REST endpoints (v0.5 slice B; PI-β: unified DB).

Eight standard endpoints per ``methodology-schema-specs/engagement.md``
§3.5.1 plus a slice-A-compatible healthcheck. PI-β: the endpoints now read/write
the **unified** DB's ``engagements`` table (the single registry the scope
resolver reads) via the normal ``readonly_session`` / ``writable_session``
dependencies — the separate meta DB is gone.

The router preserves the slice-A ``/engagements/healthcheck`` URL so
external monitors that started watching it under slice A do not break;
the canonical liveness probe is still ``/health``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.client_management.schemas import (
    DeploymentGrantIn,
    EngagementClientsIn,
    EngagementCreateIn,
    EngagementPatchIn,
    EngagementReplaceIn,
)

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.get("/healthcheck")
def healthcheck() -> dict:
    """Verify the registry is reachable; return engagement count."""
    with readonly_session() as s:
        engagements = engagement_repo.list_engagements(
            s, include_deleted=True
        )
    return ok({"status": "ok", "engagement_count": len(engagements)})


@router.get("")
def list_all(include_deleted: bool = False):
    """List engagements (default excludes soft-deleted)."""
    with readonly_session() as s:
        engagements = engagement_repo.list_engagements(
            s, include_deleted=include_deleted
        )
    return ok([e.to_dict() for e in engagements])


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``ENG-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": engagement_repo.next_engagement_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str):
    """Single engagement fetch (includes soft-deleted records)."""
    with readonly_session() as s:
        engagement = engagement_repo.get_engagement(s, identifier)
        if engagement is None:
            raise NotFoundError("engagement", identifier)
        return ok(engagement.to_dict())


@router.post("", status_code=201)
def create(body: EngagementCreateIn):
    with writable_session() as s:
        engagement = engagement_repo.create_engagement(
            s,
            engagement_code=body.engagement_code,
            engagement_name=body.engagement_name,
            engagement_purpose=body.engagement_purpose,
            engagement_status=(
                body.engagement_status
                if body.engagement_status is not None
                else "active"
            ),
            engagement_identifier=body.engagement_identifier,
            engagement_visibility=(
                body.engagement_visibility
                if body.engagement_visibility is not None
                else "private"
            ),
            engagement_defining_client=body.engagement_defining_client,
        )
    return ok(engagement.to_dict())


@router.put("/{identifier}")
def replace(identifier: str, body: EngagementReplaceIn):
    with writable_session() as s:
        engagement = engagement_repo.update_engagement(
            s,
            identifier,
            engagement_identifier=body.engagement_identifier,
            engagement_code=body.engagement_code,
            engagement_name=body.engagement_name,
            engagement_purpose=body.engagement_purpose,
            engagement_status=body.engagement_status,
            engagement_visibility=body.engagement_visibility,
            engagement_defining_client=body.engagement_defining_client,
        )
    return ok(engagement.to_dict())


@router.patch("/{identifier}")
def patch(identifier: str, body: EngagementPatchIn):
    """Partial update. ``exclude_unset`` distinguishes omitted from null."""
    provided: dict[str, Any] = body.model_dump(exclude_unset=True)
    with writable_session() as s:
        engagement = engagement_repo.patch_engagement(
            s, identifier, **provided
        )
    return ok(engagement.to_dict())


@router.delete("/{identifier}")
def delete(identifier: str):
    """Soft-delete; idempotent."""
    with writable_session() as s:
        engagement = engagement_repo.delete_engagement(s, identifier)
    return ok(engagement.to_dict())


@router.post("/{identifier}/restore")
def restore(identifier: str):
    """Clear soft-delete; 422 if not soft-deleted."""
    with writable_session() as s:
        engagement = engagement_repo.restore_engagement(s, identifier)
    return ok(engagement.to_dict())


# ---------- The clients an engagement serves (PI-512 / REQ-589) ----------


@router.get("/{identifier}/clients")
def clients_of(identifier: str):
    """The clients this engagement serves: ``clients`` (records, primary
    first) and ``primary`` (an identifier or null)."""
    with readonly_session() as s:
        return ok(client_repo.get_engagement_clients(s, identifier))


@router.put("/{identifier}/clients")
def set_clients(identifier: str, body: EngagementClientsIn):
    """Replace the set of clients this engagement serves. An empty list
    means the engagement belongs to no client."""
    with writable_session() as s:
        return ok(
            client_repo.set_engagement_clients(
                s, identifier, clients=body.clients, primary=body.primary
            )
        )


# ---------- Deployment grants (PI-588 / REQ-664, DEC-1196) ----------
# A deployment grant is a client's recorded permission to deploy a private
# application it did not define. These routes change one grant at a time
# and never move the defining client.


@router.get("/{identifier}/deployment-grants")
def deployment_grants_of(identifier: str):
    """The engagement's ``defining_client`` and the client records holding
    a deployment grant for it (``deployment_grants``)."""
    with readonly_session() as s:
        return ok(client_repo.list_deployment_grants(s, identifier))


@router.post("/{identifier}/deployment-grants")
def add_deployment_grant(identifier: str, body: DeploymentGrantIn):
    """Give a client a deployment grant. Refused for the defining client
    (``is_defining_client``), a missing client (``client_not_found``) and an
    engagement no client defines (``no_defining_client``)."""
    with writable_session() as s:
        return ok(client_repo.add_deployment_grant(s, identifier, body.client))


@router.delete("/{identifier}/deployment-grants/{client}")
def remove_deployment_grant(identifier: str, client: str):
    """Withdraw a client's deployment grant. Refused for the defining client
    (``is_defining_client``); 404 when the client holds no grant."""
    with writable_session() as s:
        return ok(client_repo.remove_deployment_grant(s, identifier, client))
