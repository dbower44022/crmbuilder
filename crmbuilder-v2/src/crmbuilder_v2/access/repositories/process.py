"""Process repository — the third methodology entity type (UI v0.4 slice D).

Per ``methodology-schema-specs/process.md``. The eight module-level
functions back the ``/processes`` REST endpoints and the desktop panel:

* :func:`list_processes` / :func:`get_process` — reads.
* :func:`create_process` — insert with server-side identifier
  auto-assignment (collision-safe retry, per acceptance criterion 8).
* :func:`update_process` — full replace (PUT).
* :func:`patch_process` — partial update (PATCH).
* :func:`delete_process` / :func:`restore_process` — soft-delete round-trip.
* :func:`next_process_identifier` — the ``PROC-NNN`` allocator helper.

Process diverges from ``domain`` / ``entity`` on two structural points
(see ``process.md`` section 3.4 and DEC-056):

* **No status field.** The four-value ``process_classification`` enum
  (``unclassified`` / ``mission_critical`` / ``supporting`` /
  ``deferred``) carries the lifecycle. The transition gate is one-way
  out of ``unclassified``; the three classified values move freely
  among themselves. A disallowed transition raises
  :class:`ClassificationTransitionError` (HTTP 422 with the dedicated
  body shape).

* **A required direct FK to ``domain``.** ``process_domain_identifier``
  is a scalar column, not a references-table edge. Its existence is
  validated at the access layer against live ``domain`` records (the
  v2 soft-FK convention); a missing, mal-formed, or soft-deleted
  target raises :class:`InvalidDomainReferenceError` (HTTP 422 with the
  dedicated body shape). PUT/PATCH may re-affiliate to a different live
  domain; re-affiliation does not cascade to handoff references.

Other validation posture matches the prior slices: identifier-format,
case-insensitive engagement-global name-uniqueness, and PUT
identifier/path mismatches raise :class:`UnprocessableError` (HTTP
422); missing entities raise :class:`NotFoundError` (404); an
explicit-identifier collision on create raises :class:`ConflictError`
(409). Soft-deleting a process does NOT cascade-delete its inbound or
outbound ``process_hands_off_to_process`` references (spec 3.4.5).
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
    ClassificationTransitionError,
    ConflictError,
    FieldError,
    InvalidDomainReferenceError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Domain, Process
from crmbuilder_v2.access.vocab import (
    PROCESS_CLASSIFICATION_TRANSITIONS,
    PROCESS_CLASSIFICATIONS,
)

_ENTITY_TYPE = "process"
_IDENTIFIER_PREFIX = "PROC"
_IDENTIFIER_RE = re.compile(r"^PROC-\d{3}$")
_DOMAIN_IDENTIFIER_RE = re.compile(r"^DOM-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_process`. The identifier and the
# timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "domain_identifier",
        "purpose",
        "classification",
        "classification_rationale",
        "notes",
        # v0.8 process v2 schema growth (PI-005, process-v2.md §3.2.2).
        # Six new Phase 3 content fields, all plain TEXT nullable, no
        # validation logic at this layer.
        "steps",
        "triggers",
        "outcomes",
        "edge_cases",
        "frequency",
        "duration_estimate",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "process_identifier",
                    "invalid_format",
                    r"must match ^PROC-\d{3}$ (e.g. PROC-001)",
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


def _require_classification(classification: object) -> str:
    if classification not in PROCESS_CLASSIFICATIONS:
        raise UnprocessableError(
            [
                FieldError(
                    "process_classification",
                    "invalid_value",
                    f"must be one of {sorted(PROCESS_CLASSIFICATIONS)}",
                )
            ]
        )
    return classification  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`ClassificationTransitionError` for a disallowed move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`PROCESS_CLASSIFICATION_TRANSITIONS` — the one-way
    ``unclassified`` gate.
    """
    if requested == current:
        return
    if requested not in PROCESS_CLASSIFICATION_TRANSITIONS.get(
        current, frozenset()
    ):
        raise ClassificationTransitionError(current, requested)


