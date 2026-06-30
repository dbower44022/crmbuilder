"""Skill repository (PI-122 — Agent Profile Registry, D-δ1).

A ``skill`` (``SKL-NNN``) is a shared, reusable capability: ``instruction`` text
or a ``tool`` with an I/O contract + optional backing callable (PRD §4/§7.2).
System/shared row with a nullable ``engagement_id`` scope.
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
from crmbuilder_v2.access.models import SkillRow
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import REGISTRY_STATUSES, SKILL_KINDS

_ENTITY_TYPE = "skill"
_IDENTIFIER_PREFIX = "SKL"
_IDENTIFIER_RE = re.compile(r"^SKL-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {"name", "kind", "description", "io_contract", "backing_callable", "version", "status"}
)


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(SkillRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^SKL-\d{3}$")]
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


def _enrich(row: SkillRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(SkillRow).where(SkillRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    kind: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(SkillRow).order_by(SkillRow.identifier)
    if kind is not None:
        stmt = stmt.where(SkillRow.kind == kind)
    if status is not None:
        stmt = stmt.where(SkillRow.status == status)
    if scope is not None:
        stmt = stmt.where(SkillRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(identifier, *, name, kind, description, io_contract, backing_callable,
             version, status, engagement_id) -> SkillRow:
    return SkillRow(
        identifier=identifier,
        engagement_id=engagement_id,
        name=name,
        kind=kind,
        description=description,
        io_contract=io_contract,
        backing_callable=backing_callable,
        version=version,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> SkillRow:
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
        f"could not assign a unique skill identifier after {_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    name: str,
    kind: str,
    description: str,
    io_contract: dict | None = None,
    backing_callable: str | None = None,
    version: int = 1,
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(name, field="name")
    require_string(description, field="description")
    _require_vocab("kind", kind, SKILL_KINDS)
    _require_vocab("status", status, REGISTRY_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "name": name,
        "kind": kind,
        "description": description,
        "io_contract": io_contract,
        "backing_callable": backing_callable,
        "version": version,
        "status": status,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(SkillRow, identifier) is not None:
            raise ConflictError(f"skill {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(SkillRow).where(SkillRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "kind" in fields:
        _require_vocab("kind", fields["kind"], SKILL_KINDS)
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
    row = session.scalar(select(SkillRow).where(SkillRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
