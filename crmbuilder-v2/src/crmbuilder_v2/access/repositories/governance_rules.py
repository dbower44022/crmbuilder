"""Governance-rule repository (PI-122 — Agent Profile Registry, D-δ1).

A ``governance_rule`` (``GVR-NNN``) is a shared, reusable rule with a hybrid
``enforcement`` mode (advisory / enforced / enforced_with_override; PRD §5).
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
from crmbuilder_v2.access.models import GovernanceRuleRow
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import REGISTRY_STATUSES, RULE_ENFORCEMENT_MODES

_ENTITY_TYPE = "governance_rule"
_IDENTIFIER_PREFIX = "GVR"
_IDENTIFIER_RE = re.compile(r"^GVR-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {"rule_type", "enforcement", "severity", "body", "predicate", "version", "status"}
)


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(GovernanceRuleRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^GVR-\d{3}$")]
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


def _enrich(row: GovernanceRuleRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    enforcement: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(GovernanceRuleRow).order_by(GovernanceRuleRow.identifier)
    if enforcement is not None:
        stmt = stmt.where(GovernanceRuleRow.enforcement == enforcement)
    if status is not None:
        stmt = stmt.where(GovernanceRuleRow.status == status)
    if scope is not None:
        stmt = stmt.where(GovernanceRuleRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(identifier, *, rule_type, enforcement, severity, body, predicate,
             version, status, engagement_id) -> GovernanceRuleRow:
    return GovernanceRuleRow(
        identifier=identifier,
        engagement_id=engagement_id,
        rule_type=rule_type,
        enforcement=enforcement,
        severity=severity,
        body=body,
        predicate=predicate,
        version=version,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> GovernanceRuleRow:
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
        f"could not assign a unique governance_rule identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    body: str,
    enforcement: str,
    rule_type: str | None = None,
    severity: str | None = None,
    predicate: dict | None = None,
    version: int = 1,
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(body, field="body")
    _require_vocab("enforcement", enforcement, RULE_ENFORCEMENT_MODES)
    _require_vocab("status", status, REGISTRY_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "rule_type": rule_type,
        "enforcement": enforcement,
        "severity": severity,
        "body": body,
        "predicate": predicate,
        "version": version,
        "status": status,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(GovernanceRuleRow, identifier) is not None:
            raise ConflictError(f"governance_rule {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "enforcement" in fields:
        _require_vocab("enforcement", fields["enforcement"], RULE_ENFORCEMENT_MODES)
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
    row = session.scalar(select(GovernanceRuleRow).where(GovernanceRuleRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
