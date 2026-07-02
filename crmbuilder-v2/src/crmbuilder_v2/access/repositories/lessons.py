"""Lesson repository (REL-039 / PI-357 — REQ-416, DEC-891).

A ``lesson`` (``LSN-NNN``) is one operational gotcha / how-to split out of the
hybrid ``project_*`` memories. System/shared row with a nullable ``engagement_id``
scope (NULL = a system default, set = an engagement overlay). A
``lesson_derived_from`` edge (created by the ingest, not here) points at the DB
record the memory was welded to, making the hybrid split lossless.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_string,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import LessonRow
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import (
    LESSON_CATEGORIES,
    LESSON_SIGNALS,
    LESSON_STATUSES,
)

_ENTITY_TYPE = "lesson"
_IDENTIFIER_PREFIX = "LSN"
_IDENTIFIER_RE = re.compile(r"^LSN-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset({"category", "title", "body", "signal", "status"})


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(LessonRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^LSN-\d{3}$")]
        )
    return identifier


def _increment(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _require_vocab(field: str, value: str, allowed) -> str:
    if value not in allowed:
        raise UnprocessableError(
            [FieldError(field, "invalid", f"{field} must be one of {sorted(allowed)}")]
        )
    return value


def _enrich(row: LessonRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(LessonRow).where(LessonRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    category: str | None = None,
    signal: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(LessonRow).order_by(LessonRow.identifier)
    if category is not None:
        stmt = stmt.where(LessonRow.category == category)
    if signal is not None:
        stmt = stmt.where(LessonRow.signal == signal)
    if status is not None:
        stmt = stmt.where(LessonRow.status == status)
    if scope is not None:
        stmt = stmt.where(LessonRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(
    identifier, *, category, title, body, signal, status, engagement_id
) -> LessonRow:
    return LessonRow(
        identifier=identifier,
        engagement_id=engagement_id,
        category=category,
        title=title,
        body=body,
        signal=signal,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> LessonRow:
    # REQ-446 / PI-384: serialize per-prefix assignment (PG advisory lock;
    # SQLite no-op) so concurrent writers don't race the read-then-probe loop.
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **fields)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        f"could not assign a unique lesson identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    category: str,
    title: str,
    body: str,
    signal: str = "guidance",
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(title, field="title")
    require_string(body, field="body")
    _require_vocab("category", category, LESSON_CATEGORIES)
    _require_vocab("signal", signal, LESSON_SIGNALS)
    _require_vocab("status", status, LESSON_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "category": category,
        "title": title,
        "body": body,
        "signal": signal,
        "status": status,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(LessonRow, identifier) is not None:
            raise ConflictError(f"lesson {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(LessonRow).where(LessonRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "category" in fields:
        _require_vocab("category", fields["category"], LESSON_CATEGORIES)
    if "signal" in fields:
        _require_vocab("signal", fields["signal"], LESSON_SIGNALS)
    if "status" in fields:
        _require_vocab("status", fields["status"], LESSON_STATUSES)
    before = _enrich(row)
    for k, v in fields.items():
        setattr(row, k, v)
    if scope is not None:
        row.engagement_id = resolve_scope(session, scope)
    session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(select(LessonRow).where(LessonRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
