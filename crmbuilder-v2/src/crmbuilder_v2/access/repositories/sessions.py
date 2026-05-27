"""Sessions repository.

Append-only per DEC-013: create + read + delete only. No update.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_in,
    require_string,
    to_dict,
    validate_optional_length,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Session as SessionModel
from crmbuilder_v2.access.vocab import SESSION_STATUSES

_ENTITY_TYPE = "session"
_IDENTIFIER_PREFIX = "SES"
_IDENTIFIER_RE = re.compile(r"^SES-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50

_EXECUTIVE_SUMMARY_MIN = 200
_EXECUTIVE_SUMMARY_MAX = 800


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``SES-NNN`` identifier."""
    identifiers = session.scalars(select(SessionModel.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "identifier",
                    "invalid_format",
                    r"must match ^SES-\d{3}$ (e.g. SES-001)",
                )
            ]
        )
    return identifier


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


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


def _new_session_row(
    identifier: str,
    title: str,
    session_date: str,
    status: str,
    conversation_reference: str,
    topics_covered: str,
    summary: str,
    artifacts_produced: str,
    in_flight_at_end: str,
    executive_summary: str | None,
) -> SessionModel:
    return SessionModel(
        identifier=identifier,
        title=title,
        session_date=session_date,
        status=status,
        conversation_reference=conversation_reference,
        topics_covered=topics_covered,
        summary=summary,
        artifacts_produced=artifacts_produced,
        in_flight_at_end=in_flight_at_end,
        executive_summary=executive_summary,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    session_date: str,
    status: str,
    conversation_reference: str,
    topics_covered: str,
    summary: str,
    artifacts_produced: str,
    in_flight_at_end: str,
    executive_summary: str | None,
) -> SessionModel:
    """Insert a session with a server-assigned identifier, collision-safe (PI-002)."""
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_session_row(
            candidate,
            title,
            session_date,
            status,
            conversation_reference,
            topics_covered,
            summary,
            artifacts_produced,
            in_flight_at_end,
            executive_summary,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique session identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    title: str,
    session_date: str,
    status: str,
    conversation_reference: str = "",
    topics_covered: str = "",
    summary: str = "",
    artifacts_produced: str = "",
    in_flight_at_end: str = "",
    executive_summary: str | None = None,
) -> dict:
    """Create a session.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^SES-\\d{3}$`` and not already exist.

    ``executive_summary`` (PI-074) is optional in v0.8; when supplied it
    must be a 200-800 character audience-facing summary. PI-075 will
    backfill and tighten the column to NOT NULL.
    """
    require_string(title, field="title")
    require_string(session_date, field="session_date")
    require_in(status, SESSION_STATUSES, field="status")
    executive_summary = validate_optional_length(
        executive_summary,
        field="executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            title,
            session_date,
            status,
            conversation_reference or "",
            topics_covered or "",
            summary or "",
            artifacts_produced or "",
            in_flight_at_end or "",
            executive_summary,
        )
    else:
        _require_identifier_format(identifier)
        existing = session.scalar(
            select(SessionModel).where(SessionModel.identifier == identifier)
        )
        if existing is not None:
            raise ConflictError(f"session {identifier!r} already exists")
        row = _new_session_row(
            identifier,
            title,
            session_date,
            status,
            conversation_reference or "",
            topics_covered or "",
            summary or "",
            artifacts_produced or "",
            in_flight_at_end or "",
            executive_summary,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.identifier,
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
