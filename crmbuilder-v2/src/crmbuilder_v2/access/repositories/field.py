"""Field repository — the sixth methodology entity type (v0.5+, PI-004
first slice).

Per ``methodology-schema-specs/field.md``. The eight module-level
functions back the ``/fields`` REST endpoints and the desktop panel:

* :func:`list_fields` / :func:`get_field` — reads. ``list_fields``
  supports an ``entity_identifier=ENT-NNN`` filter per spec §3.5.5
  that joins the ``refs`` table to surface only fields whose live
  ``field_belongs_to_entity`` edge points to the supplied entity.
* :func:`create_field` — atomic insert of the field row PLUS its
  outgoing ``field_belongs_to_entity`` edge in one transaction per
  spec §3.5.4. Identifier is server-assigned by default (PI-002).
* :func:`update_field` — full replace (PUT). Does NOT re-parent — that
  requires explicit DELETE-then-POST edge management per spec §3.5.4
  (PI-053 tracks the convenience endpoint).
* :func:`patch_field` — partial update (PATCH). Same no-reparent rule.
* :func:`delete_field` / :func:`restore_field` — soft-delete round-trip
  that atomically detaches/reattaches the parent-entity edge per spec
  §3.4.6. The stash column
  ``field_previous_parent_entity_identifier`` carries the
  previously-attached entity identifier across the soft-deleted state.
* :func:`next_field_identifier` — the ``FLD-NNN`` allocator helper.

Validation posture (``field.md`` §3.5): identifier-format,
per-entity-scoped case-insensitive name-uniqueness, status-enum,
type-enum, parent-entity-exists, and PUT identifier/path mismatches
raise :class:`UnprocessableError` (HTTP 422); disallowed status
transitions raise :class:`StatusTransitionError` (HTTP 422 with the
dedicated body shape). Missing fields raise :class:`NotFoundError`
(404); an explicit-identifier collision on create raises
:class:`ConflictError` (409).

Two cross-spec deviations from the cross-spec defaults:

* **Atomic POST.** The ``create_field`` signature requires a
  ``field_belongs_to_entity_identifier`` kwarg; the row and the edge
  land in the same enclosing transaction. The decomposed alternative
  (POST row, then POST edge) was rejected to avoid a transient
  invalid state per spec §3.5.4.
* **Per-entity name uniqueness.** The same ``field_name`` value may
  appear on multiple parent entities (``Contact.status`` and
  ``Mentor.status`` are both valid). Uniqueness is enforced on the
  ``(parent_entity_identifier, lower(field_name))`` pair via a refs
  lookup at validate-time. Spec §3.2.3.
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
from crmbuilder_v2.access.models import Entity, Field, Reference
from crmbuilder_v2.access.repositories import _rejection
from crmbuilder_v2.access.vocab import (
    FIELD_STATUS_TRANSITIONS,
    FIELD_STATUSES,
    FIELD_TYPES,
)

_ENTITY_TYPE = "field"
_IDENTIFIER_PREFIX = "FLD"
_IDENTIFIER_RE = re.compile(r"^FLD-\d{3}$")

# Upper bound on identifier-collision retries inside
# :func:`_insert_with_autoassign`. Far above any plausible concurrent
# burst; exhausting it indicates a genuine fault, surfaced as a 409.
_MAX_AUTOASSIGN_ATTEMPTS = 50

# Fields accepted by :func:`patch_field`. The identifier, timestamps,
# and the parent-entity stash column are not patchable. Re-parenting
# is not allowed via PATCH (spec §3.5.4); use explicit edge management.
_PATCHABLE_FIELDS = frozenset(
    {"name", "description", "type", "required", "notes", "status"}
)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "field_identifier",
                    "invalid_format",
                    r"must match ^FLD-\d{3}$ (e.g. FLD-001)",
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
    if status not in FIELD_STATUSES:
        raise UnprocessableError(
            [
                FieldError(
                    "field_status",
                    "invalid_value",
                    f"must be one of {sorted(FIELD_STATUSES)}",
                )
            ]
        )
    return status  # type: ignore[return-value]


def _require_type(field_type: object) -> str:
    if field_type not in FIELD_TYPES:
        raise UnprocessableError(
            [
                FieldError(
                    "field_type",
                    "invalid_value",
                    f"must be one of {sorted(FIELD_TYPES)}",
                )
            ]
        )
    return field_type  # type: ignore[return-value]


def _check_transition(current: str, requested: str) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set per
    :data:`FIELD_STATUS_TRANSITIONS`. Per ``field.md`` §3.4.3 this
    check consults only the field's own status — never the status of
    the parent entity.
    """
    if requested == current:
        return
    if requested not in FIELD_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _require_live_entity(session: Session, entity_identifier: str) -> Entity:
    """Resolve the parent entity, surfacing the spec §3.5.4 422 shapes.

    Returns the live ``Entity`` row. Missing entity raises with reason
    ``not_found``; soft-deleted entity raises with reason
    ``soft_deleted``.
    """
    if not isinstance(entity_identifier, str) or not entity_identifier.strip():
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "missing_parent_entity",
                    "field_belongs_to_entity_identifier is required",
                )
            ]
        )
    parent = get_by_identifier(session, Entity, Entity.entity_identifier, entity_identifier)
    if parent is None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "invalid_parent_entity",
                    f"parent entity {entity_identifier!r} not found",
                )
            ]
        )
    if parent.entity_deleted_at is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_belongs_to_entity_identifier",
                    "invalid_parent_entity",
                    f"parent entity {entity_identifier!r} is soft-deleted",
                )
            ]
        )
    return parent


