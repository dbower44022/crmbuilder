"""Manual Config repository — PI-004 cohort methodology entity (v0.5+).

Per ``methodology-schema-specs/manual_config.md`` v1.0. The eight
module-level functions back the ``/manual-configs`` REST endpoints and
the desktop panel:

* :func:`list_manual_configs` / :func:`get_manual_config` — reads.
* :func:`create_manual_config` — insert with server-side identifier
  auto-assignment (collision-safe retry, per spec acceptance criterion 9).
* :func:`update_manual_config` — full replace (PUT).
* :func:`patch_manual_config` — partial update (PATCH).
* :func:`delete_manual_config` / :func:`restore_manual_config` —
  soft-delete round-trip.
* :func:`next_manual_config_identifier` — the ``MCF-NNN`` allocator helper.

Validation posture (``manual_config.md`` §3.5): identifier-format,
case-insensitive global name-uniqueness, status-enum, category-enum,
and PUT identifier/path mismatches raise :class:`UnprocessableError`
(HTTP 422); disallowed status transitions raise
:class:`StatusTransitionError` (HTTP 422 with the dedicated body
shape); the §3.5.3 cross-field invariant raises
:class:`CompletedStatusRequiresCompletionFieldsError` (HTTP 422 with
the dedicated ``completed_status_requires_completion_fields`` body).
Missing records raise :class:`NotFoundError` (404); an explicit-
identifier collision on create raises :class:`ConflictError` (409).

The repository mirrors ``entity.py`` exactly with two manual_config-
specific adjustments:

* **Category-enum validation** parallels status-enum validation against
  the seven-value ``MANUAL_CONFIG_CATEGORIES`` set.
* **Cross-field invariant on transition into ``completed``** per spec
  §3.5.3 — :func:`_require_completion_fields_for_completed` server-
  defaults ``completed_at`` to ``now()`` when omitted; rejects when
  ``completed_by`` is missing. Applied on create / PUT / PATCH paths
  against the post-write status value.
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
    CompletedStatusRequiresCompletionFieldsError,
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import ManualConfig
from crmbuilder_v2.access.vocab import (
    MANUAL_CONFIG_CATEGORIES,
    MANUAL_CONFIG_STATUS_TRANSITIONS,
    MANUAL_CONFIG_STATUSES,
)

_ENTITY_TYPE = "manual_config"
_IDENTIFIER_PREFIX = "MCF"
_IDENTIFIER_RE = re.compile(r"^MCF-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_manual_config`. The identifier and
# the timestamps are not patchable.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "category",
        "description",
        "instructions",
        "notes",
        "status",
        "completed_at",
        "completed_by",
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
                    "manual_config_identifier",
                    "invalid_format",
                    r"must match ^MCF-\d{3}$ (e.g. MCF-001)",
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
    if status not in MANUAL_CONFIG_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_status",
                    "invalid_value",
                    f"must be one of {sorted(MANUAL_CONFIG_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _require_category(category: object) -> str:
    """Validate ``manual_config_category`` against the seven-value enum.

    Per spec §3.2.3 — the vocabulary is closed in v0.5+; free-text
    sub-classification under ``other`` is deferred to a v0.6+ planning
    item.
    """
    if category not in MANUAL_CONFIG_CATEGORIES:
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_category",
                    "invalid_value",
                    f"must be one of {sorted(MANUAL_CONFIG_CATEGORIES)}",
                )
            ]
        )
    return category  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`MANUAL_CONFIG_STATUS_TRANSITIONS`. The terminal ``completed``
    state has an empty successor set — any non-no-op transition out of
    ``completed`` raises (the methodology preserves audit gap by
    requiring soft-delete-and-redo instead, per spec §3.4.3).
    """
    if requested == current:
        return
    if requested not in MANUAL_CONFIG_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _require_completion_fields_for_completed(
    *,
    status_after: str,
    completed_at: datetime | None,
    completed_by: str | None,
) -> tuple[datetime | None, str | None]:
    """Enforce the §3.5.3 cross-field invariant for ``completed``.

    When ``status_after`` is ``'completed'``:

    * ``completed_at`` is server-defaulted to ``datetime.now(UTC)`` if
      omitted (None). The spec permits this so consultants don't have
      to author a timestamp by hand for the common "operator just did
      it" flow.
    * ``completed_by`` must be a non-empty string. Missing or
      blank raises :class:`CompletedStatusRequiresCompletionFieldsError`
      with ``missing=["manual_config_completed_by"]``.

    When ``status_after`` is any other value the inputs are returned
    unchanged — the spec permits setting completion fields on a non-
    completed record (discouraged but not erroneous) and the UI hides
    the affordance to keep that contract clean.

    Returns the (possibly server-defaulted) ``completed_at`` and
    normalised ``completed_by`` tuple.
    """
    if status_after != "completed":
        # Permissive on non-completed status. Strip whitespace on
        # completed_by if it is present so the storage layer never
        # carries semantically-blank strings even outside the
        # invariant.
        normalised_by = (
            completed_by.strip() if isinstance(completed_by, str) else completed_by
        )
        return completed_at, normalised_by

    missing: list[str] = []
    normalised_by: str | None = None
    if isinstance(completed_by, str) and completed_by.strip():
        normalised_by = completed_by.strip()
    else:
        missing.append("manual_config_completed_by")

    if missing:
        raise CompletedStatusRequiresCompletionFieldsError(missing)

    resolved_at = completed_at if completed_at is not None else datetime.now(UTC)
    return resolved_at, normalised_by


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``manual_config_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``manual_config.md`` §3.2.1. Uniqueness is engagement-global.
    """
    stmt = select(ManualConfig).where(
        func.lower(ManualConfig.manual_config_name) == name.lower(),
        ManualConfig.manual_config_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            ManualConfig.manual_config_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_name",
                    "duplicate",
                    f"a manual_config named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> ManualConfig:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = session.get(ManualConfig, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``MCF-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_manual_configs(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all manual_configs ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(ManualConfig).order_by(ManualConfig.manual_config_identifier)
    if not include_deleted:
        stmt = stmt.where(ManualConfig.manual_config_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_manual_config(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single manual_config by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = session.get(ManualConfig, identifier)
    if row is None:
        return None
    if row.manual_config_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_manual_config_identifier(session: Session) -> str:
    """Return the next available ``MCF-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(
        select(ManualConfig.manual_config_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_manual_config_row(
    identifier: str,
    name: str,
    category: str,
    description: str,
    instructions: str,
    notes: str | None,
    status: str,
    completed_at: datetime | None,
    completed_by: str | None,
) -> ManualConfig:
    return ManualConfig(
        manual_config_identifier=identifier,
        manual_config_name=name,
        manual_config_category=category,
        manual_config_description=description,
        manual_config_instructions=instructions,
        manual_config_notes=notes,
        manual_config_status=status,
        manual_config_completed_at=completed_at,
        manual_config_completed_by=completed_by,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    category: str,
    description: str,
    instructions: str,
    notes: str | None,
    status: str,
    completed_at: datetime | None,
    completed_by: str | None,
) -> ManualConfig:
    """Insert a manual_config with a server-assigned identifier, collision-safe.

    Computes the next ``MCF-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies spec acceptance criterion 9 — two
    concurrent POSTs never share an identifier.
    """
    candidate = next_manual_config_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_manual_config_row(
            candidate,
            name,
            category,
            description,
            instructions,
            notes,
            status,
            completed_at,
            completed_by,
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
        "could not assign a unique manual_config identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_manual_config(
    session: Session,
    *,
    name: str,
    category: str,
    description: str,
    instructions: str,
    notes: str | None = None,
    status: str | None = None,
    completed_at: datetime | None = None,
    completed_by: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a manual_config.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^MCF-\\d{3}$`` and not already exist.
    ``status`` defaults to ``candidate`` when None per spec §3.5.3.
    POST with ``status='completed'`` is permitted (e.g. importing
    already-performed records) provided both completion fields are
    populated in the same body — ``completed_at`` server-defaults to
    ``now()`` if omitted; ``completed_by`` must be supplied or the
    request raises :class:`CompletedStatusRequiresCompletionFieldsError`.
    """
    name = _require_nonempty(name, field="manual_config_name")
    _require_category(category)
    description = _require_nonempty(
        description, field="manual_config_description"
    )
    instructions = _require_nonempty(
        instructions, field="manual_config_instructions"
    )
    if status is None:
        status = "candidate"
    _require_status(status)
    _reject_duplicate_name(session, name)

    # §3.5.3 cross-field invariant — applied against the post-write
    # status. completed_at may be server-defaulted; completed_by must
    # be supplied when status is ``completed``.
    resolved_completed_at, resolved_completed_by = (
        _require_completion_fields_for_completed(
            status_after=status,
            completed_at=completed_at,
            completed_by=completed_by,
        )
    )

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            name,
            category,
            description,
            instructions,
            notes,
            status,
            resolved_completed_at,
            resolved_completed_by,
        )
    else:
        _require_identifier_format(identifier)
        if session.get(ManualConfig, identifier) is not None:
            raise ConflictError(
                f"manual_config {identifier!r} already exists"
            )
        row = _new_manual_config_row(
            identifier,
            name,
            category,
            description,
            instructions,
            notes,
            status,
            resolved_completed_at,
            resolved_completed_by,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.manual_config_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_manual_config(
    session: Session,
    identifier: str,
    *,
    manual_config_identifier: str | None = None,
    name: str | None = None,
    category: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    completed_at: datetime | None = None,
    completed_by: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``manual_config_identifier`` (the identifier echoed in the request
    body) must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``category`` /
    ``description`` / ``instructions`` / ``status`` are required (a
    full replace cannot blank them); ``notes`` is replaced wholesale
    (``None`` clears it). A ``status`` change is transition-validated;
    transitioning into ``completed`` triggers the §3.5.3 cross-field
    invariant against the post-write completion-field values.
    """
    row = _get_row(session, identifier)
    if (
        manual_config_identifier is not None
        and manual_config_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="manual_config_name")
    _require_category(category)
    description = _require_nonempty(
        description, field="manual_config_description"
    )
    instructions = _require_nonempty(
        instructions, field="manual_config_instructions"
    )
    if status is None or status not in MANUAL_CONFIG_STATUSES:
        # PUT requires status; an absent or invalid value is rejected
        # before any state mutation so the row never shifts between a
        # path-mismatch reject and a status-enum reject.
        _require_status(status)
    if name.lower() != row.manual_config_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status != row.manual_config_status:
        _check_transition(row.manual_config_status, status)

    # §3.5.3 cross-field invariant against the post-write status.
    resolved_completed_at, resolved_completed_by = (
        _require_completion_fields_for_completed(
            status_after=status,
            completed_at=completed_at,
            completed_by=completed_by,
        )
    )

    row.manual_config_name = name
    row.manual_config_category = category
    row.manual_config_description = description
    row.manual_config_instructions = instructions
    row.manual_config_notes = notes
    row.manual_config_status = status
    row.manual_config_completed_at = resolved_completed_at
    row.manual_config_completed_by = resolved_completed_by
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


def patch_manual_config(
    session: Session, identifier: str, **fields
) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``category``, ``description``,
    ``instructions``, ``notes``, ``status``, ``completed_at``,
    ``completed_by``. A ``status`` change is transition-validated;
    transitioning into ``completed`` triggers the §3.5.3 cross-field
    invariant against the post-merge values — so a PATCH that sets
    only ``status: completed`` on a record whose completion fields are
    null fails with the dedicated 422 body identifying the missing
    field(s).
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
        name = _require_nonempty(
            fields["name"], field="manual_config_name"
        )
        if name.lower() != row.manual_config_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.manual_config_name = name
    if "category" in fields:
        row.manual_config_category = _require_category(fields["category"])
    if "description" in fields:
        row.manual_config_description = _require_nonempty(
            fields["description"], field="manual_config_description"
        )
    if "instructions" in fields:
        row.manual_config_instructions = _require_nonempty(
            fields["instructions"], field="manual_config_instructions"
        )
    if "notes" in fields:
        row.manual_config_notes = fields["notes"]

    # Compute the post-merge status + completion-field values BEFORE
    # touching the row's status, so the cross-field invariant sees the
    # values the caller actually intends (PATCH allows status alone, or
    # completion-by alone, or both). The status transition check still
    # runs against the pre-write current status per spec §3.4.3.
    status_after = fields.get("status", row.manual_config_status)
    if "status" in fields:
        status_after = _require_status(fields["status"])
        if status_after != row.manual_config_status:
            _check_transition(row.manual_config_status, status_after)

    completed_at_after = fields.get(
        "completed_at", row.manual_config_completed_at
    )
    completed_by_after = fields.get(
        "completed_by", row.manual_config_completed_by
    )

    # The invariant is target-state aware: if the PATCH transitions
    # into completed, server-default completed_at if needed and require
    # completed_by. If the PATCH leaves status alone (or moves it to a
    # non-completed value), the helper passes the inputs through.
    resolved_completed_at, resolved_completed_by = (
        _require_completion_fields_for_completed(
            status_after=status_after,
            completed_at=completed_at_after,
            completed_by=completed_by_after,
        )
    )

    if "status" in fields:
        row.manual_config_status = status_after
    if (
        "completed_at" in fields
        or status_after == "completed"
    ):
        row.manual_config_completed_at = resolved_completed_at
    if (
        "completed_by" in fields
        or status_after == "completed"
    ):
        row.manual_config_completed_by = resolved_completed_by

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


def delete_manual_config(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``manual_config_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Outbound references (all four kinds)
    are NOT cascade-deleted per spec §3.4.6: this function never
    touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.manual_config_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.manual_config_deleted_at = datetime.now(UTC)
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


def restore_manual_config(session: Session, identifier: str) -> dict:
    """Clear ``manual_config_deleted_at``. Raises if the row is not soft-deleted.

    No cross-field invariant on restore — the existing status and
    completion fields are unchanged, so by definition they're already
    consistent.
    """
    row = _get_row(session, identifier)
    if row.manual_config_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "manual_config_deleted_at",
                    "not_deleted",
                    "manual_config is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.manual_config_deleted_at = None
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
