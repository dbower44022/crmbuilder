"""Transition endpoints (PI-471, REQ-577 to REQ-586).

A transition (``TRN-NNN``) is one allowed move of a status field on an entity
within a process. Each route delegates to
:mod:`crmbuilder_v2.access.repositories.transition`; bodies use the
parent-prefixed ``transition_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status moves (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``, ``incomplete``) are declared before
``/{identifier}`` — route order is load-bearing, the ``field.py`` precedent.
The reorder route hangs off the owning process, since reordering is a
statement about the whole list rather than about one transition.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import transition
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    TransitionCreateIn,
    TransitionPatchIn,
    TransitionReorderIn,
    TransitionReplaceIn,
)

router = APIRouter(prefix="/transitions", tags=["transitions"])

_PREFIX = "transition_"


@router.get("")
def list_all(
    process: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
):
    """List transitions, in process order. Filter by ``process`` to read one
    process's status lifecycle as a single ordered list (REQ-577)."""
    with readonly_session() as s:
        return ok(
            transition.list_transitions(
                s,
                process=process,
                status=status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``TRN-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": transition.next_transition_identifier(s)})


@router.get("/incomplete")
def incomplete(process: str | None = None):
    """The incompleteness report (REQ-581): every transition whose automatic
    consequences are still described in words rather than referenced as
    records. What a person does by hand afterwards is not counted."""
    with readonly_session() as s:
        return ok(transition.incomplete_transitions(s, process=process))


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = transition.get_transition(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("transition", identifier)
        return ok(record)


def _create_kwargs(body: TransitionCreateIn | TransitionReplaceIn) -> dict:
    kwargs = {
        "process": body.transition_process,
        "field": body.transition_field,
        "to_value": body.transition_to_value,
        "from_values": body.transition_from_values,
        "actor_persona": body.transition_actor_persona,
        "actor_occasion": body.transition_actor_occasion,
        "required_fields": body.transition_required_fields,
        "precondition": body.transition_precondition,
        "consequences": body.transition_consequences,
        "consequence_notes": body.transition_consequence_notes,
        "manual_follow_up": body.transition_manual_follow_up,
        "order": body.transition_order,
        "description": body.transition_description,
        "notes": body.transition_notes,
    }
    # The two enum columns carry repository defaults; only pass them through
    # when the caller stated one, so an omitted key keeps the default.
    if body.transition_from_kind is not None:
        kwargs["from_kind"] = body.transition_from_kind
    if body.transition_actor_kind is not None:
        kwargs["actor_kind"] = body.transition_actor_kind
    return kwargs


@router.post("", status_code=201)
def create(body: TransitionCreateIn):
    with writable_session() as s:
        return ok(
            transition.create_transition(
                s,
                status=body.transition_status,
                identifier=body.transition_identifier,
                **_create_kwargs(body),
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: TransitionReplaceIn):
    with writable_session() as s:
        return ok(
            transition.update_transition(
                s,
                identifier,
                transition_identifier=body.transition_identifier,
                status=body.transition_status,
                **_create_kwargs(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: TransitionPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(transition.patch_transition(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(transition.delete_transition(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(transition.restore_transition(s, identifier))


process_scoped_router = APIRouter(prefix="/processes", tags=["transitions"])


@process_scoped_router.get("/{identifier}/transitions")
def list_for_process(identifier: str, include_deleted: bool = False):
    """The process's transitions as one ordered list (REQ-577)."""
    with readonly_session() as s:
        return ok(
            transition.list_transitions(
                s, process=identifier, include_deleted=include_deleted
            )
        )


@process_scoped_router.post("/{identifier}/transitions/order")
def reorder(identifier: str, body: TransitionReorderIn):
    """Set the order of a process's transitions (REQ-585). The body names
    every live transition of the process exactly once."""
    with writable_session() as s:
        return ok(
            transition.reorder_transitions(
                s, identifier, body.ordered_identifiers
            )
        )
