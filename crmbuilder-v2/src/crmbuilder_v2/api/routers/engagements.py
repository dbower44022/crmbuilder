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

from crmbuilder_v2.access import engagement as engagement_repo
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
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
            engagement_export_dir=body.engagement_export_dir,
            engagement_identifier=body.engagement_identifier,
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
            engagement_export_dir=body.engagement_export_dir,
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
