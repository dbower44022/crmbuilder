"""Conversations endpoints — the second governance entity type (UI v0.7).

Standard eight-endpoint set per ``conversation.md`` §3.5, with the list
endpoint's ``?workstream_identifier=`` and ``?status=`` filters.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import commits as commits_repo
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
    workstream_identifier: str | None = None,
):
    with readonly_session() as s:
        return ok(
            conversations.list_conversations(
                s,
                include_deleted=include_deleted,
                status=status,
                workstream_identifier=workstream_identifier,
            )
        )


@router.get("/next-identifier")
def next_identifier():
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


@router.get("/{conversation_identifier}/commits")
def commits_for_conversation(
    conversation_identifier: str,
    include_deleted: bool = False,
    commit_repository: str | None = None,
    sort: str = "commit_committed_at",
    order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
):
    """List every commit produced by a specific conversation.

    Derived from the standard ``/commits?commit_conversation_id=`` filter
    per DEC-211 — one-hop FK-scoped derived endpoint shipped in PI-029
    slice B. The two-hop ``/workstreams/{id}/commits`` variant was
    explicitly deferred.

    Returns 404 with ``conversation_not_found`` if the named conversation
    does not exist; returns 200 with empty array if the conversation
    exists but produced no commits.
    """
    with readonly_session() as s:
        # Existence check — uses include_deleted=True so commits attributed
        # to a soft-deleted conversation can still be listed
        # (administrative-correction case).
        conv = conversations.get_conversation(
            s, conversation_identifier, include_deleted=True
        )
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "conversation_not_found",
                    "identifier": conversation_identifier,
                },
            )
        return ok(commits_repo.list_commits(
            s,
            include_deleted=include_deleted,
            commit_conversation_id=conversation_identifier,
            commit_repository=commit_repository,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        ))
