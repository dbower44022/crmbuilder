"""Topics repository (DEC-007 — free-floating concepts)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import require_string, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.models import Topic

_ENTITY_TYPE = "topic"

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


def create(
    session: Session,
    *,
    identifier: str,
    name: str,
    description: str = "",
    parent_topic: str | None = None,
) -> dict:
    require_string(identifier, field="identifier")
    require_string(name, field="name")
    if session.scalar(select(Topic).where(Topic.identifier == identifier)) is not None:
        raise ConflictError(f"topic {identifier!r} already exists")
    parent_id = _resolve_parent_id(session, parent_topic)
    row = Topic(
        identifier=identifier,
        name=name,
        description=description or "",
        parent_topic_id=parent_id,
    )
    session.add(row)
    session.flush()
    after = _enrich(session, row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
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
