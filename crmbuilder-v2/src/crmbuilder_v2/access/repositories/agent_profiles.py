"""Agent profile repository (PI-122 — Agent Profile Registry, D-δ1).

An ``agent_profile`` (``AGP-NNN``) is the skill-and-rule definition for one
ADO (area × tier) cell. System/shared row with a nullable ``engagement_id``
scope (see :mod:`._registry`).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
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
from crmbuilder_v2.access.models import AgentProfileRow
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import AGENT_PROFILE_TIERS, REGISTRY_STATUSES

_ENTITY_TYPE = "agent_profile"
_IDENTIFIER_PREFIX = "AGP"
_IDENTIFIER_RE = re.compile(r"^AGP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset({"area", "tier", "description", "status"})


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(AgentProfileRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^AGP-\d{3}$")]
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


def _enrich(row: AgentProfileRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(AgentProfileRow).where(AgentProfileRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    area: str | None = None,
    tier: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(AgentProfileRow).order_by(AgentProfileRow.identifier)
    if area is not None:
        stmt = stmt.where(AgentProfileRow.area == area)
    if tier is not None:
        stmt = stmt.where(AgentProfileRow.tier == tier)
    if status is not None:
        stmt = stmt.where(AgentProfileRow.status == status)
    if scope is not None:
        stmt = stmt.where(AgentProfileRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(identifier, *, area, tier, description, status, engagement_id) -> AgentProfileRow:
    return AgentProfileRow(
        identifier=identifier,
        engagement_id=engagement_id,
        area=area,
        tier=tier,
        description=description,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> AgentProfileRow:
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
        f"could not assign a unique agent_profile identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    area: str,
    tier: str,
    description: str,
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(area, field="area")
    require_string(description, field="description")
    _require_vocab("tier", tier, AGENT_PROFILE_TIERS)
    _require_vocab("status", status, REGISTRY_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "area": area,
        "tier": tier,
        "description": description,
        "status": status,
        "engagement_id": engagement_id,
    }

    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(AgentProfileRow, identifier) is not None:
            raise ConflictError(f"agent_profile {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()

    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(AgentProfileRow).where(AgentProfileRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "tier" in fields:
        _require_vocab("tier", fields["tier"], AGENT_PROFILE_TIERS)
    if "status" in fields:
        _require_vocab("status", fields["status"], REGISTRY_STATUSES)
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
    row = session.scalar(select(AgentProfileRow).where(AgentProfileRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
