"""Personas endpoints — the fifth methodology entity type (v0.5+, PI-003).

The eight standard endpoints from ``persona.md`` §3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.persona`
repository; request/response bodies use the parent-prefixed
``persona_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status
transitions, which the dedicated ``status_transition_handler``
renders with the spec's ``{"error": ..., "from": ..., "to": ...}``
shape.

Per ``persona.md`` §3.5.4 reference handling is decomposed: there is
no ``/personas/{id}/scopes`` or ``/personas/{id}/realizes`` shortcut
and no inline-affiliation or inline-realization fields in the create
/ update bodies. Domain affiliations and entity realizations attach
via the existing ``POST /references`` route with the
``persona_scopes_to_domain`` and ``persona_realized_as_entity``
relationship kinds.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import persona
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    PersonaCreateIn,
    PersonaPatchIn,
    PersonaReplaceIn,
)

router = APIRouter(prefix="/personas", tags=["personas"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "persona_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(persona.list_personas(s, include_deleted=include_deleted))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``PER-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": persona.next_persona_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = persona.get_persona(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("persona", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: PersonaCreateIn):
    with writable_session() as s:
        return ok(
            persona.create_persona(
                s,
                name=body.persona_name,
                role_summary=body.persona_role_summary,
                responsibilities=body.persona_responsibilities,
                notes=body.persona_notes,
                status=body.persona_status,
                identifier=body.persona_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: PersonaReplaceIn):
    with writable_session() as s:
        return ok(
            persona.update_persona(
                s,
                identifier,
                persona_identifier=body.persona_identifier,
                name=body.persona_name,
                role_summary=body.persona_role_summary,
                responsibilities=body.persona_responsibilities,
                notes=body.persona_notes,
                status=body.persona_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: PersonaPatchIn):
    # ``exclude_unset`` keeps an explicit ``persona_notes: null``
    # (clear) distinct from an omitted ``persona_notes`` (leave
    # unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(persona.patch_persona(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(persona.delete_persona(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(persona.restore_persona(s, identifier))
