"""Work tickets endpoints — the fourth governance entity type (UI v0.7).

Standard eight-endpoint set per ``work_ticket.md`` §3.5, with the list
endpoint's ``?kind=`` and ``?status=`` filters.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import work_tickets
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    WorkTicketCreateIn,
    WorkTicketPatchIn,
    WorkTicketReplaceIn,
)

router = APIRouter(prefix="/work-tickets", tags=["work-tickets"])
_FIELD_PREFIX = "work_ticket_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    kind: str | None = None,
    status: str | None = None,
):
    with readonly_session() as s:
        return ok(
            work_tickets.list_work_tickets(
                s, include_deleted=include_deleted, kind=kind, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": work_tickets.next_work_ticket_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = work_tickets.get_work_ticket(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("work_ticket", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: WorkTicketCreateIn):
    with writable_session() as s:
        return ok(
            work_tickets.create_work_ticket(
                s,
                title=body.work_ticket_title,
                description=body.work_ticket_description,
                kind=body.work_ticket_kind,
                file_path=body.work_ticket_file_path,
                notes=body.work_ticket_notes,
                status=body.work_ticket_status or "drafted",
                identifier=body.work_ticket_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: WorkTicketReplaceIn):
    with writable_session() as s:
        return ok(
            work_tickets.update_work_ticket(
                s,
                identifier,
                work_ticket_identifier=body.work_ticket_identifier,
                title=body.work_ticket_title,
                description=body.work_ticket_description,
                kind=body.work_ticket_kind,
                file_path=body.work_ticket_file_path,
                notes=body.work_ticket_notes,
                status=body.work_ticket_status,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: WorkTicketPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            work_tickets.patch_work_ticket(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(work_tickets.delete_work_ticket(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(work_tickets.restore_work_ticket(s, identifier))
