"""Decisions repository.

Decisions allow updates (notably for status: Active → Superseded). The
``supersedes`` and ``superseded_by`` columns are foreign keys to other
decision rows, addressed by their ``DEC-NNN`` identifier through the
public API.
"""

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
    validate_optional_length,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import Decision
from crmbuilder_v2.access.vocab import DECISION_STATUSES

_ENTITY_TYPE = "decision"
_IDENTIFIER_PREFIX = "DEC"
_IDENTIFIER_RE = re.compile(r"^DEC-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50


def compute_next_identifier(session: Session) -> str:
    """Return the next available ``DEC-NNN`` identifier.

    Scans every decision row including soft-deleted ones (status
    ``Deleted``) so a retired identifier is never reused.
    """
    identifiers = session.scalars(select(Decision.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "identifier",
                    "invalid_format",
                    r"must match ^DEC-\d{3}$ (e.g. DEC-001)",
                )
            ]
        )
    return identifier


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"

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
        "executive_summary",
    }
)

_EXECUTIVE_SUMMARY_MIN = 200
_EXECUTIVE_SUMMARY_MAX = 800


def _resolve_decision_id(session: Session, identifier: str | None) -> int | None:
    """Resolve an identifier to an integer FK.

    None and empty string both return None. Callers in update() use None to
    mean "don't touch" (the if-not-None guard prevents the assignment) and
    empty string to mean "clear the FK" (the guard fires; this helper
    returns None; the caller assigns None to the foreign-key column).
    """
    if identifier is None or identifier == "":
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


def list_all(session: Session, *, include_deleted: bool = False) -> list[dict]:
    stmt = select(Decision).order_by(Decision.identifier)
    if not include_deleted:
        stmt = stmt.where(Decision.status != "Deleted")
    rows = session.scalars(stmt).all()
    return [_enrich(session, r) for r in rows]


def _new_decision_row(
    identifier: str,
    title: str,
    decision_date: str,
    status: str,
    context: str,
    decision: str,
    rationale: str,
    alternatives_considered: str,
    consequences: str,
    supersedes_id: int | None,
    superseded_by_id: int | None,
    executive_summary: str | None,
) -> Decision:
    return Decision(
        identifier=identifier,
        title=title,
        decision_date=decision_date,
        status=status,
        context=context,
        decision=decision,
        rationale=rationale,
        alternatives_considered=alternatives_considered,
        consequences=consequences,
        supersedes_id=supersedes_id,
        superseded_by_id=superseded_by_id,
        executive_summary=executive_summary,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    decision_date: str,
    status: str,
    context: str,
    decision: str,
    rationale: str,
    alternatives_considered: str,
    consequences: str,
    supersedes_id: int | None,
    superseded_by_id: int | None,
    executive_summary: str | None,
) -> Decision:
    """Insert a decision with a server-assigned identifier, collision-safe.

    Mirrors the ``domain`` repository's SAVEPOINT-retry pattern (PI-002):
    a concurrent transaction that committed the same identifier first
    raises ``IntegrityError`` on flush; the savepoint rolls that INSERT
    back, the candidate is incremented, and the attempt repeats.
    """
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_decision_row(
            candidate,
            title,
            decision_date,
            status,
            context,
            decision,
            rationale,
            alternatives_considered,
            consequences,
            supersedes_id,
            superseded_by_id,
            executive_summary,
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
        "could not assign a unique decision identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
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
    executive_summary: str | None = None,
) -> dict:
    """Create a decision.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^DEC-\\d{3}$`` and not already exist.

    ``executive_summary`` (PI-074) is optional in v0.8; when supplied it
    must be a 200-800 character audience-facing summary. PI-075 will
    backfill and tighten the column to NOT NULL.
    """
    require_string(title, field="title")
    require_string(decision_date, field="decision_date")
    require_in(status, DECISION_STATUSES, field="status")
    executive_summary = validate_optional_length(
        executive_summary,
        field="executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )

    supersedes_id = _resolve_decision_id(session, supersedes)
    superseded_by_id = _resolve_decision_id(session, superseded_by)

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            title,
            decision_date,
            status,
            context or "",
            decision or "",
            rationale or "",
            alternatives_considered or "",
            consequences or "",
            supersedes_id,
            superseded_by_id,
            executive_summary,
        )
    else:
        _require_identifier_format(identifier)
        existing = session.scalar(
            select(Decision).where(Decision.identifier == identifier)
        )
        if existing is not None:
            raise ConflictError(f"decision {identifier!r} already exists")
        row = _new_decision_row(
            identifier,
            title,
            decision_date,
            status,
            context or "",
            decision or "",
            rationale or "",
            alternatives_considered or "",
            consequences or "",
            supersedes_id,
            superseded_by_id,
            executive_summary,
        )
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
    if "executive_summary" in fields:
        fields["executive_summary"] = validate_optional_length(
            fields["executive_summary"],
            field="executive_summary",
            min_len=_EXECUTIVE_SUMMARY_MIN,
            max_len=_EXECUTIVE_SUMMARY_MAX,
        )

    for key, value in fields.items():
        if key == "executive_summary":
            # Nullable column — preserve explicit None instead of coercing to "".
            setattr(row, key, value)
        else:
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
    """Soft-delete: set status to 'Deleted', leave the row in place.

    Referential integrity is preserved by construction — references pointing
    at this decision continue to resolve via get(). The row is filtered out
    of list_all() by default, so the UI sees the row disappear from the
    decisions list, matching the pre-soft-delete user experience.
    """
    row = session.scalar(select(Decision).where(Decision.identifier == identifier))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    if row.status == "Deleted":
        return _enrich(session, row)
    before = _enrich(session, row)
    row.status = "Deleted"
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
