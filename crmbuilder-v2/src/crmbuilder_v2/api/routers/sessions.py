"""Sessions endpoints — PI-073 / DEC-314 redesign.

Standard nine-endpoint set for the medium-agnostic communication container
per ``session-v2.md`` §3.6. Lifecycle CRUD with the list endpoint's
``?status=``, ``?medium=``, and ``?project_identifier=`` filters, plus
the derived endpoints ``/sessions/{id}/conversations`` and
``/sessions/{id}/commits``.

Replaces the legacy POST + DELETE-only append-only router. Sessions are
now schedulable and stateful (DEC-013 superseded).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import commits as commits_repo
from crmbuilder_v2.access.repositories import conversations as conversations_repo
from crmbuilder_v2.access.repositories import session_opening, sessions
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    SessionAdvanceSegmentIn,
    SessionCreateIn,
    SessionOpenIn,
    SessionPatchIn,
    SessionReplaceIn,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
_FIELD_PREFIX = "session_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    status: str | None = None,
    medium: str | None = None,
    project_identifier: str | None = None,
):
    with readonly_session() as s:
        return ok(
            sessions.list_sessions(
                s,
                include_deleted=include_deleted,
                status=status,
                medium=medium,
                project_identifier=project_identifier,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``SES-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": sessions.next_session_identifier(s)})


@router.get("/opening")
def opening(engagement: str | None = None):
    """The opening question, its examples, the catalogue of kinds of work and
    the cross-cutting contract (PI-488). No write — what a surface needs before
    the user answers. Registered above ``/{identifier}`` so it is reachable."""
    active = engagement if engagement is not None else get_active_engagement()
    with readonly_session() as s:
        return ok(session_opening.opening(s, active))


@router.post("/open", status_code=201)
def open_session(body: SessionOpenIn):
    """The session-open operation (REQ-570..572): classify the opening answer
    against the catalogue, create the session record carrying the answer and
    the kind of work, and return the confirmation line and the first segment's
    contract merged with the cross-cutting rules. An empty answer or no
    confident match returns the cross-cutting contract only and says so; a
    miss also records a planning item."""
    active = body.engagement if body.engagement is not None else get_active_engagement()
    with writable_session() as s:
        return ok(
            session_opening.open_session(
                s,
                engagement_id=active,
                opening_answer=body.opening_answer,
                medium=body.medium,
                project_identifier=body.project_identifier,
                title=body.title,
                participants=body.participants,
                medium_metadata=body.medium_metadata,
            )
        )


@router.post("/{identifier}/advance-segment")
def advance_segment(identifier: str, body: SessionAdvanceSegmentIn | None = None):
    """The segment-advance operation (REQ-573): close the current phase segment
    with its leaving moment, open the next with its entering moment, and return
    the next segment's contract merged with the cross-cutting rules; after the
    last segment return the completed state and no contract."""
    engagement = body.engagement if body is not None else None
    active = engagement if engagement is not None else get_active_engagement()
    with writable_session() as s:
        return ok(session_opening.advance_segment(s, identifier, engagement_id=active))


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = sessions.get_session(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("session", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: SessionCreateIn):
    with writable_session() as s:
        return ok(
            sessions.create_session(
                s,
                title=body.session_title,
                description=body.session_description,
                medium=body.session_medium,
                notes=body.session_notes,
                status=body.session_status or "planned",
                scheduled_for=body.session_scheduled_for,
                started_at=body.session_started_at,
                ended_at=body.session_ended_at,
                participants=body.session_participants,
                medium_metadata=body.session_medium_metadata,
                executive_summary=body.session_executive_summary,
                identifier=body.session_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
                opening_answer=body.session_opening_answer,
                kind_of_work=body.session_kind_of_work,
                confirmation_line=body.session_confirmation_line,
                phase_segments=body.session_phase_segments,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: SessionReplaceIn):
    with writable_session() as s:
        return ok(
            sessions.update_session(
                s,
                identifier,
                session_identifier=body.session_identifier,
                title=body.session_title,
                description=body.session_description,
                medium=body.session_medium,
                notes=body.session_notes,
                status=body.session_status,
                scheduled_for=body.session_scheduled_for,
                started_at=body.session_started_at,
                ended_at=body.session_ended_at,
                participants=body.session_participants,
                medium_metadata=body.session_medium_metadata,
                executive_summary=body.session_executive_summary,
                references=_edges(body),
                opening_answer=body.session_opening_answer,
                kind_of_work=body.session_kind_of_work,
                confirmation_line=body.session_confirmation_line,
                phase_segments=body.session_phase_segments,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: SessionPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            sessions.patch_session(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(sessions.delete_session(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(sessions.restore_session(s, identifier))


@router.get("/{session_identifier}/conversations")
def conversations_for_session(
    session_identifier: str,
    include_deleted: bool = False,
    status: str | None = None,
):
    """List every conversation belonging to a specific session.

    Per session-v2.md §3.6 — derived endpoint that filters conversations
    by their inbound ``conversation_belongs_to_session`` edge. Returns
    404 with ``session_not_found`` if the named session does not exist;
    returns 200 with empty array if the session has no conversations.
    """
    with readonly_session() as s:
        sess = sessions.get_session(
            s, session_identifier, include_deleted=True
        )
        if sess is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "session_not_found",
                    "identifier": session_identifier,
                },
            )
        return ok(
            conversations_repo.list_conversations(
                s,
                include_deleted=include_deleted,
                status=status,
                session_identifier=session_identifier,
            )
        )


@router.get("/{session_identifier}/commits")
def commits_for_session(
    session_identifier: str,
    include_deleted: bool = False,
    commit_repository: str | None = None,
    sort: str = "commit_committed_at",
    order: str = "desc",
    limit: int | None = None,
    offset: int = 0,
):
    """List every commit attributed to a specific session.

    Under the PI-073 redesign, commits attribute at session-grain via the
    renamed ``commit_session_id`` FK (the legacy ``commit_conversation_id``
    pointed at the old conversation entity, which is now the session).
    Successor to the legacy ``/conversations/{id}/commits`` derived
    endpoint.
    """
    with readonly_session() as s:
        sess = sessions.get_session(
            s, session_identifier, include_deleted=True
        )
        if sess is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "session_not_found",
                    "identifier": session_identifier,
                },
            )
        return ok(commits_repo.list_commits(
            s,
            include_deleted=include_deleted,
            commit_session_id=session_identifier,
            commit_repository=commit_repository,
            sort=sort,
            order=order,
            limit=limit,
            offset=offset,
        ))
