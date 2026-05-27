"""Conversations endpoints — PI-073 / DEC-314 redesign.

Standard nine-endpoint set for the topical sub-unit per
``conversation-v2.md`` §3.6. Lifecycle CRUD with the list endpoint's
``?status=`` and ``?session_identifier=`` filters.

The old workstream_identifier filter is removed — conversations no
longer belong to workstreams directly under the redesign; they belong to
sessions, which in turn belong to workstreams. To get a workstream's
conversations, traverse via sessions: GET /sessions?workstream_identifier=X,
then GET /sessions/{ses_id}/conversations for each.

The legacy ``/conversations/{id}/commits`` derived endpoint moved to
``/sessions/{id}/commits`` per the commits-attribute-to-session semantic
shift.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import conversations
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ConversationCreateIn,
    ConversationPatchIn,
    ConversationReplaceIn,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])
_FIELD_PREFIX = "conversation_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    status: str | None = None,
    session_identifier: str | None = None,
):
    with readonly_session() as s:
        return ok(
            conversations.list_conversations(
                s,
                include_deleted=include_deleted,
                status=status,
                session_identifier=session_identifier,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``CNV-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": conversations.next_conversation_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = conversations.get_conversation(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("conversation", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ConversationCreateIn):
    with writable_session() as s:
        return ok(
            conversations.create_conversation(
                s,
                title=body.conversation_title,
                purpose=body.conversation_purpose,
                description=body.conversation_description,
                summary=body.conversation_summary,
                notes=body.conversation_notes,
                status=body.conversation_status or "planned",
                identifier=body.conversation_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ConversationReplaceIn):
    with writable_session() as s:
        return ok(
            conversations.update_conversation(
                s,
                identifier,
                conversation_identifier=body.conversation_identifier,
                title=body.conversation_title,
                purpose=body.conversation_purpose,
                description=body.conversation_description,
                summary=body.conversation_summary,
                notes=body.conversation_notes,
                status=body.conversation_status,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ConversationPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            conversations.patch_conversation(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(conversations.delete_conversation(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(conversations.restore_conversation(s, identifier))
