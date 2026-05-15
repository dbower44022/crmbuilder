"""CRM Candidate repository — the fourth methodology entity type (UI v0.4 slice E).

Per ``methodology-schema-specs/crm_candidate.md``. The eight module-level
functions back the ``/crm_candidates`` REST endpoints and the desktop
panel:

* :func:`list_crm_candidates` / :func:`get_crm_candidate` — reads.
* :func:`create_crm_candidate` — insert with server-side identifier
  auto-assignment (collision-safe retry, per acceptance criterion 7).
* :func:`update_crm_candidate` — full replace (PUT).
* :func:`patch_crm_candidate` — partial update (PATCH).
* :func:`delete_crm_candidate` / :func:`restore_crm_candidate` —
  soft-delete round-trip.
* :func:`next_crm_candidate_identifier` — the ``CRM-NNN`` allocator
  helper.

Validation posture (``crm_candidate.md`` sections 3.5.3, 3.5.4):
identifier-format, case-insensitive name-uniqueness, status-enum, and
PUT identifier/path mismatches raise :class:`UnprocessableError`
(HTTP 422); disallowed status transitions raise
:class:`StatusTransitionError` (HTTP 422 with the dedicated body
shape); singleton-``selected`` violations raise
:class:`SelectedCandidateConflictError` (HTTP 422 with the dedicated
``selected_candidate_already_exists`` body). Missing entities raise
:class:`NotFoundError` (404); an explicit-identifier collision on
create raises :class:`ConflictError` (409).

Singleton-``selected`` is enforced on three write paths per spec
3.5.4: create, update (PUT/PATCH transitioning into ``selected``),
and restore (of a soft-deleted record whose status is ``selected``).
Soft-deleted records are excluded from the singleton count, so a
soft-deleted mistakenly-``selected`` record frees the slot for a
different record.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import next_prefixed_identifier, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    SelectedCandidateConflictError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import CrmCandidate
from crmbuilder_v2.access.vocab import (
    CRM_CANDIDATE_STATUS_TRANSITIONS,
    CRM_CANDIDATE_STATUSES,
)

_ENTITY_TYPE = "crm_candidate"
_IDENTIFIER_PREFIX = "CRM"
_IDENTIFIER_RE = re.compile(r"^CRM-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_crm_candidate`. The identifier and
# the timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {"name", "fit_reason", "notes", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "crm_candidate_identifier",
                    "invalid_format",
                    r"must match ^CRM-\d{3}$ (e.g. CRM-001)",
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
    if status not in CRM_CANDIDATE_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "crm_candidate_status",
                    "invalid_value",
                    f"must be one of {sorted(CRM_CANDIDATE_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`CRM_CANDIDATE_STATUS_TRANSITIONS`. The three terminal
    states (``selected``, ``declined``, ``removed``) have empty
    successor sets, so any non-no-op transition from them raises.
    """
    if requested == current:
        return
    if requested not in CRM_CANDIDATE_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``crm_candidate_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``crm_candidate.md`` section 3.2.1. ``exclude_identifier`` lets the
    update paths ignore the row being modified.
    """
    stmt = select(CrmCandidate).where(
        func.lower(CrmCandidate.crm_candidate_name) == name.lower(),
        CrmCandidate.crm_candidate_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            CrmCandidate.crm_candidate_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "crm_candidate_name",
                    "duplicate",
                    f"a crm_candidate named {name!r} already exists",
                )
            ]
        )


def _reject_second_selected(
    session: Session, *, exclude_identifier: str | None = None
) -> None:
    """Raise if another live record already holds ``status='selected'``.

    Per spec section 3.4.3: at most one non-soft-deleted record may
    hold ``crm_candidate_status = 'selected'``. ``exclude_identifier``
    excludes the row being created/updated/restored so a no-op edit on
    an already-selected record does not trigger the check.
    """
    stmt = select(CrmCandidate).where(
        CrmCandidate.crm_candidate_status == "selected",
        CrmCandidate.crm_candidate_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            CrmCandidate.crm_candidate_identifier != exclude_identifier
        )
    existing = session.scalar(stmt)
    if existing is not None:
        raise SelectedCandidateConflictError(
            existing.crm_candidate_identifier
        )


def _get_row(session: Session, identifier: str) -> CrmCandidate:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = session.get(CrmCandidate, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``CRM-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_crm_candidates(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all crm_candidates ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    Default sort is identifier-ascending per DEC-072; terminal-state
    records interleave with ``active`` records.
    """
    stmt = select(CrmCandidate).order_by(CrmCandidate.crm_candidate_identifier)
    if not include_deleted:
        stmt = stmt.where(CrmCandidate.crm_candidate_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_crm_candidate(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single crm_candidate by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = session.get(CrmCandidate, identifier)
    if row is None:
        return None
    if row.crm_candidate_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_crm_candidate_identifier(session: Session) -> str:
    """Return the next available ``CRM-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(CrmCandidate.crm_candidate_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_crm_candidate_row(
    identifier: str,
    name: str,
    fit_reason: str,
    notes: str | None,
    status: str,
) -> CrmCandidate:
    return CrmCandidate(
        crm_candidate_identifier=identifier,
        crm_candidate_name=name,
        crm_candidate_fit_reason=fit_reason,
        crm_candidate_notes=notes,
        crm_candidate_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    fit_reason: str,
    notes: str | None,
    status: str,
) -> CrmCandidate:
    """Insert a crm_candidate with a server-assigned identifier, collision-safe.

    Computes the next ``CRM-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies acceptance criterion 7 — two concurrent
    POSTs never share an identifier.
    """
    candidate = next_crm_candidate_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_crm_candidate_row(
            candidate, name, fit_reason, notes, status
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
        "could not assign a unique crm_candidate identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_crm_candidate(
    session: Session,
    *,
    name: str,
    fit_reason: str,
    notes: str | None = None,
    status: str = "active",
    identifier: str | None = None,
) -> dict:
    """Create a crm_candidate.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^CRM-\\d{3}$`` and not already exist.
    ``status`` defaults to ``active`` but may be set to any valid
    enum value on create (e.g. importing already-finalized
    candidate-set records). Creating with ``status='selected'`` is
    rejected with :class:`SelectedCandidateConflictError` if another
    live record already holds ``selected``.
    """
    name = _require_nonempty(name, field="crm_candidate_name")
    fit_reason = _require_nonempty(
        fit_reason, field="crm_candidate_fit_reason"
    )
    if status is None:
        status = "active"
    _require_status(status)
    _reject_duplicate_name(session, name)
    if status == "selected":
        _reject_second_selected(session)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, fit_reason, notes, status
        )
    else:
        _require_identifier_format(identifier)
        if session.get(CrmCandidate, identifier) is not None:
            raise ConflictError(
                f"crm_candidate {identifier!r} already exists"
            )
        row = _new_crm_candidate_row(
            identifier, name, fit_reason, notes, status
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.crm_candidate_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_crm_candidate(
    session: Session,
    identifier: str,
    *,
    crm_candidate_identifier: str | None = None,
    name: str | None = None,
    fit_reason: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``crm_candidate_identifier`` (the identifier echoed in the request
    body) must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` and ``fit_reason`` are
    required (a full replace cannot blank them); ``notes`` is replaced
    wholesale (``None`` clears it). A ``status`` change is
    transition-validated and, when the target is ``selected``,
    singleton-validated.
    """
    row = _get_row(session, identifier)
    if (
        crm_candidate_identifier is not None
        and crm_candidate_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "crm_candidate_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="crm_candidate_name")
    fit_reason = _require_nonempty(
        fit_reason, field="crm_candidate_fit_reason"
    )
    if name.lower() != row.crm_candidate_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.crm_candidate_status:
        _require_status(status)
        _check_transition(row.crm_candidate_status, status)
        if status == "selected":
            _reject_second_selected(session, exclude_identifier=identifier)
        row.crm_candidate_status = status

    row.crm_candidate_name = name
    row.crm_candidate_fit_reason = fit_reason
    row.crm_candidate_notes = notes
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


def patch_crm_candidate(
    session: Session, identifier: str, **fields
) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``fit_reason``, ``notes``, ``status``.
    A ``status`` change is transition-validated; transitioning to
    ``selected`` triggers the singleton check.
    """
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
        name = _require_nonempty(fields["name"], field="crm_candidate_name")
        if name.lower() != row.crm_candidate_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.crm_candidate_name = name
    if "fit_reason" in fields:
        row.crm_candidate_fit_reason = _require_nonempty(
            fields["fit_reason"], field="crm_candidate_fit_reason"
        )
    if "notes" in fields:
        row.crm_candidate_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.crm_candidate_status:
            _check_transition(row.crm_candidate_status, status)
            if status == "selected":
                _reject_second_selected(
                    session, exclude_identifier=identifier
                )
            row.crm_candidate_status = status

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


def delete_crm_candidate(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``crm_candidate_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Soft-deleting a record holding
    ``status='selected'`` frees the singleton slot for a different
    live record per spec section 3.4.3.
    """
    row = _get_row(session, identifier)
    if row.crm_candidate_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.crm_candidate_deleted_at = datetime.now(UTC)
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


def restore_crm_candidate(session: Session, identifier: str) -> dict:
    """Clear ``crm_candidate_deleted_at``. Raises if the row is not soft-deleted.

    Per spec section 3.5.4: if the restored record's status is
    ``selected`` and another live record already holds ``selected``,
    raise :class:`SelectedCandidateConflictError`.
    """
    row = _get_row(session, identifier)
    if row.crm_candidate_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "crm_candidate_deleted_at",
                    "not_deleted",
                    "crm_candidate is not soft-deleted",
                )
            ]
        )
    if row.crm_candidate_status == "selected":
        _reject_second_selected(session, exclude_identifier=identifier)
    before = to_dict(row)
    row.crm_candidate_deleted_at = None
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
