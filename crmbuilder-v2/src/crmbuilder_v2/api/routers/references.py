"""References endpoints (DEC-006 universal references pattern).

References are addressed by the full tuple, not by a synthetic identifier.
There is no PATCH — to "change" a reference, delete and recreate.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import references
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import ReferenceCreateIn, ReferenceDeleteIn

router = APIRouter(prefix="/references", tags=["references"])


@router.get("")
def list_all():
    with readonly_session() as s:
        return ok(references.list_all(s))


@router.post("", status_code=201)
def create(body: ReferenceCreateIn):
    with writable_session() as s:
        return ok(references.create(s, **body.model_dump()))


@router.post("/delete")
def delete(body: ReferenceDeleteIn):
    """Delete via POST because the tuple is in the body, not the URL."""
    with writable_session() as s:
        return ok(references.delete(s, **body.model_dump()))


@router.delete("/{ref_id}")
def delete_by_id(ref_id: int):
    """Hard-delete a reference by integer primary key.

    Added in v0.3 slice C so the UI's ``ReferenceDeleteDialog`` can
    delete by the ``id`` surfaced on every list-response row, without
    re-sending the full identifying tuple.
    """
    with writable_session() as s:
        return ok(references.delete_by_id(s, ref_id))


@router.get("/from/{source_type}/{source_id}")
def list_from(source_type: str, source_id: str):
    with readonly_session() as s:
        return ok(
            references.list_from(s, source_type=source_type, source_id=source_id)
        )


@router.get("/to/{target_type}/{target_id}")
def list_to(target_type: str, target_id: str):
    with readonly_session() as s:
        return ok(
            references.list_to(s, target_type=target_type, target_id=target_id)
        )


@router.get("/touching/{entity_type}/{entity_id}")
def list_touching(entity_type: str, entity_id: str):
    with readonly_session() as s:
        return ok(
            references.list_touching(s, entity_type=entity_type, entity_id=entity_id)
        )
