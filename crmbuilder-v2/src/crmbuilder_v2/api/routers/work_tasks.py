"""Work Task endpoints — PI-112 Phase 4b governance entity.

The standard eight-endpoint set plus claim/release, delegating to
:mod:`crmbuilder_v2.access.repositories.work_tasks`. Bodies may carry an inline
``references`` array (the ``work_task_belongs_to_workstream`` edge) and, on a
backfill create, a ``timestamps`` dict. All responses use the envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import work_tasks
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.principal_deps import enforce_claim_identity
from crmbuilder_v2.api.schemas import (
    WorkTaskClaimIn,
    WorkTaskCreateIn,
    WorkTaskPatchIn,
    WorkTaskReplaceIn,
)

router = APIRouter(prefix="/work-tasks", tags=["work_tasks"])
_FIELD_PREFIX = "work_task_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False, status: str | None = None, area: str | None = None
):
    with readonly_session() as s:
        return ok(
            work_tasks.list_work_tasks(
                s, include_deleted=include_deleted, status=status, area=area
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": work_tasks.next_work_task_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = work_tasks.get_work_task(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("work_task", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: WorkTaskCreateIn):
    with writable_session() as s:
        return ok(
            work_tasks.create_work_task(
                s,
                title=body.work_task_title,
                area=body.work_task_area,
                description=body.work_task_description,
                notes=body.work_task_notes,
                status=body.work_task_status or "Planned",
                identifier=body.work_task_identifier,
                resolved_agent_profile=body.work_task_resolved_agent_profile,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: WorkTaskReplaceIn):
    with writable_session() as s:
        return ok(
            work_tasks.update_work_task(
                s,
                identifier,
                work_task_identifier=body.work_task_identifier,
                title=body.work_task_title,
                area=body.work_task_area,
                description=body.work_task_description,
                notes=body.work_task_notes,
                status=body.work_task_status,
                resolved_agent_profile=body.work_task_resolved_agent_profile,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: WorkTaskPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            work_tasks.patch_work_task(s, identifier, references=references, **fields)
        )


@router.post("/{identifier}/claim")
def claim(identifier: str, body: WorkTaskClaimIn):
    # PI-γ: an agent may only claim as itself (no-op when auth is off).
    enforce_claim_identity(body.claimed_by)
    with writable_session() as s:
        return ok(
            work_tasks.claim_work_task(s, identifier, claimed_by=body.claimed_by)
        )


@router.post("/{identifier}/release")
def release(identifier: str, body: WorkTaskClaimIn):
    enforce_claim_identity(body.claimed_by)
    with writable_session() as s:
        return ok(
            work_tasks.release_work_task(s, identifier, claimed_by=body.claimed_by)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(work_tasks.delete_work_task(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(work_tasks.restore_work_task(s, identifier))
