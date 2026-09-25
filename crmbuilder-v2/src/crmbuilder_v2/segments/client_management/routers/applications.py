"""The application REST endpoints (PI-575 / REQ-653, DEC-1155, DEC-1183).

An application is the engagement row read with its defining client and its
visibility. ``/applications`` serves the same rows and the same record shape
as ``/engagements`` under the name the client, application and deployment
model uses, so the connector and the desktop can move to the new word
(PI-580) without a second change here. ``/engagements`` is unchanged.

Only an engagement that has a defining client is an application: the list
leaves the others out and a single fetch of one answers 422
``no_defining_client``. Creating one that names a missing or soft-deleted
client answers 422 ``client_not_found`` before any row is written.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.segments.client_management.repositories import (
    engagement as engagement_repo,
)
from crmbuilder_v2.segments.client_management.schemas import (
    ApplicationCreateIn,
    ApplicationReplaceIn,
    EngagementPatchIn,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("")
def list_all(include_deleted: bool = False, client: str | None = None):
    """List applications (default excludes soft-deleted). ``client`` narrows
    the list to the applications that client defines; 404 for an unknown
    client."""
    with readonly_session() as s:
        if client is not None:
            applications = engagement_repo.list_applications_of_client(
                s, client, include_deleted=include_deleted
            )
        else:
            applications = engagement_repo.list_applications(
                s, include_deleted=include_deleted
            )
    return ok([a.to_dict() for a in applications])


@router.get("/{identifier}")
def get(identifier: str):
    """Single application fetch (includes soft-deleted records)."""
    with readonly_session() as s:
        application = engagement_repo.get_application(s, identifier)
        if application is None:
            raise NotFoundError("application", identifier)
        return ok(application.to_dict())


@router.post("", status_code=201)
def create(body: ApplicationCreateIn):
    with writable_session() as s:
        application = engagement_repo.create_application(
            s,
            engagement_code=body.engagement_code,
            engagement_name=body.engagement_name,
            engagement_purpose=body.engagement_purpose,
            engagement_defining_client=body.engagement_defining_client,
            engagement_visibility=(
                body.engagement_visibility
                if body.engagement_visibility is not None
                else "private"
            ),
            engagement_status=(
                body.engagement_status
                if body.engagement_status is not None
                else "active"
            ),
            engagement_identifier=body.engagement_identifier,
        )
    return ok(application.to_dict())


@router.put("/{identifier}")
def replace(identifier: str, body: ApplicationReplaceIn):
    with writable_session() as s:
        application = engagement_repo.update_engagement(
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
    return ok(application.to_dict())


@router.patch("/{identifier}")
def patch(identifier: str, body: EngagementPatchIn):
    """Partial update. ``exclude_unset`` distinguishes omitted from null."""
    provided: dict[str, Any] = body.model_dump(exclude_unset=True)
    with writable_session() as s:
        application = engagement_repo.patch_engagement(s, identifier, **provided)
    return ok(application.to_dict())
