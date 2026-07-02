"""Reference-pointer repository (REL-039 / PI-357 — REQ-416, DEC-891).

A ``reference_pointer`` (``RFP-NNN``) is one external addressable target (server,
dashboard, doc, ticket, repo, credential location, service) with connection
metadata and no version history. System/shared row with a nullable
``engagement_id`` scope (NULL = a system default, set = an engagement overlay —
CBM pointers live at ``ENG-002``).

Secret-safety invariant (binding): ``access_note`` records *where* a credential
lives (keyring entry, env var name, ``~/.ssh`` key path) and the auth scheme —
NEVER the secret value itself. Enforcement is by discipline at the write site
(the ingest); this repository does not persist secrets by policy.
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
from crmbuilder_v2.access.models import ReferencePointerRow
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import (
    REFERENCE_POINTER_KINDS,
    REFERENCE_POINTER_STATUSES,
)

_ENTITY_TYPE = "reference_pointer"
_IDENTIFIER_PREFIX = "RFP"
_IDENTIFIER_RE = re.compile(r"^RFP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {"kind", "title", "target", "access_note", "body", "status"}
)


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(ReferencePointerRow.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^RFP-\d{3}$")]
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


def _enrich(row: ReferencePointerRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(ReferencePointerRow).where(ReferencePointerRow.identifier == identifier)
    )
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
    stmt = select(ReferencePointerRow).order_by(ReferencePointerRow.identifier)
    if kind is not None:
        stmt = stmt.where(ReferencePointerRow.kind == kind)
    if status is not None:
        stmt = stmt.where(ReferencePointerRow.status == status)
    if scope is not None:
        stmt = stmt.where(
            ReferencePointerRow.engagement_id == resolve_scope(session, scope)
        )
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(
    identifier, *, kind, title, target, access_note, body, status, engagement_id
) -> ReferencePointerRow:
    return ReferencePointerRow(
        identifier=identifier,
        engagement_id=engagement_id,
        kind=kind,
        title=title,
        target=target,
        access_note=access_note,
        body=body,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> ReferencePointerRow:
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
        f"could not assign a unique reference_pointer identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    kind: str,
    title: str,
    target: str,
    access_note: str | None = None,
    body: str | None = None,
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(title, field="title")
    require_string(target, field="target")
    _require_vocab("kind", kind, REFERENCE_POINTER_KINDS)
    _require_vocab("status", status, REFERENCE_POINTER_STATUSES)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "kind": kind,
        "title": title,
        "target": target,
        "access_note": access_note,
        "body": body,
        "status": status,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(ReferencePointerRow, identifier) is not None:
            raise ConflictError(f"reference_pointer {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=row.identifier,
         operation="insert", before=None, after=after)
    return after


def update(session: Session, identifier: str, *, scope: str | None = None, **fields) -> dict:
    row = session.scalar(
        select(ReferencePointerRow).where(ReferencePointerRow.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [FieldError("fields", "unknown_field", f"unknown updatable fields: {sorted(unknown)}")]
        )
    if "kind" in fields:
        _require_vocab("kind", fields["kind"], REFERENCE_POINTER_KINDS)
    if "status" in fields:
        _require_vocab("status", fields["status"], REFERENCE_POINTER_STATUSES)
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
    row = session.scalar(
        select(ReferencePointerRow).where(ReferencePointerRow.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="delete", before=before, after=None)
    return before
