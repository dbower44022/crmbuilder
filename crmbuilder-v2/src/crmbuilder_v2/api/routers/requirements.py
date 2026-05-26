"""Requirements endpoints — PI-004 cohort methodology entity (v0.5+).

The eight standard endpoints from ``requirement.md`` §3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.requirement`
repository; request/response bodies use the parent-prefixed
``requirement_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status
transitions which the dedicated ``status_transition_handler``
renders with the spec's ``{"error": ..., "from": ..., "to": ...}``
shape.

Per ``requirement.md`` §3.5.5 reference handling is decomposed: there
are no ``/requirements/{id}/scopes`` shortcut endpoints and no
inline-affiliation fields in the create/update bodies. All five
outbound reference kinds (``requirement_scopes_to_domain``,
``requirement_touches_entity``, ``requirement_touches_field``,
``requirement_realized_by_process``,
``requirement_verified_by_test_spec``) attach via the existing
``POST /references`` route.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import requirement
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    RequirementCreateIn,
    RequirementPatchIn,
    RequirementReplaceIn,
)

router = APIRouter(prefix="/requirements", tags=["requirements"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "requirement_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            requirement.list_requirements(s, include_deleted=include_deleted)
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``REQ-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": requirement.next_requirement_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = requirement.get_requirement(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("requirement", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: RequirementCreateIn):
    with writable_session() as s:
        return ok(
            requirement.create_requirement(
                s,
                name=body.requirement_name,
                description=body.requirement_description,
                acceptance_summary=body.requirement_acceptance_summary,
                priority=body.requirement_priority,
                notes=body.requirement_notes,
                status=body.requirement_status,
                identifier=body.requirement_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: RequirementReplaceIn):
    with writable_session() as s:
        return ok(
            requirement.update_requirement(
                s,
                identifier,
                requirement_identifier=body.requirement_identifier,
                name=body.requirement_name,
                description=body.requirement_description,
                acceptance_summary=body.requirement_acceptance_summary,
                priority=body.requirement_priority,
                notes=body.requirement_notes,
                status=body.requirement_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: RequirementPatchIn):
    # ``exclude_unset`` keeps an explicit ``requirement_notes: null``
    # (clear) distinct from an omitted ``requirement_notes`` (leave
    # unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(requirement.patch_requirement(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(requirement.delete_requirement(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(requirement.restore_requirement(s, identifier))
