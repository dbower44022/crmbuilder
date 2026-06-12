"""Domain repository — the first methodology entity type (UI v0.4 slice B).

Per ``methodology-schema-specs/domain.md``. The eight module-level
functions back the ``/domains`` REST endpoints and the desktop panel:

* :func:`list_domains` / :func:`get_domain` — reads.
* :func:`create_domain` — insert with server-side identifier
  auto-assignment (collision-safe retry, per acceptance criterion 7).
* :func:`update_domain` — full replace (PUT).
* :func:`patch_domain` — partial update (PATCH).
* :func:`delete_domain` / :func:`restore_domain` — soft-delete round-trip.
* :func:`next_domain_identifier` — the ``DOM-NNN`` allocator helper.

Validation posture (``domain.md`` section 3.5): identifier-format,
case-insensitive name-uniqueness, status-enum, and PUT identifier/path
mismatches raise :class:`UnprocessableError` (HTTP 422); disallowed
status transitions raise :class:`StatusTransitionError` (HTTP 422 with
the dedicated body shape). Missing entities raise
:class:`NotFoundError` (404); an explicit-identifier collision on
create raises :class:`ConflictError` (409).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Domain
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    DOMAIN_STATUS_TRANSITIONS,
    DOMAIN_STATUSES,
)

_ENTITY_TYPE = "domain"
_IDENTIFIER_PREFIX = "DOM"
_IDENTIFIER_RE = re.compile(r"^DOM-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_domain`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {"name", "purpose", "description", "notes", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "domain_identifier",
                    "invalid_format",
                    r"must match ^DOM-\d{3}$ (e.g. DOM-001)",
                )
            ]
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def _require_status(status: object) -> str:
    if status not in DOMAIN_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "domain_status",
                    "invalid_value",
                    f"must be one of {sorted(DOMAIN_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`DOMAIN_STATUS_TRANSITIONS`.
    """
    if requested == current:
        return
    if requested not in DOMAIN_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``domain_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``domain.md`` section 3.2.1. ``exclude_identifier`` lets the update
    paths ignore the row being modified.
    """
    stmt = select(Domain).where(
        func.lower(Domain.domain_name) == name.lower(),
        Domain.domain_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Domain.domain_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "domain_name",
                    "duplicate",
                    f"a domain named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Domain:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, Domain, Domain.domain_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``DOM-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_domains(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all domains ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Domain).order_by(Domain.domain_identifier)
    if not include_deleted:
        stmt = stmt.where(Domain.domain_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_domain(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single domain by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, Domain, Domain.domain_identifier, identifier)
    if row is None:
        return None
    if row.domain_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_domain_identifier(session: Session) -> str:
    """Return the next available ``DOM-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(select(Domain.domain_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_domain_row(
    identifier: str,
    name: str,
    purpose: str,
    description: str,
    notes: str | None,
    status: str,
) -> Domain:
    return Domain(
        domain_identifier=identifier,
        domain_name=name,
        domain_purpose=purpose,
        domain_description=description,
        domain_notes=notes,
        domain_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    purpose: str,
    description: str,
    notes: str | None,
    status: str,
) -> Domain:
    """Insert a domain with a server-assigned identifier, collision-safe.

    Computes the next ``DOM-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies acceptance criterion 7 — two concurrent
    POSTs never share an identifier.
    """
    candidate = next_domain_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_domain_row(
            candidate, name, purpose, description, notes, status
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            # Another transaction committed this identifier first. Roll
            # the SAVEPOINT back (the outer transaction stays intact),
            # bump the candidate, and retry.
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique domain identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_domain(
    session: Session,
    *,
    name: str,
    purpose: str,
    description: str,
    notes: str | None = None,
    status: str = "candidate",
    identifier: str | None = None,
) -> dict:
    """Create a domain.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^DOM-\\d{3}$`` and not already exist.
    ``status`` defaults to ``candidate`` but may be set to any valid
    enum value on create (e.g. importing already-confirmed domains).
    """
    name = _require_nonempty(name, field="domain_name")
    purpose = _require_nonempty(purpose, field="domain_purpose")
    description = _require_nonempty(description, field="domain_description")
    if status is None:
        status = "candidate"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, purpose, description, notes, status
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, Domain, Domain.domain_identifier, identifier) is not None:
            raise ConflictError(f"domain {identifier!r} already exists")
        row = _new_domain_row(
            identifier, name, purpose, description, notes, status
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.domain_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_domain(
    session: Session,
    identifier: str,
    *,
    domain_identifier: str | None = None,
    name: str | None = None,
    purpose: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    rejected_by_decision: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``domain_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``purpose`` / ``description``
    are required (a full replace cannot blank them); ``notes`` is
    replaced wholesale (``None`` clears it). A ``status`` change is
    transition-validated. A move to ``rejected`` requires either the
    ``rejected_by_decision`` key (atomic edge + flip, PI-153 §3.4) or a
    pre-existing ``rejected_by_decision`` edge.
    """
    row = _get_row(session, identifier)
    if domain_identifier is not None and domain_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "domain_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="domain_name")
    purpose = _require_nonempty(purpose, field="domain_purpose")
    description = _require_nonempty(description, field="domain_description")
    if name.lower() != row.domain_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.domain_status:
        _require_status(status)
        _check_transition(row.domain_status, status)
        if status == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.domain_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.domain_status,
        )

    row.domain_name = name
    row.domain_purpose = purpose
    row.domain_description = description
    row.domain_notes = notes
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


def patch_domain(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``purpose``, ``description``, ``notes``,
    ``status``, ``rejected_by_decision``. A ``status`` change is
    transition-validated; a move to ``rejected`` requires either the
    ``rejected_by_decision`` key (atomic edge + flip, PI-153 §3.4) or a
    pre-existing ``rejected_by_decision`` edge.
    """
    rejected_by_decision = fields.pop("rejected_by_decision", None)
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)}",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "name" in fields:
        name = _require_nonempty(fields["name"], field="domain_name")
        if name.lower() != row.domain_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.domain_name = name
    if "purpose" in fields:
        row.domain_purpose = _require_nonempty(
            fields["purpose"], field="domain_purpose"
        )
    if "description" in fields:
        row.domain_description = _require_nonempty(
            fields["description"], field="domain_description"
        )
    if "notes" in fields:
        row.domain_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.domain_status:
            _check_transition(row.domain_status, status)
            if status == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
            row.domain_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.domain_status,
        )

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


def delete_domain(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``domain_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged.
    """
    row = _get_row(session, identifier)
    if row.domain_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.domain_deleted_at = datetime.now(UTC)
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


def restore_domain(session: Session, identifier: str) -> dict:
    """Clear ``domain_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.domain_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "domain_deleted_at",
                    "not_deleted",
                    "domain is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.domain_deleted_at = None
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
