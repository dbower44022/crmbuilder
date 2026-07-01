"""Participant repository — the engagement-participant methodology entity.

REL-040 / PI-094 (REQ-412). A ``participant`` is the real engagement
person/role (Implementation Consultant, Client SME, …) that a
methodology ``Persona`` is backed by via the
``persona_backed_by_participant`` reference. The eight module-level
functions back the ``/participants`` REST endpoints:

* :func:`list_participants` / :func:`get_participant` — reads.
* :func:`create_participant` — insert with server-side identifier
  auto-assignment (collision-safe retry).
* :func:`update_participant` — full replace (PUT).
* :func:`patch_participant` — partial update (PATCH).
* :func:`delete_participant` / :func:`restore_participant` — soft-delete
  round-trip.
* :func:`next_participant_identifier` — the ``PTC-NNN`` allocator helper.

Mirrors ``persona.py`` with two simplifications: a participant carries
no propose-verify lifecycle (its ``participant_status`` toggles between
``active`` and ``inactive``, no ``rejected``/decision machinery), and it
sources exactly one outbound reference kind
(``persona_backed_by_participant``, attached from the persona side).
Soft-deleting a participant never touches the ``refs`` table, so the
backing reference persists and surfaces via the show-deleted toggle on
either side.

Validation posture: identifier-format, case-insensitive name-uniqueness,
required ``participant_role_kind``, status-enum, and PUT identifier/path
mismatches raise :class:`UnprocessableError` (HTTP 422); a disallowed
status transition raises :class:`StatusTransitionError` (HTTP 422);
missing participants raise :class:`NotFoundError` (404); an
explicit-identifier collision on create raises :class:`ConflictError`
(409).
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
    serialize_identifier_assignment,
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
from crmbuilder_v2.access.models import Participant
from crmbuilder_v2.access.vocab import (
    PARTICIPANT_STATUS_TRANSITIONS,
    PARTICIPANT_STATUSES,
)

_ENTITY_TYPE = "participant"
_IDENTIFIER_PREFIX = "PTC"
_IDENTIFIER_RE = re.compile(r"^PTC-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_participant`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {"name", "role_kind", "affiliation", "contact", "notes", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "participant_identifier",
                    "invalid_format",
                    r"must match ^PTC-\d{3}$ (e.g. PTC-001)",
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
    if status not in PARTICIPANT_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "participant_status",
                    "invalid_value",
                    f"must be one of {sorted(PARTICIPANT_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`PARTICIPANT_STATUS_TRANSITIONS`. For a participant this is a
    free toggle — ``active`` and ``inactive`` each admit the other.
    """
    if requested == current:
        return
    if requested not in PARTICIPANT_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``participant_name`` collision.

    Only non-soft-deleted rows participate. Uniqueness is
    engagement-global. ``exclude_identifier`` lets the update paths
    ignore the row being modified.
    """
    stmt = select(Participant).where(
        func.lower(Participant.participant_name) == name.lower(),
        Participant.participant_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            Participant.participant_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "participant_name",
                    "duplicate",
                    f"a participant named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Participant:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(
        session, Participant, Participant.participant_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``PTC-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_participants(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all participants ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Participant).order_by(Participant.participant_identifier)
    if not include_deleted:
        stmt = stmt.where(Participant.participant_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_participant(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single participant by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(
        session, Participant, Participant.participant_identifier, identifier
    )
    if row is None:
        return None
    if row.participant_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_participant_identifier(session: Session) -> str:
    """Return the next available ``PTC-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(Participant.participant_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_participant_row(
    identifier: str,
    name: str,
    role_kind: str,
    affiliation: str | None,
    contact: str | None,
    notes: str | None,
    status: str,
) -> Participant:
    return Participant(
        participant_identifier=identifier,
        participant_name=name,
        participant_role_kind=role_kind,
        participant_affiliation=affiliation,
        participant_contact=contact,
        participant_notes=notes,
        participant_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    role_kind: str,
    affiliation: str | None,
    contact: str | None,
    notes: str | None,
    status: str,
) -> Participant:
    """Insert a participant with a server-assigned identifier, collision-safe.

    Computes the next ``PTC-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the attempt
    repeats — two concurrent POSTs never share an identifier.
    """
    # Serialize per-prefix assignment so concurrent Postgres writers don't
    # race the read-then-probe loop (no-op on SQLite; REQ-446 / PI-384).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_participant_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_participant_row(
            candidate, name, role_kind, affiliation, contact, notes, status
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
        "could not assign a unique participant identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_participant(
    session: Session,
    *,
    name: str,
    role_kind: str,
    affiliation: str | None = None,
    contact: str | None = None,
    notes: str | None = None,
    status: str = "active",
    identifier: str | None = None,
) -> dict:
    """Create a participant.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^PTC-\\d{3}$`` and not already exist.
    ``status`` defaults to ``active``.
    """
    name = _require_nonempty(name, field="participant_name")
    role_kind = _require_nonempty(role_kind, field="participant_role_kind")
    if status is None:
        status = "active"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, role_kind, affiliation, contact, notes, status
        )
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                Participant,
                Participant.participant_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"participant {identifier!r} already exists")
        row = _new_participant_row(
            identifier, name, role_kind, affiliation, contact, notes, status
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.participant_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_participant(
    session: Session,
    identifier: str,
    *,
    participant_identifier: str | None = None,
    name: str | None = None,
    role_kind: str | None = None,
    affiliation: str | None = None,
    contact: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``participant_identifier`` (echoed in the body) must match the path
    ``identifier`` — a mismatch raises :class:`UnprocessableError`.
    ``name`` / ``role_kind`` are required (a full replace cannot blank
    them); ``affiliation`` / ``contact`` / ``notes`` are replaced
    wholesale (``None`` clears them). A ``status`` change is
    transition-validated.
    """
    row = _get_row(session, identifier)
    if (
        participant_identifier is not None
        and participant_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "participant_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="participant_name")
    role_kind = _require_nonempty(role_kind, field="participant_role_kind")
    if name.lower() != row.participant_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.participant_status:
        _require_status(status)
        _check_transition(row.participant_status, status)
        row.participant_status = status

    row.participant_name = name
    row.participant_role_kind = role_kind
    row.participant_affiliation = affiliation
    row.participant_contact = contact
    row.participant_notes = notes
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


def patch_participant(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``role_kind``, ``affiliation``,
    ``contact``, ``notes``, ``status``. A ``status`` change is
    transition-validated.
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
        name = _require_nonempty(fields["name"], field="participant_name")
        if name.lower() != row.participant_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.participant_name = name
    if "role_kind" in fields:
        row.participant_role_kind = _require_nonempty(
            fields["role_kind"], field="participant_role_kind"
        )
    if "affiliation" in fields:
        row.participant_affiliation = fields["affiliation"]
    if "contact" in fields:
        row.participant_contact = fields["contact"]
    if "notes" in fields:
        row.participant_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.participant_status:
            _check_transition(row.participant_status, status)
            row.participant_status = status

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


def delete_participant(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``participant_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. The outbound
    ``persona_backed_by_participant`` reference is NOT cascade-deleted:
    this function never touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.participant_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.participant_deleted_at = datetime.now(UTC)
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


def restore_participant(session: Session, identifier: str) -> dict:
    """Clear ``participant_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.participant_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "participant_deleted_at",
                    "not_deleted",
                    "participant is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.participant_deleted_at = None
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
