"""Participants endpoints — the engagement-participant methodology entity.

REL-040 / PI-094 (REQ-412). The eight standard methodology-entity
endpoints. Each delegates to
:mod:`crmbuilder_v2.access.repositories.participant`; request/response
bodies use the parent-prefixed ``participant_*`` field names. Error
responses use the v2 ``{data, meta, errors}`` envelope, except
disallowed status transitions, which the dedicated
``status_transition_handler`` renders with the spec's
``{"error": ..., "from": ..., "to": ...}`` shape.

The persona-backing reference is not inlined here: a Persona attaches its
backing via the existing ``POST /references`` route with the
``persona_backed_by_participant`` relationship kind.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import participant
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ParticipantCreateIn,
    ParticipantPatchIn,
    ParticipantReplaceIn,
)

router = APIRouter(prefix="/participants", tags=["participants"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "participant_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            participant.list_participants(s, include_deleted=include_deleted)
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``PTC-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": participant.next_participant_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = participant.get_participant(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("participant", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ParticipantCreateIn):
    with writable_session() as s:
        return ok(
            participant.create_participant(
                s,
                name=body.participant_name,
                role_kind=body.participant_role_kind,
                affiliation=body.participant_affiliation,
                contact=body.participant_contact,
                notes=body.participant_notes,
                status=body.participant_status,
                identifier=body.participant_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ParticipantReplaceIn):
    with writable_session() as s:
        return ok(
            participant.update_participant(
                s,
                identifier,
                participant_identifier=body.participant_identifier,
                name=body.participant_name,
                role_kind=body.participant_role_kind,
                affiliation=body.participant_affiliation,
                contact=body.participant_contact,
                notes=body.participant_notes,
                status=body.participant_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ParticipantPatchIn):
    # ``exclude_unset`` keeps an explicit ``participant_notes: null``
    # (clear) distinct from an omitted ``participant_notes`` (leave
    # unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(participant.patch_participant(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(participant.delete_participant(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(participant.restore_participant(s, identifier))
