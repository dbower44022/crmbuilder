"""Automation endpoints (PRJ-025 PI-189 slice 2).

The eight standard methodology routes for the condition-carrying workflow
(``engine-neutral-design-model-and-adapters.md`` §8). Each delegates to
:mod:`crmbuilder_v2.access.repositories.automation`; bodies use the
parent-prefixed ``automation_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import automation
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    AutomationCreateIn,
    AutomationPatchIn,
    AutomationReplaceIn,
)

router = APIRouter(prefix="/automations", tags=["automations"])

_PREFIX = "automation_"


@router.get("")
def list_all(
    entity: str | None = None,
    trigger: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            automation.list_automations(
                s,
                entity=entity,
                trigger=trigger,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``AUT-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": automation.next_automation_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = automation.get_automation(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("automation", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: AutomationCreateIn):
    with writable_session() as s:
        return ok(
            automation.create_automation(
                s,
                name=body.automation_name,
                entity=body.automation_entity,
                trigger=body.automation_trigger,
                actions=body.automation_actions,
                condition=body.automation_condition,
                description=body.automation_description,
                notes=body.automation_notes,
                status=body.automation_status,
                identifier=body.automation_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: AutomationReplaceIn):
    with writable_session() as s:
        return ok(
            automation.update_automation(
                s,
                identifier,
                automation_identifier=body.automation_identifier,
                name=body.automation_name,
                entity=body.automation_entity,
                trigger=body.automation_trigger,
                actions=body.automation_actions,
                condition=body.automation_condition,
                description=body.automation_description,
                notes=body.automation_notes,
                status=body.automation_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: AutomationPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(automation.patch_automation(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(automation.delete_automation(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(automation.restore_automation(s, identifier))
