"""Workstream (delivery-phase) endpoints — PI-112 Phase 4 governance entity.

Standard eight-endpoint set delegating to
:mod:`crmbuilder_v2.access.repositories.workstreams`. Request bodies may carry
an inline ``references`` array (the ``workstream_belongs_to_planning_item`` edge
to the parent Planning Item) and, on a backfill create, a ``timestamps`` dict.
All responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import workstreams
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    WorkstreamCreateIn,
    WorkstreamPatchIn,
    WorkstreamReplaceIn,
)

router = APIRouter(prefix="/workstreams", tags=["workstreams"])
_FIELD_PREFIX = "workstream_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            workstreams.list_workstreams(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": workstreams.next_workstream_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = workstreams.get_workstream(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("workstream", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: WorkstreamCreateIn):
    with writable_session() as s:
        return ok(
            workstreams.create_workstream(
                s,
                phase_type=body.workstream_phase_type,
                title=body.workstream_title,
                description=body.workstream_description,
                notes=body.workstream_notes,
                status=body.workstream_status or "Planned",
                needs_attention=bool(body.workstream_needs_attention),
                needs_attention_reason=body.workstream_needs_attention_reason,
                identifier=body.workstream_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: WorkstreamReplaceIn):
    with writable_session() as s:
        return ok(
            workstreams.update_workstream(
                s,
                identifier,
                workstream_identifier=body.workstream_identifier,
                phase_type=body.workstream_phase_type,
                title=body.workstream_title,
                description=body.workstream_description,
                notes=body.workstream_notes,
                status=body.workstream_status,
                needs_attention=body.workstream_needs_attention,
                needs_attention_reason=body.workstream_needs_attention_reason,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: WorkstreamPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            workstreams.patch_workstream(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(workstreams.delete_workstream(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(workstreams.restore_workstream(s, identifier))
