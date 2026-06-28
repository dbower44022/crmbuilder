"""Entity repository — the second methodology entity type (UI v0.4 slice C).

Per ``methodology-schema-specs/entity.md``. The eight module-level
functions back the ``/entities`` REST endpoints and the desktop panel:

* :func:`list_entities` / :func:`get_entity` — reads.
* :func:`create_entity` — insert with server-side identifier
  auto-assignment (collision-safe retry, per acceptance criterion 7).
* :func:`update_entity` — full replace (PUT).
* :func:`patch_entity` — partial update (PATCH).
* :func:`delete_entity` / :func:`restore_entity` — soft-delete round-trip.
* :func:`next_entity_identifier` — the ``ENT-NNN`` allocator helper.

Validation posture (``entity.md`` section 3.5): identifier-format,
case-insensitive name-uniqueness, status-enum, and PUT identifier/path
mismatches raise :class:`UnprocessableError` (HTTP 422); disallowed
status transitions raise :class:`StatusTransitionError` (HTTP 422 with
the dedicated body shape). Missing entities raise
:class:`NotFoundError` (404); an explicit-identifier collision on
create raises :class:`ConflictError` (409).

The repository mirrors ``domain.py`` exactly with entity-specific
adjustments. Two spec points worth noting:

* ``entity_status`` is independent of any affiliated domains' statuses
  (``entity.md`` section 3.4.3). This module never consults domain
  records when validating an entity-status change — the two lifecycles
  are managed separately.
* Soft-deleting an entity does NOT cascade-delete its outbound
  ``entity_scopes_to_domain`` references (``entity.md`` section 3.4.6).
  Those rows live in the ``refs`` table and the soft-delete here never
  touches it; the references persist and surface via the show-deleted
  toggle on either side.
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
from crmbuilder_v2.access.models import Entity
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    ENTITY_KINDS,
    ENTITY_SORT_DIRECTIONS,
    ENTITY_STATUS_TRANSITIONS,
    ENTITY_STATUSES,
)

_ENTITY_TYPE = "entity"
_IDENTIFIER_PREFIX = "ENT"
_IDENTIFIER_RE = re.compile(r"^ENT-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_entity`. The identifier and the
# timestamps are not patchable. v0.5+ PI-010 adds ``kind`` per
# ``entity.md`` v1.1 §3.2.3 / DEC-292. PRJ-025 PI-182 adds the three
# intrinsic engine-neutral design-intent attributes (§6).
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "description",
        "notes",
        "status",
        "kind",
        "default_sort_field",
        "default_sort_direction",
        "track_activity",
        "tracks_activities",
        "text_filter_fields",
        "full_text_search",
        "full_text_search_min_length",
        "label",
        "label_plural",
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
                    "entity_identifier",
                    "invalid_format",
                    r"must match ^ENT-\d{3}$ (e.g. ENT-001)",
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
    if status not in ENTITY_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_status",
                    "invalid_value",
                    f"must be one of {sorted(ENTITY_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _coerce_kind(kind: object) -> str | None:
    """Validate ``entity_kind`` per ``entity.md`` v1.1 §3.2.3 / DEC-292.

    ``None`` is admitted unchanged (operator-deferred classification).
    Empty / whitespace strings are coerced to ``None`` so callers can
    use ``""`` interchangeably with ``null`` to clear the field. Any
    other value must be a member of :data:`ENTITY_KINDS`.
    """
    if kind is None:
        return None
    if isinstance(kind, str) and not kind.strip():
        return None
    if kind not in ENTITY_KINDS:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_kind",
                    "invalid_value",
                    f"must be null or one of {sorted(ENTITY_KINDS)}",
                )
            ]
        )
    return kind  # type: ignore[return-value]


def _coerce_sort_direction(value: object) -> str | None:
    """Validate ``entity_default_sort_direction`` (PRJ-025 §6).

    ``None`` / empty clears; otherwise must be a member of
    :data:`ENTITY_SORT_DIRECTIONS`.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if value not in ENTITY_SORT_DIRECTIONS:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_default_sort_direction",
                    "invalid_value",
                    f"must be null or one of {sorted(ENTITY_SORT_DIRECTIONS)}",
                )
            ]
        )
    return value  # type: ignore[return-value]


