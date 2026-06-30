"""Topics repository (DEC-007 — free-floating concepts)."""

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
from crmbuilder_v2.access.models import Topic

_ENTITY_TYPE = "topic"
_IDENTIFIER_PREFIX = "TOP"
_IDENTIFIER_RE = re.compile(r"^TOP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``TOP-NNN`` identifier."""
    identifiers = session.scalars(select(Topic.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "identifier",
                    "invalid_format",
                    r"must match ^TOP-\d{3}$ (e.g. TOP-001)",
                )
            ]
        )
    return identifier


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"

# Direct column updates; ``parent_topic`` is handled separately via its own kwarg.
_UPDATABLE_FIELDS = frozenset({"name", "description"})


def _resolve_parent_id(session: Session, parent_identifier: str | None) -> int | None:
    """Resolve an identifier to an integer FK.

    None and empty string both return None. Callers in update() use None to
    mean "don't touch" (the if-not-None guard prevents the assignment) and
    empty string to mean "clear the FK" (the guard fires; this helper
    returns None; the caller assigns None to the foreign-key column).
    """
    if parent_identifier is None or parent_identifier == "":
        return None
    row = session.scalar(select(Topic).where(Topic.identifier == parent_identifier))
    if row is None:
        raise ValidationError(
            [FieldError("parent_topic", "not_found", f"topic {parent_identifier!r} does not exist")]
        )
    return row.id


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(Topic).where(Topic.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(session, row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(select(Topic).order_by(Topic.identifier)).all()
    return [_enrich(session, r) for r in rows]


def _new_topic_row(
    identifier: str, name: str, description: str, parent_id: int | None
) -> Topic:
    return Topic(
        identifier=identifier,
        name=name,
        description=description,
        parent_topic_id=parent_id,
    )


def _insert_with_autoassign(
    session: Session, name: str, description: str, parent_id: int | None
) -> Topic:
    """Insert a topic with a server-assigned identifier (PI-002)."""
    # REQ-446 / PI-384: serialize per-prefix assignment (PG advisory lock;
    # SQLite no-op) so concurrent writers don't race the read-then-probe loop.
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_topic_row(candidate, name, description, parent_id)
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
        "could not assign a unique topic identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    name: str,
    description: str = "",
    parent_topic: str | None = None,
) -> dict:
    """Create a topic.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^TOP-\\d{3}$`` and not already exist.
    """
    require_string(name, field="name")
    parent_id = _resolve_parent_id(session, parent_topic)

    if identifier is None:
        row = _insert_with_autoassign(session, name, description or "", parent_id)
    else:
        _require_identifier_format(identifier)
        if (
            session.scalar(select(Topic).where(Topic.identifier == identifier))
            is not None
        ):
            raise ConflictError(f"topic {identifier!r} already exists")
        row = _new_topic_row(identifier, name, description or "", parent_id)
        session.add(row)
        session.flush()

    after = _enrich(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update(
    session: Session, identifier: str, *, parent_topic: str | None = None, **fields
) -> dict:
    row = session.scalar(select(Topic).where(Topic.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown updatable fields: {sorted(unknown)}",
                )
            ]
        )
    before = _enrich(session, row)
    for k, v in fields.items():
        setattr(row, k, v)
    if parent_topic is not None:
        row.parent_topic_id = _resolve_parent_id(session, parent_topic)
    session.flush()
    after = _enrich(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(select(Topic).where(Topic.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(session, row)
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


def _enrich(session: Session, row: Topic) -> dict:
    base = to_dict(row)
    if row.parent_topic_id is not None:
        parent = session.get(Topic, row.parent_topic_id)
        base["parent_topic_identifier"] = parent.identifier if parent else None
    else:
        base["parent_topic_identifier"] = None
    return base
