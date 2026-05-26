"""Persona repository — the fifth methodology entity type (v0.5+, PI-003).

Per ``methodology-schema-specs/persona.md``. The eight module-level
functions back the ``/personas`` REST endpoints and the desktop panel:

* :func:`list_personas` / :func:`get_persona` — reads.
* :func:`create_persona` — insert with server-side identifier
  auto-assignment (collision-safe retry, per acceptance criterion 7).
* :func:`update_persona` — full replace (PUT).
* :func:`patch_persona` — partial update (PATCH).
* :func:`delete_persona` / :func:`restore_persona` — soft-delete
  round-trip.
* :func:`next_persona_identifier` — the ``PER-NNN`` allocator helper.

Validation posture (``persona.md`` §3.5): identifier-format,
case-insensitive name-uniqueness, status-enum, and PUT
identifier/path mismatches raise :class:`UnprocessableError`
(HTTP 422); disallowed status transitions raise
:class:`StatusTransitionError` (HTTP 422 with the dedicated body
shape). Missing personas raise :class:`NotFoundError` (404); an
explicit-identifier collision on create raises
:class:`ConflictError` (409).

The repository mirrors ``entity.py`` exactly with persona-specific
adjustments. Two spec points worth noting:

* ``persona_status`` is independent of any affiliated domains'
  statuses and the realization entity's status (``persona.md``
  §3.4.3). This module never consults domain or entity records when
  validating a persona-status change — the lifecycles are managed
  separately.
* Soft-deleting a persona does NOT cascade-delete its outbound
  ``persona_scopes_to_domain`` or ``persona_realized_as_entity``
  references (``persona.md`` §3.4.6). Those rows live in the
  ``refs`` table and the soft-delete here never touches it; the
  references persist and surface via the show-deleted toggle on
  either side.
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
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Persona
from crmbuilder_v2.access.vocab import (
    PERSONA_STATUS_TRANSITIONS,
    PERSONA_STATUSES,
)

_ENTITY_TYPE = "persona"
_IDENTIFIER_PREFIX = "PER"
_IDENTIFIER_RE = re.compile(r"^PER-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_persona`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {"name", "role_summary", "responsibilities", "notes", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "persona_identifier",
                    "invalid_format",
                    r"must match ^PER-\d{3}$ (e.g. PER-001)",
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
    if status not in PERSONA_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "persona_status",
                    "invalid_value",
                    f"must be one of {sorted(PERSONA_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`PERSONA_STATUS_TRANSITIONS`. Per ``persona.md`` §3.4.3 this
    check consults only the persona's own status — never the statuses
    of any affiliated domains or the realization entity.
    """
    if requested == current:
        return
    if requested not in PERSONA_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``persona_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``persona.md`` §3.2.1. Uniqueness is engagement-global.
    ``exclude_identifier`` lets the update paths ignore the row being
    modified.
    """
    stmt = select(Persona).where(
        func.lower(Persona.persona_name) == name.lower(),
        Persona.persona_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Persona.persona_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "persona_name",
                    "duplicate",
                    f"a persona named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Persona:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = session.get(Persona, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``PER-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_personas(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all personas ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Persona).order_by(Persona.persona_identifier)
    if not include_deleted:
        stmt = stmt.where(Persona.persona_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_persona(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single persona by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = session.get(Persona, identifier)
    if row is None:
        return None
    if row.persona_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_persona_identifier(session: Session) -> str:
    """Return the next available ``PER-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(select(Persona.persona_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_persona_row(
    identifier: str,
    name: str,
    role_summary: str,
    responsibilities: str | None,
    notes: str | None,
    status: str,
) -> Persona:
    return Persona(
        persona_identifier=identifier,
        persona_name=name,
        persona_role_summary=role_summary,
        persona_responsibilities=responsibilities,
        persona_notes=notes,
        persona_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    role_summary: str,
    responsibilities: str | None,
    notes: str | None,
    status: str,
) -> Persona:
    """Insert a persona with a server-assigned identifier, collision-safe.

    Computes the next ``PER-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies acceptance criterion 7 — two concurrent
    POSTs never share an identifier.
    """
    candidate = next_persona_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_persona_row(
            candidate, name, role_summary, responsibilities, notes, status
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            # Another transaction committed this identifier first.
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique persona identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_persona(
    session: Session,
    *,
    name: str,
    role_summary: str,
    responsibilities: str | None = None,
    notes: str | None = None,
    status: str = "candidate",
    identifier: str | None = None,
) -> dict:
    """Create a persona.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^PER-\\d{3}$`` and not already exist.
    ``status`` defaults to ``candidate`` but may be set to any valid
    enum value on create (e.g. importing already-confirmed personas).
    """
    name = _require_nonempty(name, field="persona_name")
    role_summary = _require_nonempty(role_summary, field="persona_role_summary")
    if status is None:
        status = "candidate"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, role_summary, responsibilities, notes, status
        )
    else:
        _require_identifier_format(identifier)
        if session.get(Persona, identifier) is not None:
            raise ConflictError(f"persona {identifier!r} already exists")
        row = _new_persona_row(
            identifier, name, role_summary, responsibilities, notes, status
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.persona_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_persona(
    session: Session,
    identifier: str,
    *,
    persona_identifier: str | None = None,
    name: str | None = None,
    role_summary: str | None = None,
    responsibilities: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``persona_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``role_summary`` are
    required (a full replace cannot blank them); ``responsibilities``
    and ``notes`` are replaced wholesale (``None`` clears them). A
    ``status`` change is transition-validated.
    """
    row = _get_row(session, identifier)
    if persona_identifier is not None and persona_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "persona_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="persona_name")
    role_summary = _require_nonempty(
        role_summary, field="persona_role_summary"
    )
    if name.lower() != row.persona_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.persona_status:
        _require_status(status)
        _check_transition(row.persona_status, status)
        row.persona_status = status

    row.persona_name = name
    row.persona_role_summary = role_summary
    row.persona_responsibilities = responsibilities
    row.persona_notes = notes
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


def patch_persona(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``role_summary``, ``responsibilities``,
    ``notes``, ``status``. A ``status`` change is transition-validated.
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
        name = _require_nonempty(fields["name"], field="persona_name")
        if name.lower() != row.persona_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.persona_name = name
    if "role_summary" in fields:
        row.persona_role_summary = _require_nonempty(
            fields["role_summary"], field="persona_role_summary"
        )
    if "responsibilities" in fields:
        row.persona_responsibilities = fields["responsibilities"]
    if "notes" in fields:
        row.persona_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.persona_status:
            _check_transition(row.persona_status, status)
            row.persona_status = status

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


def delete_persona(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``persona_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Outbound
    ``persona_scopes_to_domain`` and ``persona_realized_as_entity``
    references are NOT cascade-deleted (``persona.md`` §3.4.6): this
    function never touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.persona_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.persona_deleted_at = datetime.now(UTC)
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


def restore_persona(session: Session, identifier: str) -> dict:
    """Clear ``persona_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.persona_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "persona_deleted_at",
                    "not_deleted",
                    "persona is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.persona_deleted_at = None
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