def _require_live_domain(session: Session, domain_identifier: object) -> str:
    """Validate ``process_domain_identifier`` against a live domain record.

    A value that is not a ``DOM-NNN`` string, refers to no domain, or
    refers to a soft-deleted domain raises
    :class:`InvalidDomainReferenceError` (HTTP 422 with the dedicated
    body shape per ``process.md`` section 3.5.4).
    """
    if not isinstance(domain_identifier, str) or not _DOMAIN_IDENTIFIER_RE.match(
        domain_identifier
    ):
        raise InvalidDomainReferenceError(str(domain_identifier))
    row = session.get(Domain, domain_identifier)
    if row is None or row.domain_deleted_at is not None:
        raise InvalidDomainReferenceError(domain_identifier)
    return domain_identifier


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``process_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``process.md`` section 3.2.1. Uniqueness is engagement-global (no
    domain-scoping). ``exclude_identifier`` lets the update paths
    ignore the row being modified.
    """
    stmt = select(Process).where(
        func.lower(Process.process_name) == name.lower(),
        Process.process_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Process.process_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "process_name",
                    "duplicate",
                    f"a process named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Process:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = session.get(Process, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``PROC-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_processes(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all processes ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Process).order_by(Process.process_identifier)
    if not include_deleted:
        stmt = stmt.where(Process.process_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_process(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single process by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = session.get(Process, identifier)
    if row is None:
        return None
    if row.process_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_process_identifier(session: Session) -> str:
    """Return the next available ``PROC-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(select(Process.process_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_process_row(
    identifier: str,
    name: str,
    domain_identifier: str,
    purpose: str,
    classification: str,
    classification_rationale: str | None,
    notes: str | None,
    *,
    steps: str | None = None,
    triggers: str | None = None,
    outcomes: str | None = None,
    edge_cases: str | None = None,
    frequency: str | None = None,
    duration_estimate: str | None = None,
) -> Process:
    return Process(
        process_identifier=identifier,
        process_name=name,
        process_domain_identifier=domain_identifier,
        process_purpose=purpose,
        process_classification=classification,
        process_classification_rationale=classification_rationale,
        process_notes=notes,
        process_steps=steps,
        process_triggers=triggers,
        process_outcomes=outcomes,
        process_edge_cases=edge_cases,
        process_frequency=frequency,
        process_duration_estimate=duration_estimate,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    domain_identifier: str,
    purpose: str,
    classification: str,
    classification_rationale: str | None,
    notes: str | None,
    *,
    steps: str | None = None,
    triggers: str | None = None,
    outcomes: str | None = None,
    edge_cases: str | None = None,
    frequency: str | None = None,
    duration_estimate: str | None = None,
) -> Process:
    """Insert a process with a server-assigned identifier, collision-safe.

    Computes the next ``PROC-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies acceptance criterion 8 — two concurrent
    POSTs never share an identifier.
    """
    candidate = next_process_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_process_row(
            candidate,
            name,
            domain_identifier,
            purpose,
            classification,
            classification_rationale,
            notes,
            steps=steps,
            triggers=triggers,
            outcomes=outcomes,
            edge_cases=edge_cases,
            frequency=frequency,
            duration_estimate=duration_estimate,
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
        "could not assign a unique process identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_process(
    session: Session,
    *,
    name: str,
    domain_identifier: str,
    purpose: str,
    classification: str = "unclassified",
    classification_rationale: str | None = None,
    notes: str | None = None,
    identifier: str | None = None,
    steps: str | None = None,
    triggers: str | None = None,
    outcomes: str | None = None,
    edge_cases: str | None = None,
    frequency: str | None = None,
    duration_estimate: str | None = None,
) -> dict:
    """Create a process.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^PROC-\\d{3}$`` and not already exist.
    ``domain_identifier`` is required and must resolve to a live
    ``domain`` record. ``classification`` defaults to ``unclassified``
    but may be set to any valid enum value on create (e.g. importing
    already-classified processes).

    The six Phase 3 content fields (``steps``, ``triggers``,
    ``outcomes``, ``edge_cases``, ``frequency``,
    ``duration_estimate``) are optional per ``process-v2.md`` §3.6.4
    — Phase 3 content may be authored at create time or after via
    PATCH. All six default to ``None`` (stored as NULL).
    """
    name = _require_nonempty(name, field="process_name")
    purpose = _require_nonempty(purpose, field="process_purpose")
    domain_identifier = _require_live_domain(session, domain_identifier)
    if classification is None:
        classification = "unclassified"
    _require_classification(classification)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            name,
            domain_identifier,
            purpose,
            classification,
            classification_rationale,
            notes,
            steps=steps,
            triggers=triggers,
            outcomes=outcomes,
            edge_cases=edge_cases,
            frequency=frequency,
            duration_estimate=duration_estimate,
        )
    else:
        _require_identifier_format(identifier)
        if session.get(Process, identifier) is not None:
            raise ConflictError(f"process {identifier!r} already exists")
        row = _new_process_row(
            identifier,
            name,
            domain_identifier,
            purpose,
            classification,
            classification_rationale,
            notes,
            steps=steps,
            triggers=triggers,
            outcomes=outcomes,
            edge_cases=edge_cases,
            frequency=frequency,
            duration_estimate=duration_estimate,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.process_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_process(
    session: Session,
    identifier: str,
    *,
    process_identifier: str | None = None,
    name: str | None = None,
    domain_identifier: str | None = None,
    purpose: str | None = None,
    classification: str | None = None,
    classification_rationale: str | None = None,
    notes: str | None = None,
    steps: str | None = None,
    triggers: str | None = None,
    outcomes: str | None = None,
    edge_cases: str | None = None,
    frequency: str | None = None,
    duration_estimate: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``process_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``domain_identifier`` /
    ``purpose`` are required (a full replace cannot blank them);
    ``classification_rationale`` and ``notes`` are replaced wholesale
    (``None`` clears them). A ``domain_identifier`` change is
    FK-validated; a ``classification`` change is transition-validated.

    The six Phase 3 content fields are replaced wholesale under PUT
    semantics per ``process-v2.md`` §3.5.2 — omitting any of them from
    the request body clears the corresponding column to NULL. To
    preserve an existing Phase 3 value without re-supplying it, use
    PATCH instead.
    """
    row = _get_row(session, identifier)
    if process_identifier is not None and process_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "process_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="process_name")
    purpose = _require_nonempty(purpose, field="process_purpose")
    domain_identifier = _require_live_domain(session, domain_identifier)
    if name.lower() != row.process_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if (
        classification is not None
        and classification != row.process_classification
    ):
        _require_classification(classification)
        _check_transition(row.process_classification, classification)
        row.process_classification = classification

    row.process_name = name
    row.process_domain_identifier = domain_identifier
    row.process_purpose = purpose
    row.process_classification_rationale = classification_rationale
    row.process_notes = notes
    # v0.8 PUT-replace of the six Phase 3 content fields. Omitted-
    # from-body values arrive as None and clear the column.
    row.process_steps = steps
    row.process_triggers = triggers
    row.process_outcomes = outcomes
    row.process_edge_cases = edge_cases
    row.process_frequency = frequency
    row.process_duration_estimate = duration_estimate
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


def patch_process(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``domain_identifier``, ``purpose``,
    ``classification``, ``classification_rationale``, ``notes``,
    and (v0.8, PI-005, ``process-v2.md`` §3.2.2) the six Phase 3
    content fields ``steps``, ``triggers``, ``outcomes``,
    ``edge_cases``, ``frequency``, ``duration_estimate``. A
    ``domain_identifier`` change is FK-validated; a ``classification``
    change is transition-validated.

    Per ``process-v2.md`` §3.5.2, each of the six new fields is
    independently PATCH-able: PATCH-to-``None`` clears the column;
    PATCH-to-``""`` stores the empty string; PATCH-to-non-empty stores
    the supplied value. The other five new fields and all v0.4 fields
    are untouched when only one is PATCH-ed.
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
        name = _require_nonempty(fields["name"], field="process_name")
        if name.lower() != row.process_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.process_name = name
    if "domain_identifier" in fields:
        row.process_domain_identifier = _require_live_domain(
            session, fields["domain_identifier"]
        )
    if "purpose" in fields:
        row.process_purpose = _require_nonempty(
            fields["purpose"], field="process_purpose"
        )
    if "classification" in fields:
        classification = _require_classification(fields["classification"])
        if classification != row.process_classification:
            _check_transition(row.process_classification, classification)
            row.process_classification = classification
    if "classification_rationale" in fields:
        row.process_classification_rationale = fields[
            "classification_rationale"
        ]
    if "notes" in fields:
        row.process_notes = fields["notes"]
    # v0.8 PATCH-ability for the six Phase 3 content fields. None clears
    # the column; "" stores empty string; non-empty stores the value.
    if "steps" in fields:
        row.process_steps = fields["steps"]
    if "triggers" in fields:
        row.process_triggers = fields["triggers"]
    if "outcomes" in fields:
        row.process_outcomes = fields["outcomes"]
    if "edge_cases" in fields:
        row.process_edge_cases = fields["edge_cases"]
    if "frequency" in fields:
        row.process_frequency = fields["frequency"]
    if "duration_estimate" in fields:
        row.process_duration_estimate = fields["duration_estimate"]

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


def delete_process(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``process_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Inbound and outbound
    ``process_hands_off_to_process`` references are NOT cascade-deleted
    (``process.md`` section 3.4.5): this function never touches the
    ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.process_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.process_deleted_at = datetime.now(UTC)
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


def restore_process(session: Session, identifier: str) -> dict:
    """Clear ``process_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.process_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "process_deleted_at",
                    "not_deleted",
                    "process is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.process_deleted_at = None
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