def _resolve_parent_entity_identifier(
    session: Session, field_identifier: str
) -> str | None:
    """Return the field's live parent-entity identifier or ``None``.

    Looks up the live ``field_belongs_to_entity`` edge for the supplied
    field. Returns ``None`` if no such edge exists (the soft-deleted
    field state, where the edge has been hard-deleted and the parent
    is stashed in ``field_previous_parent_entity_identifier`` instead).
    """
    row = session.scalar(
        select(Reference).where(
            Reference.source_type == "field",
            Reference.source_id == field_identifier,
            Reference.target_type == "entity",
            Reference.relationship_kind == "field_belongs_to_entity",
        )
    )
    return row.target_id if row is not None else None


def _reject_duplicate_name_within_entity(
    session: Session,
    name: str,
    entity_identifier: str,
    *,
    exclude_identifier: str | None = None,
) -> None:
    """Reject a case-insensitive name collision *within the parent entity*.

    Per ``field.md`` §3.2.3: uniqueness is on
    ``(parent_entity_identifier, lower(field_name))``, not on
    ``field_name`` alone. The parent entity is resolved via the
    ``field_belongs_to_entity`` edge in the ``refs`` table — this
    function queries it directly rather than holding an FK column.
    """
    sibling_ids_stmt = select(Reference.source_id).where(
        Reference.source_type == "field",
        Reference.target_type == "entity",
        Reference.target_id == entity_identifier,
        Reference.relationship_kind == "field_belongs_to_entity",
    )
    stmt = select(Field).where(
        Field.field_identifier.in_(sibling_ids_stmt),
        func.lower(Field.field_name) == name.lower(),
        Field.field_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Field.field_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_name",
                    "duplicate",
                    f"a field named {name!r} already exists on "
                    f"entity {entity_identifier}",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Field:
    """Return the ORM row (including soft-deleted) or raise NotFoundError."""
    row = get_by_identifier(session, Field, Field.field_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    """Return the next ``FLD-NNN`` after ``identifier`` (collision retry)."""
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_fields(
    session: Session,
    *,
    entity_identifier: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return all fields ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    When ``entity_identifier`` is supplied (per spec §3.5.5), the
    result is filtered to fields whose live
    ``field_belongs_to_entity`` edge points to the supplied entity.
    Soft-deleted fields are excluded from the entity-filter view
    regardless of ``include_deleted`` because their edge has been
    detached; callers wanting deleted rows on a per-entity basis must
    use the ``field_previous_parent_entity_identifier`` column.
    """
    stmt = select(Field).order_by(Field.field_identifier)
    if entity_identifier is not None:
        sibling_ids_stmt = select(Reference.source_id).where(
            Reference.source_type == "field",
            Reference.target_type == "entity",
            Reference.target_id == entity_identifier,
            Reference.relationship_kind == "field_belongs_to_entity",
        )
        stmt = stmt.where(Field.field_identifier.in_(sibling_ids_stmt))
        # When filtering by entity_identifier, soft-deleted fields have
        # no live edge so they're naturally excluded by the join.
        # include_deleted is ignored in this branch.
    else:
        if not include_deleted:
            stmt = stmt.where(Field.field_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_field(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single field by identifier, or ``None`` if not visible.

    A soft-deleted row reads as ``None`` unless ``include_deleted`` is
    True — the REST layer translates ``None`` to HTTP 404.
    """
    row = get_by_identifier(session, Field, Field.field_identifier, identifier)
    if row is None:
        return None
    if row.field_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_field_identifier(session: Session) -> str:
    """Return the next available ``FLD-NNN`` identifier.

    Scans every row including soft-deleted ones so a retired
    identifier is never reused.
    """
    identifiers = session.scalars(select(Field.field_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_field_row(
    identifier: str,
    name: str,
    description: str,
    field_type: str,
    required: bool,
    notes: str | None,
    status: str,
) -> Field:
    return Field(
        field_identifier=identifier,
        field_name=name,
        field_description=description,
        field_type=field_type,
        field_required=required,
        field_notes=notes,
        field_status=status,
    )


def _insert_with_autoassign(
    session: Session,
    name: str,
    description: str,
    field_type: str,
    required: bool,
    notes: str | None,
    status: str,
) -> Field:
    """Insert a field with a server-assigned identifier, collision-safe.

    Computes the next ``FLD-NNN`` and attempts the INSERT inside a
    SAVEPOINT. A concurrent transaction that committed the same
    identifier first raises ``IntegrityError`` on flush; the savepoint
    rolls that INSERT back, the candidate is incremented, and the
    attempt repeats.
    """
    candidate = next_field_identifier(session)
    last_error: IntegrityError | None = None
    for _attempt in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_field_row(
            candidate, name, description, field_type, required, notes, status
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
        "could not assign a unique field identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_field(
    session: Session,
    *,
    field_belongs_to_entity_identifier: str,
    name: str,
    description: str,
    type: str,
    required: bool | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a field atomically with its parent-entity edge.

    Per ``field.md`` §3.5.4: the field row, the
    ``field_belongs_to_entity`` edge to the supplied parent entity,
    and the change-log emit all land in one transactional scope.

    Validation order:

    1. ``name`` / ``description`` non-empty.
    2. ``type`` in :data:`FIELD_TYPES`.
    3. ``status`` defaults to ``candidate``, validated against
       :data:`FIELD_STATUSES`.
    4. ``required`` defaults to ``False``.
    5. Parent entity must exist and be live (surfaces the spec
       ``missing_parent_entity`` / ``invalid_parent_entity`` shapes).
    6. ``name`` collision check scoped to the parent entity's siblings.
    7. Insert the field row (server-assigned id if ``identifier`` is
       ``None``).
    8. Create the ``field_belongs_to_entity`` edge via the references
       repository (re-imported locally to avoid an import cycle).
    """
    name = _require_nonempty(name, field="field_name")
    description = _require_nonempty(description, field="field_description")
    field_type = _require_type(type)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    if required is None:
        required = False
    required = bool(required)

    _require_live_entity(session, field_belongs_to_entity_identifier)
    _reject_duplicate_name_within_entity(
        session, name, field_belongs_to_entity_identifier
    )

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, description, field_type, required, notes, status
        )
    else:
        _require_identifier_format(identifier)
        if get_by_identifier(session, Field, Field.field_identifier, identifier) is not None:
            raise ConflictError(f"field {identifier!r} already exists")
        row = _new_field_row(
            identifier, name, description, field_type, required, notes, status
        )
        session.add(row)
        session.flush()

    # Create the mandatory parent-entity edge in the same transaction.
    # Imported locally to avoid a module-load cycle (references.py does
    # not import this module, but this module is loaded before the
    # references module during repository package wiring).
    from crmbuilder_v2.access.repositories import references

    references.create(
        session,
        source_type="field",
        source_id=row.field_identifier,
        target_type="entity",
        target_id=field_belongs_to_entity_identifier,
        relationship="field_belongs_to_entity",
    )

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.field_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_field(
    session: Session,
    identifier: str,
    *,
    field_identifier: str | None = None,
    name: str,
    description: str,
    type: str,
    required: bool,
    notes: str | None = None,
    status: str,
    rejected_by_decision: str | None = None,
) -> dict:
    """Full-replace update (PUT).

    ``field_identifier`` (the identifier echoed in the request body)
    must match the path ``identifier`` — a mismatch raises
    :class:`UnprocessableError`. ``name`` / ``description`` / ``type``
    / ``required`` / ``status`` are required; ``notes`` is replaced
    wholesale (``None`` clears). A ``status`` change is
    transition-validated. The parent entity cannot be changed via PUT
    (spec §3.5.4).
    """
    row = _get_row(session, identifier)
    if field_identifier is not None and field_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "field_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="field_name")
    description = _require_nonempty(description, field="field_description")
    field_type = _require_type(type)
    status_v = _require_status(status)
    if status_v != row.field_status:
        _check_transition(row.field_status, status_v)
        if status_v == "rejected":
            _rejection.enforce_rejected_status(
                session,
                source_type=_ENTITY_TYPE,
                source_identifier=identifier,
                decision_identifier=rejected_by_decision,
            )
            rejected_by_decision = None
        row.field_status = status_v
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.field_status,
        )

    if name.lower() != row.field_name.lower():
        parent = _resolve_parent_entity_identifier(session, identifier)
        if parent is not None:
            _reject_duplicate_name_within_entity(
                session, name, parent, exclude_identifier=identifier
            )

    row.field_name = name
    row.field_description = description
    row.field_type = field_type
    row.field_required = bool(required)
    row.field_notes = notes
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


def patch_field(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    Recognised keys: ``name``, ``description``, ``type``, ``required``,
    ``notes``, ``status``, ``rejected_by_decision``. A ``status`` change
    is transition-validated; a move to ``rejected`` requires either the
    ``rejected_by_decision`` key (atomic edge + flip, PI-153 §3.4) or a
    pre-existing ``rejected_by_decision`` edge. Parent-entity
    reparenting is not allowed via PATCH (spec §3.5.4).
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
        name = _require_nonempty(fields["name"], field="field_name")
        if name.lower() != row.field_name.lower():
            parent = _resolve_parent_entity_identifier(session, identifier)
            if parent is not None:
                _reject_duplicate_name_within_entity(
                    session, name, parent, exclude_identifier=identifier
                )
        row.field_name = name
    if "description" in fields:
        row.field_description = _require_nonempty(
            fields["description"], field="field_description"
        )
    if "type" in fields:
        row.field_type = _require_type(fields["type"])
    if "required" in fields:
        row.field_required = bool(fields["required"])
    if "notes" in fields:
        row.field_notes = fields["notes"]
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.field_status:
            _check_transition(row.field_status, status_v)
            if status_v == "rejected":
                _rejection.enforce_rejected_status(
                    session,
                    source_type=_ENTITY_TYPE,
                    source_identifier=identifier,
                    decision_identifier=rejected_by_decision,
                )
                rejected_by_decision = None
            row.field_status = status_v
    if rejected_by_decision is not None:
        _rejection.attach_decision(
            session,
            source_type=_ENTITY_TYPE,
            source_identifier=identifier,
            decision_identifier=rejected_by_decision,
            current_status=row.field_status,
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


def delete_field(session: Session, identifier: str) -> dict:
    """Soft-delete the field AND detach the parent-entity edge atomically.

    Per ``field.md`` §3.4.6 both effects must land in the same
    transaction. Implementation:

    1. Set ``field_deleted_at`` to now.
    2. Stash the parent entity's identifier in
       ``field_previous_parent_entity_identifier``.
    3. Hard-delete the ``field_belongs_to_entity`` edge via the
       references repository's ``_skip_cardinality_check=True`` path
       (the cardinality guard would otherwise reject deleting the
       only live edge of what was, until step 1, a live field).

    Idempotent — DELETE on an already-soft-deleted row is a no-op
    that returns the record unchanged.
    """
    row = _get_row(session, identifier)
    if row.field_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)

    parent = _resolve_parent_entity_identifier(session, identifier)
    row.field_deleted_at = datetime.now(UTC)
    row.field_previous_parent_entity_identifier = parent
    session.flush()

    if parent is not None:
        from crmbuilder_v2.access.repositories import references

        references.delete(
            session,
            source_type="field",
            source_id=identifier,
            target_type="entity",
            target_id=parent,
            relationship="field_belongs_to_entity",
            _skip_cardinality_check=True,
        )

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


def restore_field(session: Session, identifier: str) -> dict:
    """Clear ``field_deleted_at`` AND restore the parent-entity edge.

    Reads the stash column to find the previously-attached parent;
    validates the parent is still live (surfaces the spec
    ``parent_entity_soft_deleted`` 422 if not); recreates the edge
    atomically with clearing ``field_deleted_at`` and the stash.
    Raises :class:`UnprocessableError` if the row is not soft-deleted.
    """
    row = _get_row(session, identifier)
    if row.field_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "field_deleted_at",
                    "not_deleted",
                    "field is not soft-deleted",
                )
            ]
        )

    previous_parent = row.field_previous_parent_entity_identifier
    if previous_parent is not None:
        parent = get_by_identifier(session, Entity, Entity.entity_identifier, previous_parent)
        if parent is None:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_belongs_to_entity_identifier",
                        "parent_entity_not_found",
                        f"previously-attached entity {previous_parent!r} no "
                        "longer exists; cannot restore",
                    )
                ]
            )
        if parent.entity_deleted_at is not None:
            raise UnprocessableError(
                [
                    FieldError(
                        "field_belongs_to_entity_identifier",
                        "parent_entity_soft_deleted",
                        f"previously-attached entity {previous_parent!r} is "
                        "soft-deleted; restore the parent entity first",
                    )
                ]
            )

    before = to_dict(row)
    row.field_deleted_at = None
    row.field_previous_parent_entity_identifier = None
    session.flush()

    if previous_parent is not None:
        from crmbuilder_v2.access.repositories import references

        references.create(
            session,
            source_type="field",
            source_id=identifier,
            target_type="entity",
            target_id=previous_parent,
            relationship="field_belongs_to_entity",
        )

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
