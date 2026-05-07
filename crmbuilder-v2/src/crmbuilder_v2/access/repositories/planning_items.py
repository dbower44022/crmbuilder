"""Planning items repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import require_in, require_string, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.models import PlanningItem
from crmbuilder_v2.access.vocab import PLANNING_ITEM_STATUSES, PLANNING_ITEM_TYPES

_ENTITY_TYPE = "planning_item"

_UPDATABLE_FIELDS = frozenset(
    {"title", "item_type", "description", "status", "resolution_reference"}
)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return to_dict(row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(select(PlanningItem).order_by(PlanningItem.identifier)).all()
    return [to_dict(r) for r in rows]


def create(
    session: Session,
    *,
    identifier: str,
    title: str,
    item_type: str,
    description: str = "",
    status: str,
    resolution_reference: str | None = None,
) -> dict:
    require_string(identifier, field="identifier")
    require_string(title, field="title")
    require_in(item_type, PLANNING_ITEM_TYPES, field="item_type")
    require_in(status, PLANNING_ITEM_STATUSES, field="status")

    if (
        session.scalar(select(PlanningItem).where(PlanningItem.identifier == identifier))
        is not None
    ):
        raise ConflictError(f"planning_item {identifier!r} already exists")

    row = PlanningItem(
        identifier=identifier,
        title=title,
        item_type=item_type,
        description=description or "",
        status=status,
        resolution_reference=resolution_reference,
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


def update(session: Session, identifier: str, **fields) -> dict:
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
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
    if "item_type" in fields:
        require_in(fields["item_type"], PLANNING_ITEM_TYPES, field="item_type")
    if "status" in fields:
        require_in(fields["status"], PLANNING_ITEM_STATUSES, field="status")
    before = to_dict(row)
    for k, v in fields.items():
        setattr(row, k, v)
    session.flush()
    after = to_dict(row)
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
    row = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
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
    existing = session.scalar(
        select(PlanningItem).where(PlanningItem.identifier == identifier)
    )
    if existing is None:
        return create(session, identifier=identifier, **fields)
    return update(session, identifier, **fields)