def _coerce_sort_field(value: object) -> str | None:
    """Normalise ``entity_default_sort_field`` — store the authored string."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise UnprocessableError(
            [
                FieldError(
                    "entity_default_sort_field",
                    "invalid_value",
                    "must be a string or null",
                )
            ]
        )
    value = value.strip()
    return value or None


def _coerce_text_filter_fields(value: object) -> list[str] | None:
    """Normalise ``entity_text_filter_fields`` (REQ-340 / PI-300).

    ``None`` / empty list clears; otherwise must be a list of non-empty
    strings (the quick-search field names). Members are stripped; an
    all-empty list collapses to ``None``.
    """
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise UnprocessableError(
            [
                FieldError(
                    "entity_text_filter_fields",
                    "invalid_value",
                    "must be a list of strings or null",
                )
            ]
        )
    cleaned = [v.strip() for v in value if v.strip()]
    return cleaned or None


def _coerce_fts_min_length(value: object) -> int | None:
    """Validate ``entity_full_text_search_min_length`` (REQ-340 / PI-300).

    ``None`` clears; otherwise must be a non-negative integer (``bool`` is
    rejected — it is an ``int`` subclass but never a valid length).
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_full_text_search_min_length",
                    "invalid_value",
                    "must be a non-negative integer or null",
                )
            ]
        )
    return value


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`ENTITY_STATUS_TRANSITIONS`. Per ``entity.md`` section 3.4.3
    this check consults only the entity's own status — never the
    statuses of any affiliated domains.
    """
    if requested == current:
        return
    if requested not in ENTITY_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    """Reject a case-insensitive ``entity_name`` collision.

    Only non-soft-deleted rows participate in the uniqueness check, per
    ``entity.md`` section 3.2.1. Uniqueness is engagement-global (no
    domain-scoping). ``exclude_identifier`` lets the update paths ignore
    the row being modified.
    """
    stmt = select(Entity).where(
        func.lower(Entity.entity_name) == name.lower(),
        Entity.entity_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Entity.entity_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_name",
                    "duplicate",
                    f"an entity named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Entity:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, Entity, Entity.entity_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``ENT-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_entities(
    session: Session, *, include_deleted: bool = False
) -> list[dict]:
    """Return all entities ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    """
    stmt = select(Entity).order_by(Entity.entity_identifier)
    if not include_deleted:
        stmt = stmt.where(Entity.entity_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_entity(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single entity by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, Entity, Entity.entity_identifier, identifier)
    if row is None:
        return None
    if row.entity_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_entity_identifier(session: Session) -> str:
    """Return the next available ``ENT-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired identifier
    is never reused.
    """
    identifiers = session.scalars(select(Entity.entity_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_entity_row(
    identifier: str,
    name: str,
    description: str,
    notes: str | None,
    status: str,
    kind: str | None,
    default_sort_field: str | None = None,
    default_sort_direction: str | None = None,
    track_activity: bool = False,
    tracks_activities: bool = False,
    text_filter_fields: list[str] | None = None,
    full_text_search: bool = False,
    full_text_search_min_length: int | None = None,
) -> Entity:
    return Entity(
        entity_identifier=identifier,
        entity_name=name,
        entity_description=description,
        entity_notes=notes,
        entity_status=status,
        entity_kind=kind,
        entity_default_sort_field=default_sort_field,
        entity_default_sort_direction=default_sort_direction,
        entity_track_activity=track_activity,
        entity_tracks_activities=tracks_activities,
        entity_text_filter_fields=text_filter_fields,
        entity_full_text_search=full_text_search,
        entity_full_text_search_min_length=full_text_search_min_length,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    description: str,
    notes: str | None,
    status: str,
    kind: str | None,
    default_sort_field: str | None = None,
    default_sort_direction: str | None = None,
    track_activity: bool = False,
    tracks_activities: bool = False,
    text_filter_fields: list[str] | None = None,
    full_text_search: bool = False,
    full_text_search_min_length: int | None = None,
) -> Entity:
    """Insert an entity with a server-assigned identifier, collision-safe.

    Computes the next ``ENT-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats. Satisfies acceptance criterion 7 — two concurrent
    POSTs never share an identifier.
    """
    candidate = next_entity_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_entity_row(
            candidate,
            name,
            description,
            notes,
            status,
            kind,
            default_sort_field,
            default_sort_direction,
            track_activity,
            tracks_activities,
            text_filter_fields,
            full_text_search,
            full_text_search_min_length,
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
        "could not assign a unique entity identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_entity(
    session: Session,
    *,
    name: str,
    description: str,
    notes: str | None = None,
    status: str = "candidate",
    kind: str | None = None,
    identifier: str | None = None,
    default_sort_field: str | None = None,
    default_sort_direction: str | None = None,
    track_activity: bool | None = None,
    tracks_activities: bool | None = None,
    text_filter_fields: list[str] | None = None,
    full_text_search: bool | None = None,
    full_text_search_min_length: int | None = None,
) -> dict:
    """Create an entity.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^ENT-\\d{3}$`` and not already exist.
    ``status`` defaults to ``candidate`` but may be set to any valid
    enum value on create (e.g. importing already-confirmed entities).
    ``kind`` is optional per ``entity.md`` v1.1 §3.2.3 / DEC-292 —
    operators may defer classification when Phase 1 surfaces an
    entity before its kind is settled.

    PRJ-025 PI-182: ``default_sort_field`` / ``default_sort_direction``
    (asc/desc) carry the §6 default-sort intent; ``track_activity`` the
    neutral activity-feed intent. All optional and default to
    null/null/False.
    """
    name = _require_nonempty(name, field="entity_name")
    description = _require_nonempty(description, field="entity_description")
    if status is None:
        status = "candidate"
    _require_status(status)
    kind = _coerce_kind(kind)
    default_sort_field = _coerce_sort_field(default_sort_field)
    default_sort_direction = _coerce_sort_direction(default_sort_direction)
    track_activity = bool(track_activity)
    tracks_activities = bool(tracks_activities)
    text_filter_fields = _coerce_text_filter_fields(text_filter_fields)
    full_text_search = bool(full_text_search)
    full_text_search_min_length = _coerce_fts_min_length(full_text_search_min_length)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, description, notes, status, kind,
            default_sort_field, default_sort_direction, track_activity,
            tracks_activities, text_filter_fields, full_text_search,
            full_text_search_min_length,
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, Entity, Entity.entity_identifier, identifier) is not None:
            raise ConflictError(f"entity {identifier!r} already exists")
        row = _new_entity_row(
            identifier, name, description, notes, status, kind,
            default_sort_field, default_sort_direction, track_activity,
            tracks_activities, text_filter_fields, full_text_search,
            full_text_search_min_length,
        )
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.entity_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def _flag_design_staleness(
    session: Session, identifier: str, before: dict, after: dict
) -> None:
    """PI-345 hook: an entity rename flips resolved source mappings targeting it
    stale (design_changed). Lazy import avoids a repo import cycle."""
    from crmbuilder_v2.access.repositories import design_staleness
    design_staleness.on_entity_updated(session, identifier, before, after)


def update_entity(
    session: Session,
    identifier: str,
    *,
    entity_identifier: str | None = None,
    name: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    kind: str | None = None,
    rejected_by_decision: str | None = None,
    default_sort_field: str | None = None,
    default_sort_direction: str | None = None,
    track_activity: bool | None = None,
    tracks_activities: bool | None = None,
    text_filter_fields: list[str] | None = None,
    full_text_search: bool | None = None,
    full_text_search_min_length: int | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``entity_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``description`` are required
    (a full replace cannot blank them); ``notes`` is replaced wholesale
    (``None`` clears it). A ``status`` change is transition-validated.
    ``kind`` is replaced wholesale (``None`` clears it) per PUT
    semantics; omitted-from-body deserialises to ``None`` and likewise
    clears the field — operators wanting partial update should use
    PATCH.

    PRJ-025 PI-182: the §6 intrinsics
    (``default_sort_field`` / ``default_sort_direction`` /
    ``track_activity``) are replaced wholesale under the same PUT
    semantics (omitted deserialises to null/null/False).
    """
    row = _get_row(session, identifier)
    if entity_identifier is not None and entity_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="entity_name")
    description = _require_nonempty(description, field="entity_description")
    if name.lower() != row.entity_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)
    if status is not None and status != row.entity_status:
        _require_status(status)
        _check_transition(row.entity_status, status)
        if status == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.entity_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.entity_status,
        )

    row.entity_name = name
    row.entity_description = description
    row.entity_notes = notes
    row.entity_kind = _coerce_kind(kind)
    row.entity_default_sort_field = _coerce_sort_field(default_sort_field)
    row.entity_default_sort_direction = _coerce_sort_direction(
        default_sort_direction
    )
    row.entity_track_activity = bool(track_activity)
    row.entity_tracks_activities = bool(tracks_activities)
    row.entity_text_filter_fields = _coerce_text_filter_fields(text_filter_fields)
    row.entity_full_text_search = bool(full_text_search)
    row.entity_full_text_search_min_length = _coerce_fts_min_length(
        full_text_search_min_length
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
    _flag_design_staleness(session, identifier, before, after)
    return after


def patch_entity(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``description``, ``notes``, ``status``,
    ``kind``, ``rejected_by_decision``, and the PRJ-025 PI-182 §6
    intrinsics (``default_sort_field``, ``default_sort_direction``,
    ``track_activity``). A ``status`` change is transition-validated; a
    move to ``rejected`` requires either the ``rejected_by_decision``
    key (atomic edge + flip, PI-153 §3.4) or a pre-existing
    ``rejected_by_decision`` edge. A ``kind`` of ``None`` or an empty
    string clears the field; otherwise the value must be a member of
    :data:`ENTITY_KINDS`.
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
        name = _require_nonempty(fields["name"], field="entity_name")
        if name.lower() != row.entity_name.lower():
            _reject_duplicate_name(
                session, name, exclude_identifier=identifier
            )
        row.entity_name = name
    if "description" in fields:
        row.entity_description = _require_nonempty(
            fields["description"], field="entity_description"
        )
    if "notes" in fields:
        row.entity_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.entity_status:
            _check_transition(row.entity_status, status)
            if status == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
            row.entity_status = status
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.entity_status,
        )
    if "kind" in fields:
        row.entity_kind = _coerce_kind(fields["kind"])
    if "default_sort_field" in fields:
        row.entity_default_sort_field = _coerce_sort_field(
            fields["default_sort_field"]
        )
    if "default_sort_direction" in fields:
        row.entity_default_sort_direction = _coerce_sort_direction(
            fields["default_sort_direction"]
        )
    if "track_activity" in fields:
        row.entity_track_activity = bool(fields["track_activity"])
    if "tracks_activities" in fields:
        row.entity_tracks_activities = bool(fields["tracks_activities"])
    if "text_filter_fields" in fields:
        row.entity_text_filter_fields = _coerce_text_filter_fields(
            fields["text_filter_fields"]
        )
    if "full_text_search" in fields:
        row.entity_full_text_search = bool(fields["full_text_search"])
    if "full_text_search_min_length" in fields:
        row.entity_full_text_search_min_length = _coerce_fts_min_length(
            fields["full_text_search_min_length"]
        )
    # REL-025 / REQ-364: source display labels (singular + plural). A blank
    # value clears the label; otherwise it is stored verbatim.
    if "label" in fields:
        v = fields["label"]
        row.entity_label = v.strip() if isinstance(v, str) and v.strip() else None
    if "label_plural" in fields:
        v = fields["label_plural"]
        row.entity_label_plural = v.strip() if isinstance(v, str) and v.strip() else None

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
    _flag_design_staleness(session, identifier, before, after)
    return after


def delete_entity(session: Session, identifier: str) -> dict:
    """Soft-delete: set ``entity_deleted_at`` to now.

    Idempotent — DELETE on an already-soft-deleted row is a no-op that
    returns the record unchanged. Outbound ``entity_scopes_to_domain``
    references are NOT cascade-deleted (``entity.md`` section 3.4.6):
    this function never touches the ``refs`` table.
    """
    row = _get_row(session, identifier)
    if row.entity_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.entity_deleted_at = datetime.now(UTC)
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


def restore_entity(session: Session, identifier: str) -> dict:
    """Clear ``entity_deleted_at``. Raises if the row is not soft-deleted."""
    row = _get_row(session, identifier)
    if row.entity_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_deleted_at",
                    "not_deleted",
                    "entity is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.entity_deleted_at = None
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
