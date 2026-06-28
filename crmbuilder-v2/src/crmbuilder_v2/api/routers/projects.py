"""Projects endpoints — the first governance entity type (UI v0.7).

Standard eight-endpoint set per ``workstream.md`` §3.5, delegating to the
:mod:`crmbuilder_v2.access.repositories.projects` repository. Request
bodies may carry an inline ``references`` array (edges created in the same
transaction) and, on a backfill create, a ``timestamps`` dict. All responses
use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import pm, projects
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ProjectClaimIn,
    ProjectCreateIn,
    ProjectPatchIn,
    ProjectReleaseIn,
    ProjectReplaceIn,
)

router = APIRouter(prefix="/projects", tags=["projects"])
_FIELD_PREFIX = "project_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            projects.list_projects(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": projects.next_project_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = projects.get_project(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("project", identifier)
        return ok(record)


@router.get("/{identifier}/backlog")
def backlog(identifier: str):
    """The Project Manager's PI backlog (ADO §3.1): every Planning Item in the
    Project with status, blocked_by dependencies + unresolved blockers, and an
    eligible flag, plus the eligible / in_flight / blocked / resolved partitions
    and all_resolved. 404 if the Project does not exist."""
    with readonly_session() as s:
        return ok(pm.project_backlog(s, identifier))


@router.get("/{identifier}/eligible-planning-items")
def eligible_planning_items(identifier: str):
    """The Planning Items eligible to start now (dependencies satisfied,
    not yet started) — the PM prioritizes these and dispatches a Lead each."""
    with readonly_session() as s:
        return ok(pm.eligible_planning_items(s, identifier))


@router.post("", status_code=201)
def create(body: ProjectCreateIn):
    with writable_session() as s:
        return ok(
            projects.create_project(
                s,
                name=body.project_name,
                purpose=body.project_purpose,
                description=body.project_description,
                notes=body.project_notes,
                status=body.project_status or "planned",
                execution_mode=body.project_execution_mode or "ado",
                identifier=body.project_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ProjectReplaceIn):
    with writable_session() as s:
        return ok(
            projects.update_project(
                s,
                identifier,
                project_identifier=body.project_identifier,
                name=body.project_name,
                purpose=body.project_purpose,
                description=body.project_description,
                notes=body.project_notes,
                status=body.project_status,
                execution_mode=body.project_execution_mode,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ProjectPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            projects.patch_project(s, identifier, references=references, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(projects.delete_project(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(projects.restore_project(s, identifier))


@router.post("/{identifier}/claim")
def claim(identifier: str, body: ProjectClaimIn):
    """Acquire the exclusive build-run claim (heartbeat lease) — REQ-423."""
    kwargs = {"claimed_by": body.claimed_by}
    if body.stale_seconds is not None:
        kwargs["stale_seconds"] = body.stale_seconds
    with writable_session() as s:
        return ok(projects.claim_project(s, identifier, **kwargs))


@router.post("/{identifier}/heartbeat")
def heartbeat(identifier: str, body: ProjectClaimIn):
    """Refresh the build-run lease while still held — REQ-423."""
    with writable_session() as s:
        return ok(projects.heartbeat_project(s, identifier, claimed_by=body.claimed_by))


@router.post("/{identifier}/release")
def release(identifier: str, body: ProjectReleaseIn):
    """Release the build-run claim — REQ-423."""
    with writable_session() as s:
        return ok(
            projects.release_project(
                s, identifier, claimed_by=body.claimed_by, force=body.force
            )
        )
