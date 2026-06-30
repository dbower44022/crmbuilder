"""Learning repository (PI-122 slice 3 — the registry's living memory, PRD §13.2).

A ``learning`` (``LRN-NNN``) is an append-mostly, evidence-tagged observation
written by the area experts. Evidence is the promotion currency: seen once = a
hunch (confidence 1); confirmed across many Work Tasks = institutional knowledge
(confidence rises); contradicted = confidence falls. System/shared row with a
nullable ``engagement_id`` scope.

Slice 3 ships capture + evidence accumulation + CRUD. The propose/promote
workflow and the per-release curate task are slice 4; cross-engagement promotion
is slice 5.
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
from crmbuilder_v2.access.models import LearningRow
from crmbuilder_v2.access.repositories import references
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import (
    LEARNING_CATEGORIES,
    LEARNING_STATUSES,
    LEARNING_TIERS,
)

_ENTITY_TYPE = "learning"
_IDENTIFIER_PREFIX = "LRN"
_IDENTIFIER_RE = re.compile(r"^LRN-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {"area", "tier", "category", "content", "status", "confidence"}
)
_DERIVED_FROM = "learning_derived_from"
_CONTRADICTED_BY = "learning_contradicted_by"
# Evidence target types currently admitted by _kinds_for_pair (D-δ6: finding
# is added when that entity lands).
_DERIVED_TARGETS = {"work_task", "decision", "test_spec"}


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(LearningRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^LRN-\d{3}$")]
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


def _enrich(row: LearningRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(LearningRow).where(LearningRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    area: str | None = None,
    tier: str | None = None,
    category: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(LearningRow).order_by(LearningRow.identifier)
    if area is not None:
        stmt = stmt.where(LearningRow.area == area)
    if tier is not None:
        stmt = stmt.where(LearningRow.tier == tier)
    if category is not None:
        stmt = stmt.where(LearningRow.category == category)
    if status is not None:
        stmt = stmt.where(LearningRow.status == status)
    if scope is not None:
        stmt = stmt.where(LearningRow.engagement_id == resolve_scope(session, scope))
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(identifier, *, area, tier, category, content, status, confidence, engagement_id) -> LearningRow:
    return LearningRow(
        identifier=identifier,
        engagement_id=engagement_id,
        area=area,
        tier=tier,
        category=category,
        content=content,
        status=status,
        confidence=confidence,
    )


def _insert_with_autoassign(session: Session, **fields) -> LearningRow:
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
        f"could not assign a unique learning identifier after {_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    area: str,
    tier: str,
    category: str,
    content: str,
    status: str = "active",
    confidence: int = 0,
    scope: str | None = None,
) -> dict:
    require_string(area, field="area")
    require_string(content, field="content")
    _require_vocab("tier", tier, LEARNING_TIERS)
    _require_vocab("category", category, LEARNING_CATEGORIES)
    _require_vocab("status", status, LEARNING_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "area": area,
        "tier": tier,
        "category": category,
        "content": content,
        "status": status,
        "confidence": confidence,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(LearningRow, identifier) is not None:
            raise ConflictError(f"learning {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def capture(
    session: Session,
    *,
    area: str,
    tier: str,
    category: str,
    content: str,
    evidence_type: str | None = None,
    evidence_id: str | None = None,
    scope: str | None = None,
) -> dict:
    """Capture a learning at Work-Task close, optionally linking one evidence row.

    With evidence, the learning starts at confidence 1 and gets a
    ``learning_derived_from`` edge; without, confidence 0 (a bare hunch).
    """
    confidence = 1 if (evidence_type and evidence_id) else 0
    record = create(
        session, area=area, tier=tier, category=category, content=content,
        confidence=confidence, scope=scope,
    )
    if evidence_type and evidence_id:
        _require_vocab("evidence_type", evidence_type, _DERIVED_TARGETS)
        references.create(
            session,
            source_type=_ENTITY_TYPE,
            source_id=record["identifier"],
            target_type=evidence_type,
            target_id=evidence_id,
            relationship=_DERIVED_FROM,
        )
    return get(session, record["identifier"])


def add_evidence(
    session: Session,
    identifier: str,
    *,
    target_type: str,
    target_id: str,
    contradicts: bool = False,
) -> dict:
    """Link new evidence to an existing learning, adjusting confidence (PRD §13.2).

    Supporting evidence raises confidence (institutional knowledge accrues);
    contradicting evidence lowers it and is the curation trigger.
    """
    row = session.scalar(select(LearningRow).where(LearningRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if not contradicts:
        _require_vocab("target_type", target_type, _DERIVED_TARGETS)
    elif target_type != "work_task":
        raise UnprocessableError(
            [FieldError("target_type", "invalid", "contradicting evidence must be a work_task")]
        )
    before = _enrich(row)
    references.create(
        session,
        source_type=_ENTITY_TYPE,
        source_id=identifier,
        target_type=target_type,
        target_id=target_id,
        relationship=_CONTRADICTED_BY if contradicts else _DERIVED_FROM,
    )
    row.confidence = max(0, row.confidence + (-1 if contradicts else 1))
    session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(select(LearningRow).where(LearningRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "tier" in fields:
        _require_vocab("tier", fields["tier"], LEARNING_TIERS)
    if "category" in fields:
        _require_vocab("category", fields["category"], LEARNING_CATEGORIES)
    if "status" in fields:
        _require_vocab("status", fields["status"], LEARNING_STATUSES)
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
    row = session.scalar(select(LearningRow).where(LearningRow.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
