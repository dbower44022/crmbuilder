"""Client endpoints: the organisation above the engagement (PI-512 /
REQ-589, DEC-1092). Eight standard endpoints plus a client's engagements.
Bodies use the parent-prefixed ``client_*`` field names; the repository
takes unprefixed keyword arguments.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.segments.client_management.repositories import client as client_repo
from crmbuilder_v2.segments.client_management.schemas import (
    ClientCreateIn,
    ClientPatchIn,
    ClientReplaceIn,
)

router = APIRouter(prefix="/clients", tags=["clients"])

_FIELD_PREFIX = "client_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(client_repo.list_clients(s, include_deleted=include_deleted))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``CLI-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": client_repo.next_client_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = client_repo.get_client(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("client", identifier)
        return ok(record)


@router.get("/{identifier}/engagements")
def engagements(identifier: str):
    """The engagements a client serves, with ``is_primary`` on each."""
    with readonly_session() as s:
        return ok(client_repo.list_client_engagements(s, identifier))


@router.post("", status_code=201)
def create(body: ClientCreateIn):
    with writable_session() as s:
        return ok(
            client_repo.create_client(
                s,
                name=body.client_name,
                notes=body.client_notes,
                status=body.client_status,
                identifier=body.client_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ClientReplaceIn):
    with writable_session() as s:
        return ok(
            client_repo.update_client(
                s,
                identifier,
                client_identifier=body.client_identifier,
                name=body.client_name,
                notes=body.client_notes,
                status=body.client_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ClientPatchIn):
    provided = body.model_dump(exclude_unset=True)
    fields = {key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}
    with writable_session() as s:
        return ok(client_repo.patch_client(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    """Soft-delete; refused while the client still holds engagements."""
    with writable_session() as s:
        return ok(client_repo.delete_client(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(client_repo.restore_client(s, identifier))
