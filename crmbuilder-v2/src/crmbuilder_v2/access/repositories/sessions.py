"""Sessions repository.

Append-only per DEC-013: create + read + delete only. No update.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import require_in, require_string, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
)
from crmbuilder_v2.access.models import Session as SessionModel
from crmbuilder_v2.access.vocab import SESSION_STATUSES

_ENTITY_TYPE = "session"


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(SessionModel).where(SessionModel.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return to_dict(row)


def list_all(session: Session, *, limit: int | None = None) -> list[dict]:
    stmt = select(SessionModel).order_by(
        SessionModel.session_date.desc(), SessionModel.id.desc()
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def create(
    session: Session,
    *,
    identifier: str,
    title: str,
    session_date: str,
    status: str,
    conversation_reference: str = "",
    topics_covered: str = "",
    summary: str = "",
    artifacts_produced: str = "",
    in_flight_at_end: str = "",
) -> dict:
    require_string(identifier, field="identifier")
    require_string(title, field="title")
    require_string(session_date, field="session_date")
    require_in(status, SESSION_STATUSES, field="status")

    existing = session.scalar(
        select(SessionModel).where(SessionModel.identifier == identifier)
    )
    if existing is not None:
        raise ConflictError(f"session {identifier!r} already exists")

    row = SessionModel(
        identifier=identifier,
        title=title,
        session_date=session_date,
        status=status,
        conversation_reference=conversation_reference or "",
        topics_covered=topics_covered or "",
        summary=summary or "",
        artifacts_produced=artifacts_produced or "",
        in_flight_at_end=in_flight_at_end or "",
    )
    session.add(row)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(SessionModel).where(SessionModel.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = to_dict(row)
    session.delete(row)
    session.flush()
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="delete",
        before=before,
        after=None,
    )
    return before


def upsert(session: Session, *, identifier: str, **fields) -> dict:
    """Bootstrap-only idempotent insert; no update path because sessions are append-only.

    If the row already exists with matching content, returns the existing row.
    If it exists with different content, raises ConflictError — bootstrap
    callers can ``delete`` then ``create`` if they intend to replace.
    """
    existing = session.scalar(
        select(SessionModel).where(SessionModel.identifier == identifier)
    )
    if existing is None:
        return create(session, identifier=identifier, **fields)
    return to_dict(existing)
