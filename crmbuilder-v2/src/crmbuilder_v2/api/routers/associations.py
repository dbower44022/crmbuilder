"""Association endpoints (PRJ-025 PI-189 slice 1).

The eight standard methodology routes for the engine-neutral
entity-to-entity link (``engine-neutral-design-model-and-adapters.md`` §8).
Each delegates to :mod:`crmbuilder_v2.access.repositories.association`;
bodies use the parent-prefixed ``association_*`` field names. Error responses
use the v2 ``{data, meta, errors}`` envelope, except disallowed status
transitions (the ``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import association
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    AssociationCreateIn,
    AssociationPatchIn,
    AssociationReplaceIn,
)

router = APIRouter(prefix="/associations", tags=["associations"])

_PREFIX = "association_"


@router.get("")
def list_all(
    source_entity: str | None = None,
    target_entity: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            association.list_associations(
                s,
                source_entity=source_entity,
                target_entity=target_entity,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``ASN-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": association.next_association_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = association.get_association(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("association", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: AssociationCreateIn):
    with writable_session() as s:
        return ok(
            association.create_association(
                s,
                name=body.association_name,
                source_entity=body.association_source_entity,
                target_entity=body.association_target_entity,
                cardinality=body.association_cardinality,
                source_role=body.association_source_role,
                target_role=body.association_target_role,
                description=body.association_description,
                notes=body.association_notes,
                status=body.association_status,
                identifier=body.association_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: AssociationReplaceIn):
    with writable_session() as s:
        return ok(
            association.update_association(
                s,
                identifier,
                association_identifier=body.association_identifier,
                name=body.association_name,
                source_entity=body.association_source_entity,
                target_entity=body.association_target_entity,
                cardinality=body.association_cardinality,
                source_role=body.association_source_role,
                target_role=body.association_target_role,
                description=body.association_description,
                notes=body.association_notes,
                status=body.association_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: AssociationPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(association.patch_association(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(association.delete_association(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(association.restore_association(s, identifier))
