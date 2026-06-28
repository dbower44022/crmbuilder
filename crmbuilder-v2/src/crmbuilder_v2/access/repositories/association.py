"""Association repository — composite design record (PRJ-025 PI-189 slice 1).

Per ``engine-neutral-design-model-and-adapters.md`` §8. An ``association``
(``ASN-NNN``) is the engine-neutral description of an entity-to-entity link;
it is the construct the EspoCRM adapter renders into the ``relationships:``
block. The module-level functions back the ``/associations`` REST endpoints
and any access-layer caller (the adapter, MCP tools):

* :func:`list_associations` / :func:`get_association` — reads. ``list`` takes
  optional ``source_entity`` / ``target_entity`` filters on the columns.
* :func:`create_association` — insert with a server-assigned (or explicit)
  identifier. Both endpoints are validated to exist and be live in the
  active engagement; the association *is* the relationship, so the endpoints
  live as ``ENT-NNN`` columns rather than ``refs`` edges.
* :func:`update_association` / :func:`patch_association` — full / partial
  update. Endpoints are re-validated when changed; a status change is
  transition-validated.
* :func:`delete_association` / :func:`restore_association` — soft-delete
  round-trip (plain row-level stamp; no edges to detach).
* :func:`next_association_identifier` — the ``ASN-NNN`` allocator helper.

Validation posture: identifier-format, cardinality-enum, status-enum, and a
PUT identifier/path mismatch raise :class:`UnprocessableError` (HTTP 422); a
non-existent or soft-deleted endpoint entity raises :class:`UnprocessableError`
(422); disallowed status transitions raise :class:`StatusTransitionError`
(422); a missing record raises :class:`NotFoundError` (404); an
explicit-identifier collision on create raises :class:`ConflictError` (409).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
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
from crmbuilder_v2.access.models import Association, Entity
from crmbuilder_v2.access.vocab import (
    ASSOCIATION_CARDINALITIES,
    ASSOCIATION_STATUS_TRANSITIONS,
    ASSOCIATION_STATUSES,
)

_ENTITY_TYPE = "association"
_IDENTIFIER_PREFIX = "ASN"
_IDENTIFIER_RE = re.compile(r"^ASN-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign` (the field.py posture).
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_association`. The identifier and timestamps
# are server-owned and not patchable.
_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "source_entity",
        "target_entity",
        "cardinality",
        "source_role",
        "target_role",
        "description",
        "notes",
        "status",
    }
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "association_identifier",
            "invalid_format",
            r"must match ^ASN-\d{3}$ (e.g. ASN-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_cardinality(cardinality: object) -> str:
    if cardinality not in ASSOCIATION_CARDINALITIES:
        _fail(
            "association_cardinality",
            "invalid_value",
            f"must be one of {sorted(ASSOCIATION_CARDINALITIES)}",
        )
    return cardinality  # type: ignore[return-value]


def _require_status(status: object) -> str:
    if status not in ASSOCIATION_STATUSES:
        _fail(
            "association_status",
            "invalid_value",
            f"must be one of {sorted(ASSOCIATION_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_live_entity(value: object, *, field: str, session: Session) -> str:
    """Resolve an endpoint entity, requiring it to exist and be live."""
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_endpoint_entity", f"{field} is required")
    identifier = value.strip()  # type: ignore[union-attr]
    row = get_by_identifier(
        session, Entity, Entity.entity_identifier, identifier
    )
    if row is None:
        _fail(
            field,
            "invalid_endpoint_entity",
            f"entity {identifier!r} not found",
        )
    if row.entity_deleted_at is not None:  # type: ignore[union-attr]
        _fail(
            field,
            "invalid_endpoint_entity",
            f"entity {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move."""
    if requested == current:
        return
    if requested not in ASSOCIATION_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> Association:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(
        session, Association, Association.association_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_associations(
    session: Session,
    *,
    source_entity: str | None = None,
    target_entity: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return associations ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``source_entity`` / ``target_entity`` filter on the endpoint columns.
    """
    stmt = select(Association).order_by(Association.association_identifier)
    if source_entity is not None:
        stmt = stmt.where(
            Association.association_source_entity == source_entity
        )
    if target_entity is not None:
        stmt = stmt.where(
            Association.association_target_entity == target_entity
        )
    if not include_deleted:
        stmt = stmt.where(Association.association_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_association(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single association by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session, Association, Association.association_identifier, identifier
    )
    if row is None:
        return None
    if row.association_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_association_identifier(session: Session) -> str:
    """Return the next available ``ASN-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(Association.association_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    source_entity: str,
    target_entity: str,
    cardinality: str,
    source_role: str | None,
    target_role: str | None,
    description: str | None,
    notes: str | None,
    status: str,
) -> Association:
    return Association(
        association_identifier=identifier,
        association_name=name,
        association_source_entity=source_entity,
        association_target_entity=target_entity,
        association_cardinality=cardinality,
        association_source_role=source_role,
        association_target_role=target_role,
        association_description=description,
        association_notes=notes,
        association_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> Association:
    """Insert with a server-assigned identifier, SAVEPOINT-collision-safe."""
    candidate = next_association_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **columns)
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
        "could not assign a unique association identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_association(
    session: Session,
    *,
    name: str,
    source_entity: str,
    target_entity: str,
    cardinality: str,
    source_role: str | None = None,
    target_role: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create an association.

    Validation order: ``name`` non-empty; ``cardinality`` in vocab;
    ``status`` defaults to ``candidate``, validated against the vocab; both
    endpoint entities exist and are live; then insert (server-assigned id
    when ``identifier`` is ``None``).
    """
    name = _require_nonempty(name, field="association_name")
    cardinality = _require_cardinality(cardinality)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    source_role = _optional_text(source_role, field="association_source_role")
    target_role = _optional_text(target_role, field="association_target_role")
    description = _optional_text(
        description, field="association_description"
    )
    notes = _optional_text(notes, field="association_notes")

    source_entity = _require_live_entity(
        source_entity, field="association_source_entity", session=session
    )
    target_entity = _require_live_entity(
        target_entity, field="association_target_entity", session=session
    )

    columns = {
        "name": name,
        "source_entity": source_entity,
        "target_entity": target_entity,
        "cardinality": cardinality,
        "source_role": source_role,
        "target_role": target_role,
        "description": description,
        "notes": notes,
        "status": status,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                Association,
                Association.association_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"association {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.association_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def _flag_design_staleness(
    session: Session, identifier: str, before: dict, after: dict
) -> None:
    """PI-345 hook: an association cardinality/name change flips resolved
    association mappings targeting it stale. Lazy import avoids a repo cycle."""
    from crmbuilder_v2.access.repositories import design_staleness
    design_staleness.on_association_updated(session, identifier, before, after)


def update_association(
    session: Session,
    identifier: str,
    *,
    association_identifier: str | None = None,
    name: str,
    source_entity: str,
    target_entity: str,
    cardinality: str,
    source_role: str | None = None,
    target_role: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT).

    ``association_identifier`` (the identifier echoed in the body) must match
    the path ``identifier`` — a mismatch raises :class:`UnprocessableError`.
    Endpoints are re-validated; a status change is transition-validated.
    """
    row = _get_row(session, identifier)
    if (
        association_identifier is not None
        and association_identifier != identifier
    ):
        _fail(
            "association_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="association_name")
    cardinality = _require_cardinality(cardinality)
    source_role = _optional_text(source_role, field="association_source_role")
    target_role = _optional_text(target_role, field="association_target_role")
    description = _optional_text(
        description, field="association_description"
    )
    notes = _optional_text(notes, field="association_notes")
    source_entity = _require_live_entity(
        source_entity, field="association_source_entity", session=session
    )
    target_entity = _require_live_entity(
        target_entity, field="association_target_entity", session=session
    )

    status_v = _require_status(status)
    if status_v != row.association_status:
        _check_transition(row.association_status, status_v)
        row.association_status = status_v

    row.association_name = name
    row.association_source_entity = source_entity
    row.association_target_entity = target_entity
    row.association_cardinality = cardinality
    row.association_source_role = source_role
    row.association_target_role = target_role
    row.association_description = description
    row.association_notes = notes
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


def patch_association(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``source_entity``, ``target_entity``,
    ``cardinality``, ``source_role``, ``target_role``, ``description``,
    ``notes``, ``status``. A ``status`` change is transition-validated; an
    endpoint change is re-validated against live entities.
    """
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        _fail(
            "fields",
            "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}",
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    if "name" in fields:
        row.association_name = _require_nonempty(
            fields["name"], field="association_name"
        )
    if "source_entity" in fields:
        row.association_source_entity = _require_live_entity(
            fields["source_entity"],
            field="association_source_entity",
            session=session,
        )
    if "target_entity" in fields:
        row.association_target_entity = _require_live_entity(
            fields["target_entity"],
            field="association_target_entity",
            session=session,
        )
    if "cardinality" in fields:
        row.association_cardinality = _require_cardinality(
            fields["cardinality"]
        )
    if "source_role" in fields:
        row.association_source_role = _optional_text(
            fields["source_role"], field="association_source_role"
        )
    if "target_role" in fields:
        row.association_target_role = _optional_text(
            fields["target_role"], field="association_target_role"
        )
    if "description" in fields:
        row.association_description = _optional_text(
            fields["description"], field="association_description"
        )
    if "notes" in fields:
        row.association_notes = _optional_text(
            fields["notes"], field="association_notes"
        )
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.association_status:
            _check_transition(row.association_status, status_v)
            row.association_status = status_v

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


def delete_association(session: Session, identifier: str) -> dict:
    """Soft-delete the association. Idempotent."""
    row = _get_row(session, identifier)
    if row.association_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.association_deleted_at = datetime.now(UTC)
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


def restore_association(session: Session, identifier: str) -> dict:
    """Clear ``association_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.association_deleted_at is None:
        _fail(
            "association_deleted_at",
            "not_deleted",
            "association is not soft-deleted",
        )
    before = to_dict(row)
    row.association_deleted_at = None
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
