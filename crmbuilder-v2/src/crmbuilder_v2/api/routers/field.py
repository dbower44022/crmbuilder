"""Fields endpoints — the sixth methodology entity type (v0.5+, PI-004
first slice).

The eight standard endpoints from ``field.md`` §3.5.1. Each delegates
to the :mod:`crmbuilder_v2.access.repositories.field` repository;
request/response bodies use the parent-prefixed ``field_*`` field
names. Error responses use the v2 ``{data, meta, errors}`` envelope,
except disallowed status transitions which the dedicated
``status_transition_handler`` renders with the spec's
``{"error": ..., "from": ..., "to": ...}`` shape.

Per ``field.md`` §3.5.4 POST atomicity is the one cross-spec
deviation: ``POST /fields`` REQUIRES a
``field_belongs_to_entity_identifier`` body key; the access layer
creates the field row, the ``field_belongs_to_entity`` edge, and the
change-log emit in one transaction. PUT and PATCH do NOT accept the
key — reparenting requires explicit DELETE-then-POST edge management
via ``/references`` (PI-053 tracks the convenience endpoint).

The ``?entity_identifier=ENT-NNN`` list filter (spec §3.5.5) returns
only fields whose live ``field_belongs_to_entity`` edge points to the
named entity — the most common access pattern at CBM-redo scale.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import field
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FieldCreateIn,
    FieldPatchIn,
    FieldReplaceIn,
)

router = APIRouter(prefix="/fields", tags=["fields"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "field_"


@router.get("")
def list_all(
    entity_identifier: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            field.list_fields(
                s,
                entity_identifier=entity_identifier,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FLD-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": field.next_field_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = field.get_field(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("field", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FieldCreateIn):
    with writable_session() as s:
        return ok(
            field.create_field(
                s,
                field_belongs_to_entity_identifier=(
                    body.field_belongs_to_entity_identifier
                ),
                name=body.field_name,
                description=body.field_description,
                type=body.field_type,
                required=body.field_required,
                notes=body.field_notes,
                status=body.field_status,
                identifier=body.field_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FieldReplaceIn):
    with writable_session() as s:
        return ok(
            field.update_field(
                s,
                identifier,
                field_identifier=body.field_identifier,
                name=body.field_name,
                description=body.field_description,
                type=body.field_type,
                required=body.field_required,
                notes=body.field_notes,
                status=body.field_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FieldPatchIn):
    # ``exclude_unset`` keeps an explicit ``field_notes: null`` (clear)
    # distinct from an omitted ``field_notes`` (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(field.patch_field(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(field.delete_field(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(field.restore_field(s, identifier))
