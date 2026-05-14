"""Risks repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_in,
    require_string,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.models import Risk
from crmbuilder_v2.access.vocab import (
    RISK_IMPACTS,
    RISK_PROBABILITIES,
    RISK_STATUSES,
)

_ENTITY_TYPE = "risk"
_IDENTIFIER_PREFIX = "RSK"


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``RSK-NNN`` identifier."""
    identifiers = session.scalars(select(Risk.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)

_UPDATABLE_FIELDS = frozenset(
    {"title", "description", "probability", "impact", "response_plan", "status"}
)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(Risk).where(Risk.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return to_dict(row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(select(Risk).order_by(Risk.identifier)).all()
    return [to_dict(r) for r in rows]


def create(
    session: Session,
    *,
    identifier: str,
    title: str,
    description: str = "",
    probability: str,
    impact: str,
    response_plan: str = "",
    status: str,
) -> dict:
    require_string(identifier, field="identifier")
    require_string(title, field="title")
    require_in(probability, RISK_PROBABILITIES, field="probability")
    require_in(impact, RISK_IMPACTS, field="impact")
    require_in(status, RISK_STATUSES, field="status")

    if session.scalar(select(Risk).where(Risk.identifier == identifier)) is not None:
        raise ConflictError(f"risk {identifier!r} already exists")

    row = Risk(
        identifier=identifier,
        title=title,
        description=description or "",
        probability=probability,
        impact=impact,
        response_plan=response_plan or "",
        status=status,
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
    row = session.scalar(select(Risk).where(Risk.identifier == identifier))
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
    if "probability" in fields:
        require_in(fields["probability"], RISK_PROBABILITIES, field="probability")
    if "impact" in fields:
        require_in(fields["impact"], RISK_IMPACTS, field="impact")
    if "status" in fields:
        require_in(fields["status"], RISK_STATUSES, field="status")
    before = to_dict(row)
    for k, v in fields.items():
        setattr(row, k, v if v is not None else "")
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
    row = session.scalar(select(Risk).where(Risk.identifier == identifier))
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
