"""View repository — condition-carrying design record (PRJ-025 PI-189 slice 2).

Per ``engine-neutral-design-model-and-adapters.md`` §8. A ``view`` (``VEW-NNN``)
is the engine-neutral description of a list view: a non-empty ordered list of
column field references, an optional neutral-condition filter, and a default
sort. The module-level functions back the ``/views`` REST endpoints and any
access-layer caller (the adapter, MCP tools):

* :func:`list_views` / :func:`get_view` — reads. ``list`` takes an optional
  ``entity`` filter on the listed-entity column.
* :func:`create_view` — insert with a server-assigned (or explicit)
  identifier. ``entity`` (``ENT-NNN``) is validated live; ``columns`` is a
  non-empty list of field references; ``filter`` (when present) is a valid
  neutral condition AST; ``sort_direction`` (when present) is in
  ``ENTITY_SORT_DIRECTIONS``.
* :func:`update_view` / :func:`patch_view` — full / partial update.
* :func:`delete_view` / :func:`restore_view` — soft-delete round-trip.
* :func:`next_view_identifier` — the ``VEW-NNN`` allocator helper.

Validation posture mirrors the other design records — bad enum / format /
condition / empty-columns / dead-entity raise :class:`UnprocessableError`
(422); disallowed status transitions raise :class:`StatusTransitionError`
(422); a missing record raises :class:`NotFoundError` (404); an
explicit-identifier collision raises :class:`ConflictError` (409).
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
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.conditions import ConditionError, validate_condition
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Entity, View
from crmbuilder_v2.access.vocab import (
    ENTITY_SORT_DIRECTIONS,
    VIEW_STATUS_TRANSITIONS,
    VIEW_STATUSES,
)

_ENTITY_TYPE = "view"
_IDENTIFIER_PREFIX = "VEW"
_IDENTIFIER_RE = re.compile(r"^VEW-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "entity",
        "columns",
        "filter",
        "sort_field",
        "sort_direction",
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
            "view_identifier",
            "invalid_format",
            r"must match ^VEW-\d{3}$ (e.g. VEW-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_status(status: object) -> str:
    if status not in VIEW_STATUSES:
        _fail(
            "view_status",
            "invalid_value",
            f"must be one of {sorted(VIEW_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_columns(columns: object) -> list:
    if not isinstance(columns, list) or not columns:
        _fail(
            "view_columns",
            "invalid_value",
            "must be a non-empty list of field references",
        )
    for index, col in enumerate(columns):  # type: ignore[arg-type]
        if not isinstance(col, str) or not col.strip():
            _fail(
                "view_columns",
                "invalid_value",
                f"column[{index}] must be a non-empty field reference string",
            )
    return columns  # type: ignore[return-value]


def _optional_filter(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(
            "view_filter",
            "invalid_value",
            "must be a neutral condition object or null",
        )
    try:
        validate_condition(value)
    except ConditionError as exc:
        _fail("view_filter", "invalid_condition", str(exc))
    return value  # type: ignore[return-value]


def _optional_sort_direction(value: object) -> str | None:
    if value is None:
        return None
    if value not in ENTITY_SORT_DIRECTIONS:
        _fail(
            "view_sort_direction",
            "invalid_value",
            f"must be one of {sorted(ENTITY_SORT_DIRECTIONS)} or null",
        )
    return value  # type: ignore[return-value]


def _require_live_entity(value: object, *, session: Session) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("view_entity", "missing_entity", "view_entity is required")
    identifier = value.strip()  # type: ignore[union-attr]
    row = get_by_identifier(
        session, Entity, Entity.entity_identifier, identifier
    )
    if row is None:
        _fail(
            "view_entity",
            "invalid_entity",
            f"entity {identifier!r} not found",
        )
    if row.entity_deleted_at is not None:
        _fail(
            "view_entity",
            "invalid_entity",
            f"entity {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in VIEW_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> View:
    row = get_by_identifier(session, View, View.view_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_views(
    session: Session,
    *,
    entity: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return views ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``entity`` filters on the listed-entity column.
    """
    stmt = select(View).order_by(View.view_identifier)
    if entity is not None:
        stmt = stmt.where(View.view_entity == entity)
    if not include_deleted:
        stmt = stmt.where(View.view_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_view(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single view by identifier, or ``None`` if not visible."""
    row = get_by_identifier(session, View, View.view_identifier, identifier)
    if row is None:
        return None
    if row.view_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_view_identifier(session: Session) -> str:
    """Return the next available ``VEW-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(select(View.view_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    entity: str,
    columns: list,
    filter: dict | None,
    sort_field: str | None,
    sort_direction: str | None,
    description: str | None,
    notes: str | None,
    status: str,
) -> View:
    return View(
        view_identifier=identifier,
        view_name=name,
        view_entity=entity,
        view_columns=columns,
        view_filter=filter,
        view_sort_field=sort_field,
        view_sort_direction=sort_direction,
        view_description=description,
        view_notes=notes,
        view_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> View:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_view_identifier(session)
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
        "could not assign a unique view identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_view(
    session: Session,
    *,
    name: str,
    entity: str,
    columns: list,
    filter: dict | None = None,
    sort_field: str | None = None,
    sort_direction: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a view.

    Validation order: ``name`` non-empty; ``status`` defaults to ``candidate``;
    ``columns`` a non-empty list of field references; ``filter`` a valid
    neutral AST when present; ``sort_direction`` in vocab when present; the
    listed ``entity`` exists and is live; then insert.
    """
    name = _require_nonempty(name, field="view_name")
    if status is None:
        status = "candidate"
    status = _require_status(status)
    columns = _require_columns(columns)
    filter = _optional_filter(filter)
    sort_field = _optional_text(sort_field, field="view_sort_field")
    sort_direction = _optional_sort_direction(sort_direction)
    description = _optional_text(description, field="view_description")
    notes = _optional_text(notes, field="view_notes")
    entity = _require_live_entity(entity, session=session)

    column_values = {
        "name": name,
        "entity": entity,
        "columns": columns,
        "filter": filter,
        "sort_field": sort_field,
        "sort_direction": sort_direction,
        "description": description,
        "notes": notes,
        "status": status,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **column_values)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(session, View, View.view_identifier, identifier)
            is not None
        ):
            raise ConflictError(f"view {identifier!r} already exists")
        row = _new_row(identifier, **column_values)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.view_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_view(
    session: Session,
    identifier: str,
    *,
    view_identifier: str | None = None,
    name: str,
    entity: str,
    columns: list,
    filter: dict | None = None,
    sort_field: str | None = None,
    sort_direction: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if view_identifier is not None and view_identifier != identifier:
        _fail(
            "view_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="view_name")
    columns = _require_columns(columns)
    filter = _optional_filter(filter)
    sort_field = _optional_text(sort_field, field="view_sort_field")
    sort_direction = _optional_sort_direction(sort_direction)
    description = _optional_text(description, field="view_description")
    notes = _optional_text(notes, field="view_notes")
    entity = _require_live_entity(entity, session=session)

    status_v = _require_status(status)
    if status_v != row.view_status:
        _check_transition(row.view_status, status_v)
        row.view_status = status_v

    row.view_name = name
    row.view_entity = entity
    row.view_columns = columns
    row.view_filter = filter
    row.view_sort_field = sort_field
    row.view_sort_direction = sort_direction
    row.view_description = description
    row.view_notes = notes
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


def patch_view(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched."""
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
        row.view_name = _require_nonempty(fields["name"], field="view_name")
    if "entity" in fields:
        row.view_entity = _require_live_entity(
            fields["entity"], session=session
        )
    if "columns" in fields:
        row.view_columns = _require_columns(fields["columns"])
    if "filter" in fields:
        row.view_filter = _optional_filter(fields["filter"])
    if "sort_field" in fields:
        row.view_sort_field = _optional_text(
            fields["sort_field"], field="view_sort_field"
        )
    if "sort_direction" in fields:
        row.view_sort_direction = _optional_sort_direction(
            fields["sort_direction"]
        )
    if "description" in fields:
        row.view_description = _optional_text(
            fields["description"], field="view_description"
        )
    if "notes" in fields:
        row.view_notes = _optional_text(fields["notes"], field="view_notes")
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.view_status:
            _check_transition(row.view_status, status_v)
            row.view_status = status_v

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


def delete_view(session: Session, identifier: str) -> dict:
    """Soft-delete the view. Idempotent."""
    row = _get_row(session, identifier)
    if row.view_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.view_deleted_at = datetime.now(UTC)
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


def restore_view(session: Session, identifier: str) -> dict:
    """Clear ``view_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.view_deleted_at is None:
        _fail("view_deleted_at", "not_deleted", "view is not soft-deleted")
    before = to_dict(row)
    row.view_deleted_at = None
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
