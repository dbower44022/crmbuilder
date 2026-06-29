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
def list_all(
    source_type: str | None = None,
    source_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    relationship_kind: str | None = None,
    relationship: str | None = None,
):
    """List references, optionally filtered by any tuple component.

    The filter parameters were accepted but ignored before v0.7 (gap
    surfaced during the SES-054 apply, commit ``dcb7377``); they are now
    honored server-side. No filters returns the full list.

    ``relationship`` is accepted as an alias for ``relationship_kind``
    (REQ-427): several callers (the ADO scheduler, the baseline report) and
    the documented ``?relationship=`` convention spell it that way. Without
    the alias the filter was silently dropped and the endpoint returned every
    edge to the tuple — which let an unrelated ``blocked_by`` edge leak into a
    work-task lookup and crash a scheduler run. ``relationship_kind`` wins when
    both are supplied.
    """
    with readonly_session() as s:
        return ok(
            references.list_references(
                s,
                source_type=source_type,
                source_id=source_id,
                target_type=target_type,
                target_id=target_id,
                relationship_kind=relationship_kind or relationship,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next reference primary-key ``id`` (DEC-043).

    References are tuple-identified and carry no prefixed identifier;
    this returns the next autoincrement ``id`` for API-surface
    consistency with the prefixed-identifier governance entity types.
    """
    with readonly_session() as s:
        return ok({"next": references.compute_next_identifier(s)})


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
