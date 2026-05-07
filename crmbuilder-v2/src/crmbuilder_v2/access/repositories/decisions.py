"""Decisions repository.

Decisions allow updates (notably for status: Active → Superseded). The
``supersedes`` and ``superseded_by`` columns are foreign keys to other
decision rows, addressed by their ``DEC-NNN`` identifier through the
public API.
"""

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
from crmbuilder_v2.access.models import Decision
from crmbuilder_v2.access.vocab import DECISION_STATUSES

_ENTITY_TYPE = "decision"

_UPDATABLE_FIELDS = frozenset(
    {
        "title",
        "decision_date",
        "status",
        "context",
        "decision",
        "rationale",
        "alternatives_considered",
        "consequences",
    }
)


def _resolve_decision_id(session: Session, identifier: str | None) -> int | None:
    if identifier is None:
        return None
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise ValidationError(
            [FieldError("supersedes_or_superseded_by", "not_found", f"decision {identifier!r} does not exist")]
        )
    return row.id


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(session, row)


def list_all(session: Session) -> list[dict]:
    rows = session.scalars(select(Decision).order_by(Decision.identifier)).all()
    return [_enrich(session, r) for r in rows]


def create(
    session: Session,
    *,
    identifier: str,
    title: str,
    decision_date: str,
    status: str,
    context: str = "",
    decision: str = "",
    rationale: str = "",
    alternatives_considered: str = "",
    consequences: str = "",
    supersedes: str | None = None,
    superseded_by: str | None = None,
) -> dict:
    require_string(identifier, field="identifier")
    require_string(title, field="title")
    require_string(decision_date, field="decision_date")
    require_in(status, DECISION_STATUSES, field="status")

    existing = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if existing is not None:
        raise ConflictError(f"decision {identifier!r} already exists")

    supersedes_id = _resolve_decision_id(session, supersedes)
    superseded_by_id = _resolve_decision_id(session, superseded_by)

    row = Decision(
        identifier=identifier,
        title=title,
        decision_date=decision_date,
        status=status,
        context=context or "",
        decision=decision or "",
        rationale=rationale or "",
        alternatives_considered=alternatives_considered or "",
        consequences=consequences or "",
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
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
    session: Session,
    identifier: str,
    *,
    superseded_by: str | None = None,
    supersedes: str | None = None,
    **fields,
) -> dict:
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(session, row)

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
    if "status" in fields:
        require_in(fields["status"], DECISION_STATUSES, field="status")

    for key, value in fields.items():
        setattr(row, key, value if value is not None else "")

    if supersedes is not None:
        row.supersedes_id = _resolve_decision_id(session, supersedes)
    if superseded_by is not None:
        row.superseded_by_id = _resolve_decision_id(session, superseded_by)

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
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
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


def upsert(session: Session, *, identifier: str, **fields) -> dict:
    """Idempotent insert-or-update keyed by identifier (used by bootstrap)."""
    existing = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if existing is None:
        return create(session, identifier=identifier, **fields)
    # Map the create-style 'supersedes' / 'superseded_by' kwargs (identifier
    # strings) over to the update path, leaving everything else as-is.
    supersedes = fields.pop("supersedes", None)
    superseded_by = fields.pop("superseded_by", None)
    return update(
        session,
        identifier,
        supersedes=supersedes,
        superseded_by=superseded_by,
        **fields,
    )


def _enrich(session: Session, row: Decision) -> dict:
    """Add identifier-style references for ``supersedes`` / ``superseded_by``."""
    base = to_dict(row)
    if row.supersedes_id is not None:
        target = session.get(Decision, row.supersedes_id)
        base["supersedes_identifier"] = target.identifier if target else None
    else:
        base["supersedes_identifier"] = None
    if row.superseded_by_id is not None:
        target = session.get(Decision, row.superseded_by_id)
        base["superseded_by_identifier"] = target.identifier if target else None
    else:
        base["superseded_by_identifier"] = None
    return base
