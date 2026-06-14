"""Message-template endpoints (PRJ-025 PI-189 slice 3).

The eight standard methodology routes for the notification/communication
design record (``engine-neutral-design-model-and-adapters.md`` §8). Each
delegates to :mod:`crmbuilder_v2.access.repositories.message_template`; bodies
use the parent-prefixed ``message_template_*`` field names. Error responses use
the v2 ``{data, meta, errors}`` envelope, except disallowed status transitions
(the ``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import message_template
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    MessageTemplateCreateIn,
    MessageTemplatePatchIn,
    MessageTemplateReplaceIn,
)

router = APIRouter(prefix="/message-templates", tags=["message-templates"])

_PREFIX = "message_template_"


@router.get("")
def list_all(
    entity: str | None = None,
    channel: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            message_template.list_message_templates(
                s,
                entity=entity,
                channel=channel,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``MSG-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {"next": message_template.next_message_template_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = message_template.get_message_template(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("message_template", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: MessageTemplateCreateIn):
    with writable_session() as s:
        return ok(
            message_template.create_message_template(
                s,
                name=body.message_template_name,
                body=body.message_template_body,
                entity=body.message_template_entity,
                channel=body.message_template_channel,
                subject=body.message_template_subject,
                merge_fields=body.message_template_merge_fields,
                audience=body.message_template_audience,
                description=body.message_template_description,
                notes=body.message_template_notes,
                status=body.message_template_status,
                identifier=body.message_template_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: MessageTemplateReplaceIn):
    with writable_session() as s:
        return ok(
            message_template.update_message_template(
                s,
                identifier,
                message_template_identifier=body.message_template_identifier,
                name=body.message_template_name,
                body=body.message_template_body,
                entity=body.message_template_entity,
                channel=body.message_template_channel,
                subject=body.message_template_subject,
                merge_fields=body.message_template_merge_fields,
                audience=body.message_template_audience,
                description=body.message_template_description,
                notes=body.message_template_notes,
                status=body.message_template_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: MessageTemplatePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            message_template.patch_message_template(s, identifier, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(message_template.delete_message_template(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(message_template.restore_message_template(s, identifier))
