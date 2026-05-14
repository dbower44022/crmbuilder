"""Entities endpoints — the second methodology entity type (UI v0.4 slice C).

The eight standard endpoints from ``entity.md`` section 3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.entity`
repository; request/response bodies use the parent-prefixed
``entity_*`` field names. Error responses use the v2 envelope, except
disallowed status transitions, which the dedicated
``status_transition_handler`` renders with the spec's
``{"error": ..., "from": ..., "to": ...}`` shape.

Per ``entity.md`` section 3.5.4 reference handling is decomposed: there
is no ``/entities/{id}/scopes`` shortcut and no inline-affiliation field
in the create/update bodies. Domain affiliations attach via the
existing ``POST /references`` route with the ``entity_scopes_to_domain``
relationship kind.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import entity
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    EntityCreateIn,
    EntityPatchIn,
    EntityReplaceIn,
)

router = APIRouter(prefix="/entities", tags=["entities"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "entity_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(entity.list_entities(s, include_deleted=include_deleted))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``ENT-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": entity.next_entity_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = entity.get_entity(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("entity", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: EntityCreateIn):
    with writable_session() as s:
        return ok(
            entity.create_entity(
                s,
                name=body.entity_name,
                description=body.entity_description,
                notes=body.entity_notes,
                status=body.entity_status,
                identifier=body.entity_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: EntityReplaceIn):
    with writable_session() as s:
        return ok(
            entity.update_entity(
                s,
                identifier,
                entity_identifier=body.entity_identifier,
                name=body.entity_name,
                description=body.entity_description,
                notes=body.entity_notes,
                status=body.entity_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: EntityPatchIn):
    # ``exclude_unset`` keeps an explicit ``entity_notes: null`` (clear)
    # distinct from an omitted ``entity_notes`` (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(entity.patch_entity(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(entity.delete_entity(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(entity.restore_entity(s, identifier))
