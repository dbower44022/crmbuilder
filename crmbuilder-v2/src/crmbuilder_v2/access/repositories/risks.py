"""Risks repository."""

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
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
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
_IDENTIFIER_RE = re.compile(r"^RSK-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``RSK-NNN`` identifier."""
    identifiers = session.scalars(select(Risk.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "identifier",
                    "invalid_format",
                    r"must match ^RSK-\d{3}$ (e.g. RSK-001)",
                )
            ]
        )
    return identifier


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"

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


def _new_risk_row(
    identifier: str,
    title: str,
    description: str,
    probability: str,
    impact: str,
    response_plan: str,
    status: str,
) -> Risk:
    return Risk(
        identifier=identifier,
        title=title,
        description=description,
        probability=probability,
        impact=impact,
        response_plan=response_plan,
        status=status,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    description: str,
    probability: str,
    impact: str,
    response_plan: str,
    status: str,
) -> Risk:
    """Insert a risk with a server-assigned identifier, collision-safe (PI-002)."""
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_risk_row(
            candidate, title, description, probability, impact, response_plan, status
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
        "could not assign a unique risk identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    title: str,
    description: str = "",
    probability: str,
    impact: str,
    response_plan: str = "",
    status: str,
) -> dict:
    """Create a risk.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^RSK-\\d{3}$`` and not already exist.
    """
    require_string(title, field="title")
    require_in(probability, RISK_PROBABILITIES, field="probability")
    require_in(impact, RISK_IMPACTS, field="impact")
    require_in(status, RISK_STATUSES, field="status")

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            title,
            description or "",
            probability,
            impact,
            response_plan or "",
            status,
        )
    else:
        _require_identifier_format(identifier)
        if session.scalar(select(Risk).where(Risk.identifier == identifier)) is not None:
            raise ConflictError(f"risk {identifier!r} already exists")
        row = _new_risk_row(
            identifier,
            title,
            description or "",
            probability,
            impact,
            response_plan or "",
            status,
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
