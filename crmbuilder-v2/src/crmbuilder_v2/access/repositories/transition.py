"""Transition repository — one allowed move of a status field in a process.

PI-471, implementing REQ-577 to REQ-586 (approved by DEC-1071). A
``transition`` (``TRN-NNN``) says that within one process a record may move
from one value of a status field — or from a set of its values, or from the
creation of the record — to one other value, and states who may make the move,
what must be recorded before it, and what happens automatically after it.

The module-level functions back the ``/transitions`` REST endpoints and any
access-layer caller (the render, the desktop, the connector tools):

* :func:`list_transitions` / :func:`get_transition` — reads. ``list`` takes an
  optional ``process`` filter and returns the process's transitions in
  ``transition_order`` (REQ-577).
* :func:`create_transition` — insert with a server-assigned (or explicit)
  identifier, under every check of REQ-578 to REQ-581.
* :func:`update_transition` / :func:`patch_transition` — full / partial update.
* :func:`delete_transition` / :func:`restore_transition` — soft-delete
  round-trip (REQ-582).
* :func:`reorder_transitions` — set the order of a process's transitions.
* :func:`incomplete_transitions` — the report of REQ-581: every transition
  whose consequences are still described in words rather than referenced as
  records.
* :func:`next_transition_identifier` — the ``TRN-NNN`` allocator helper.

The checks, each refused with the name of the check that failed (REQ-578):

``invalid_process``       the owning process does not exist or is soft-deleted
``invalid_field``         the status field does not exist or is soft-deleted
``field_not_a_choice``    the status field is not a choice field
``field_entity_untouched`` the status field's entity is not one the process
                          touches (no ``process_touches_entity`` edge)
``to_value_not_an_option`` the value moved to is not an option of the field
``from_value_not_an_option`` a value moved from is not an option of the field
``to_value_in_from_values`` the value moved to also appears among the values
                          moved from
``required_field_entity_untouched`` a required field belongs to an entity the
                          process does not touch
``invalid_consequence``   a consequence names a record type a transition may
                          not reference, or a record that is not there

Validation posture mirrors the other design records — a failed check raises
:class:`UnprocessableError` (422); a disallowed status move raises
:class:`StatusTransitionError` (422); a missing record raises
:class:`NotFoundError` (404); an explicit-identifier collision raises
:class:`ConflictError` (409).
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
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import (
    Automation,
    Field,
    FieldOption,
    MessageTemplate,
    Persona,
    Process,
    Reference,
    Transition,
    View,
)
from crmbuilder_v2.access.vocab import (
    TRANSITION_ACTOR_KINDS,
    TRANSITION_CONSEQUENCE_PREFIXES,
    TRANSITION_FROM_KINDS,
    TRANSITION_STATUS_TRANSITIONS,
    TRANSITION_STATUSES,
)

_ENTITY_TYPE = "transition"
_IDENTIFIER_PREFIX = "TRN"
_IDENTIFIER_RE = re.compile(r"^TRN-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

#: The field type a status field must have (REQ-578, "a choice field").
_CHOICE_FIELD_TYPE = "enum"

_PATCHABLE_FIELDS = frozenset(
    {
        "process",
        "field",
        "from_kind",
        "from_values",
        "to_value",
        "actor_kind",
        "actor_persona",
        "actor_occasion",
        "required_fields",
        "precondition",
        "consequences",
        "consequence_notes",
        "manual_follow_up",
        "order",
        "description",
        "notes",
        "status",
    }
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "transition_identifier",
            "invalid_format",
            r"must match ^TRN-\d{3}$ (e.g. TRN-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    text = value.strip()  # type: ignore[union-attr]
    return text or None


def _require_status(status: object) -> str:
    if status not in TRANSITION_STATUSES:
        _fail(
            "transition_status",
            "invalid_value",
            f"must be one of {sorted(TRANSITION_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _require_order(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("transition_order", "invalid_value", "must be an integer")
    if value < 0:  # type: ignore[operator]
        _fail("transition_order", "invalid_value", "must not be negative")
    return value  # type: ignore[return-value]


def _check_status_move(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in TRANSITION_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> Transition:
    row = get_by_identifier(
        session, Transition, Transition.transition_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# The checks of REQ-578 to REQ-581
# ---------------------------------------------------------------------------


def _require_live_process(value: object, *, session: Session) -> str:
    identifier = _require_nonempty(value, field="transition_process")
    row = get_by_identifier(
        session, Process, Process.process_identifier, identifier
    )
    if row is None:
        _fail(
            "transition_process",
            "invalid_process",
            f"process {identifier!r} not found",
        )
    if row.process_deleted_at is not None:
        _fail(
            "transition_process",
            "invalid_process",
            f"process {identifier!r} is soft-deleted",
        )
    return identifier


def _live_field(session: Session, identifier: str, *, field: str) -> Field:
    row = get_by_identifier(
        session, Field, Field.field_identifier, identifier
    )
    if row is None:
        _fail(field, "invalid_field", f"field {identifier!r} not found")
    if row.field_deleted_at is not None:
        _fail(field, "invalid_field", f"field {identifier!r} is soft-deleted")
    return row  # type: ignore[return-value]


def _entities_touched_by(session: Session, process: str) -> set[str]:
    """Return the ``ENT-NNN`` a process touches (``process_touches_entity``)."""
    rows = session.scalars(
        select(Reference.target_id).where(
            Reference.source_type == "process",
            Reference.source_id == process,
            Reference.target_type == "entity",
            Reference.relationship_kind == "process_touches_entity",
        )
    ).all()
    return set(rows)


def _parent_entity_of_field(session: Session, field_identifier: str) -> str | None:
    row = session.scalar(
        select(Reference).where(
            Reference.source_type == "field",
            Reference.source_id == field_identifier,
            Reference.target_type == "entity",
            Reference.relationship_kind == "field_belongs_to_entity",
        )
    )
    return row.target_id if row is not None else None


def _option_values(session: Session, field_identifier: str) -> list[str]:
    return list(
        session.scalars(
            select(FieldOption.option_value)
            .where(FieldOption.field_identifier == field_identifier)
            .order_by(FieldOption.option_order, FieldOption.id)
        ).all()
    )


def _require_status_field(
    value: object, *, session: Session, process: str
) -> tuple[str, list[str]]:
    """Check the status field and return its identifier and option values.

    REQ-578: the field must exist and be live, must be a choice field, and its
    entity must be one the process touches.
    """
    identifier = _require_nonempty(value, field="transition_field")
    row = _live_field(session, identifier, field="transition_field")
    if row.field_type != _CHOICE_FIELD_TYPE:
        _fail(
            "transition_field",
            "field_not_a_choice",
            f"field {identifier!r} is of type {row.field_type!r}; a status "
            f"field must be a choice field ({_CHOICE_FIELD_TYPE})",
        )
    entity = _parent_entity_of_field(session, identifier)
    touched = _entities_touched_by(session, process)
    if entity is None or entity not in touched:
        _fail(
            "transition_field",
            "field_entity_untouched",
            f"field {identifier!r} belongs to entity {entity!r}, which "
            f"process {process!r} does not touch",
        )
    return identifier, _option_values(session, identifier)


def _require_from_kind(value: object) -> str:
    if value not in TRANSITION_FROM_KINDS:
        _fail(
            "transition_from_kind",
            "invalid_value",
            f"must be one of {sorted(TRANSITION_FROM_KINDS)}",
        )
    return value  # type: ignore[return-value]


def _require_endpoints(
    *,
    from_kind: str,
    from_values: object,
    to_value: object,
    options: list[str],
) -> tuple[list[str], str]:
    """Check both ends of the move against the status field's option list."""
    to_text = _require_nonempty(to_value, field="transition_to_value")
    if to_text not in options:
        _fail(
            "transition_to_value",
            "to_value_not_an_option",
            f"{to_text!r} is not an option of the status field "
            f"(options: {options})",
        )

    if from_kind == "record_creation":
        if from_values not in (None, [], ()):
            _fail(
                "transition_from_values",
                "invalid_value",
                "must be empty when the move is from the creation of the "
                "record",
            )
        return [], to_text

    if not isinstance(from_values, list) or not from_values:
        _fail(
            "transition_from_values",
            "invalid_value",
            "must be a non-empty list of option values when the move is "
            "from values",
        )
    cleaned: list[str] = []
    for index, raw in enumerate(from_values):  # type: ignore[arg-type]
        if not isinstance(raw, str) or not raw.strip():
            _fail(
                "transition_from_values",
                "invalid_value",
                f"from value[{index}] must be a non-empty string",
            )
        value = raw.strip()
        if value not in options:
            _fail(
                "transition_from_values",
                "from_value_not_an_option",
                f"{value!r} is not an option of the status field "
                f"(options: {options})",
            )
        if value not in cleaned:
            cleaned.append(value)
    if to_text in cleaned:
        _fail(
            "transition_to_value",
            "to_value_in_from_values",
            f"{to_text!r} is both the value moved to and a value moved from",
        )
    return cleaned, to_text


def _require_actor(
    *,
    actor_kind: object,
    actor_persona: object,
    session: Session,
) -> tuple[str, str | None]:
    """Check who makes the move (REQ-579)."""
    if actor_kind not in TRANSITION_ACTOR_KINDS:
        _fail(
            "transition_actor_kind",
            "invalid_value",
            f"must be one of {sorted(TRANSITION_ACTOR_KINDS)}",
        )
    if actor_kind == "system":
        if actor_persona is not None:
            _fail(
                "transition_actor_persona",
                "forbidden_for_system_actor",
                "a system move does not name a persona",
            )
        return "system", None

    identifier = _require_nonempty(
        actor_persona, field="transition_actor_persona"
    )
    row = get_by_identifier(
        session, Persona, Persona.persona_identifier, identifier
    )
    if row is None:
        _fail(
            "transition_actor_persona",
            "invalid_persona",
            f"persona {identifier!r} not found",
        )
    if row.persona_deleted_at is not None:
        _fail(
            "transition_actor_persona",
            "invalid_persona",
            f"persona {identifier!r} is soft-deleted",
        )
    return "persona", identifier


def _require_required_fields(
    value: object, *, session: Session, process: str
) -> list[str]:
    """Check the fields that must hold a value before the move (REQ-580)."""
    if value is None:
        return []
    if not isinstance(value, list):
        _fail(
            "transition_required_fields",
            "invalid_value",
            "must be a list of FLD-NNN identifiers",
        )
    touched = _entities_touched_by(session, process)
    cleaned: list[str] = []
    for index, raw in enumerate(value):  # type: ignore[arg-type]
        if not isinstance(raw, str) or not raw.strip():
            _fail(
                "transition_required_fields",
                "invalid_value",
                f"required field[{index}] must be a non-empty string",
            )
        identifier = raw.strip()
        _live_field(session, identifier, field="transition_required_fields")
        entity = _parent_entity_of_field(session, identifier)
        if entity is None or entity not in touched:
            _fail(
                "transition_required_fields",
                "required_field_entity_untouched",
                f"field {identifier!r} belongs to entity {entity!r}, which "
                f"process {process!r} does not touch",
            )
        if identifier not in cleaned:
            cleaned.append(identifier)
    return cleaned


_CONSEQUENCE_LOOKUP = {
    "automation": (Automation, "automation_identifier", "automation_deleted_at"),
    "message_template": (
        MessageTemplate,
        "message_template_identifier",
        "message_template_deleted_at",
    ),
    "view": (View, "view_identifier", "view_deleted_at"),
    "transition": (
        Transition,
        "transition_identifier",
        "transition_deleted_at",
    ),
    "process": (Process, "process_identifier", "process_deleted_at"),
}


def _require_consequences(
    value: object, *, session: Session, own_identifier: str | None = None
) -> list[str]:
    """Check what happens automatically after the move (REQ-581).

    Each entry names an automation, a message template, a view, another
    transition or a process, by its identifier; the prefix says which, and the
    record must exist and be live.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        _fail(
            "transition_consequences",
            "invalid_value",
            "must be a list of record identifiers",
        )
    cleaned: list[str] = []
    for index, raw in enumerate(value):  # type: ignore[arg-type]
        if not isinstance(raw, str) or not raw.strip():
            _fail(
                "transition_consequences",
                "invalid_value",
                f"consequence[{index}] must be a non-empty string",
            )
        identifier = raw.strip()
        if own_identifier is not None and identifier == own_identifier:
            _fail(
                "transition_consequences",
                "invalid_consequence",
                f"transition {identifier!r} cannot follow automatically from "
                "itself",
            )
        prefix = identifier.split("-", 1)[0]
        record_type = TRANSITION_CONSEQUENCE_PREFIXES.get(prefix)
        if record_type is None:
            _fail(
                "transition_consequences",
                "invalid_consequence",
                f"{identifier!r} names no record type a transition may "
                "reference as a consequence; the prefixes allowed are "
                f"{sorted(TRANSITION_CONSEQUENCE_PREFIXES)}",
            )
        model, id_column, deleted_column = _CONSEQUENCE_LOOKUP[record_type]
        row = get_by_identifier(
            session, model, getattr(model, id_column), identifier
        )
        if row is None:
            _fail(
                "transition_consequences",
                "invalid_consequence",
                f"{record_type} {identifier!r} not found",
            )
        if getattr(row, deleted_column) is not None:
            _fail(
                "transition_consequences",
                "invalid_consequence",
                f"{record_type} {identifier!r} is soft-deleted",
            )
        if identifier not in cleaned:
            cleaned.append(identifier)
    return cleaned


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_transitions(
    session: Session,
    *,
    process: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return transitions in process order, then identifier.

    REQ-577: filtered by ``process`` this is the process's status lifecycle as
    one ordered list. Soft-deleted rows are excluded unless ``include_deleted``
    is True.
    """
    stmt = select(Transition).order_by(
        Transition.transition_process,
        Transition.transition_order,
        Transition.transition_identifier,
    )
    if process is not None:
        stmt = stmt.where(Transition.transition_process == process)
    if status is not None:
        stmt = stmt.where(Transition.transition_status == status)
    if not include_deleted:
        stmt = stmt.where(Transition.transition_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_transition(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single transition by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session, Transition, Transition.transition_identifier, identifier
    )
    if row is None:
        return None
    if row.transition_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def incomplete_transitions(
    session: Session, *, process: str | None = None
) -> list[dict]:
    """The incompleteness report of REQ-581.

    Every live transition whose automatic consequences are still described in
    words — ``transition_consequence_notes`` is non-empty — is named here,
    because a builder reading those words would have to make a choice the
    definition did not make. What a person does by hand afterwards
    (``transition_manual_follow_up``) is never counted as incomplete.

    Each entry carries the transition's identifier, its process, the move it
    describes and the words still owed a record.
    """
    rows = list_transitions(session, process=process)
    report = []
    for row in rows:
        words = row.get("transition_consequence_notes")
        if not words:
            continue
        report.append(
            {
                "transition_identifier": row["transition_identifier"],
                "transition_process": row["transition_process"],
                "transition_from_kind": row["transition_from_kind"],
                "transition_from_values": row["transition_from_values"],
                "transition_to_value": row["transition_to_value"],
                "transition_consequence_notes": words,
            }
        )
    return report


def next_transition_identifier(session: Session) -> str:
    """Return the next available ``TRN-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(Transition.transition_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier: str, **columns) -> Transition:
    return Transition(
        transition_identifier=identifier,
        **{f"transition_{key}": value for key, value in columns.items()},
    )


def _insert_with_autoassign(session: Session, **columns) -> Transition:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_transition_identifier(session)
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
        "could not assign a unique transition identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def _next_order_in_process(session: Session, process: str) -> int:
    existing = session.scalars(
        select(Transition.transition_order).where(
            Transition.transition_process == process,
            Transition.transition_deleted_at.is_(None),
        )
    ).all()
    return (max(existing) + 1) if existing else 0


def _validated_columns(
    session: Session,
    *,
    process: object,
    field: object,
    from_kind: object,
    from_values: object,
    to_value: object,
    actor_kind: object,
    actor_persona: object,
    actor_occasion: object,
    required_fields: object,
    precondition: object,
    consequences: object,
    consequence_notes: object,
    manual_follow_up: object,
    description: object,
    notes: object,
    own_identifier: str | None = None,
) -> dict:
    """Run every check of REQ-578 to REQ-581 and return the stored columns.

    ``own_identifier`` is the transition being written, when it already has
    one, so a move cannot name itself as its own automatic consequence.
    """
    process_id = _require_live_process(process, session=session)
    field_id, options = _require_status_field(
        field, session=session, process=process_id
    )
    kind = _require_from_kind(from_kind)
    values, to_text = _require_endpoints(
        from_kind=kind,
        from_values=from_values,
        to_value=to_value,
        options=options,
    )
    actor, persona = _require_actor(
        actor_kind=actor_kind, actor_persona=actor_persona, session=session
    )
    return {
        "process": process_id,
        "field": field_id,
        "from_kind": kind,
        "from_values": values,
        "to_value": to_text,
        "actor_kind": actor,
        "actor_persona": persona,
        "actor_occasion": _optional_text(
            actor_occasion, field="transition_actor_occasion"
        ),
        "required_fields": _require_required_fields(
            required_fields, session=session, process=process_id
        ),
        "precondition": _optional_text(
            precondition, field="transition_precondition"
        ),
        "consequences": _require_consequences(
            consequences, session=session, own_identifier=own_identifier
        ),
        "consequence_notes": _optional_text(
            consequence_notes, field="transition_consequence_notes"
        ),
        "manual_follow_up": _optional_text(
            manual_follow_up, field="transition_manual_follow_up"
        ),
        "description": _optional_text(
            description, field="transition_description"
        ),
        "notes": _optional_text(notes, field="transition_notes"),
    }


def create_transition(
    session: Session,
    *,
    process: str,
    field: str,
    to_value: str,
    from_kind: str = "values",
    from_values: list | None = None,
    actor_kind: str = "system",
    actor_persona: str | None = None,
    actor_occasion: str | None = None,
    required_fields: list | None = None,
    precondition: str | None = None,
    consequences: list | None = None,
    consequence_notes: str | None = None,
    manual_follow_up: str | None = None,
    order: int | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a transition on a process.

    Every check of REQ-578 to REQ-581 runs before the insert; a failure names
    the check. ``order`` defaults to the end of the process's list, ``status``
    to ``candidate``, and the identifier is server-assigned when omitted.
    """
    columns = _validated_columns(
        session,
        process=process,
        field=field,
        from_kind=from_kind,
        from_values=from_values,
        to_value=to_value,
        actor_kind=actor_kind,
        actor_persona=actor_persona,
        actor_occasion=actor_occasion,
        required_fields=required_fields,
        precondition=precondition,
        consequences=consequences,
        consequence_notes=consequence_notes,
        manual_follow_up=manual_follow_up,
        description=description,
        notes=notes,
        own_identifier=identifier,
    )
    columns["status"] = _require_status(
        "candidate" if status is None else status
    )
    columns["order"] = (
        _next_order_in_process(session, columns["process"])
        if order is None
        else _require_order(order)
    )

    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                Transition,
                Transition.transition_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"transition {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.transition_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_transition(
    session: Session,
    identifier: str,
    *,
    transition_identifier: str | None = None,
    process: str,
    field: str,
    to_value: str,
    status: str,
    from_kind: str = "values",
    from_values: list | None = None,
    actor_kind: str = "system",
    actor_persona: str | None = None,
    actor_occasion: str | None = None,
    required_fields: list | None = None,
    precondition: str | None = None,
    consequences: list | None = None,
    consequence_notes: str | None = None,
    manual_follow_up: str | None = None,
    order: int | None = None,
    description: str | None = None,
    notes: str | None = None,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if (
        transition_identifier is not None
        and transition_identifier != identifier
    ):
        _fail(
            "transition_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    columns = _validated_columns(
        session,
        process=process,
        field=field,
        from_kind=from_kind,
        from_values=from_values,
        to_value=to_value,
        actor_kind=actor_kind,
        actor_persona=actor_persona,
        actor_occasion=actor_occasion,
        required_fields=required_fields,
        precondition=precondition,
        consequences=consequences,
        consequence_notes=consequence_notes,
        manual_follow_up=manual_follow_up,
        description=description,
        notes=notes,
        own_identifier=identifier,
    )
    status_v = _require_status(status)
    if status_v != row.transition_status:
        _check_status_move(row.transition_status, status_v)
        row.transition_status = status_v
    if order is not None:
        row.transition_order = _require_order(order)
    for key, value in columns.items():
        setattr(row, f"transition_{key}", value)
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


def patch_transition(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    A change to either end of the move, to the status field, to the owning
    process or to a list of references re-runs the checks of REQ-578 to
    REQ-581 against the record as it will be after the change — not against
    the supplied keys alone, since the checks read both ends together.
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

    def current(key: str) -> object:
        return getattr(row, f"transition_{key}")

    merged = {
        key: fields.get(key, current(key))
        for key in (
            "process",
            "field",
            "from_kind",
            "from_values",
            "to_value",
            "actor_kind",
            "actor_persona",
            "actor_occasion",
            "required_fields",
            "precondition",
            "consequences",
            "consequence_notes",
            "manual_follow_up",
            "description",
            "notes",
        )
    }
    # A move that becomes a from-creation move drops its from values, and one
    # that stops being a from-creation move must be given them in the same
    # call — the endpoint check below says so if it was not.
    if fields.get("from_kind") == "record_creation" and "from_values" not in fields:
        merged["from_values"] = []
    if fields.get("actor_kind") == "system" and "actor_persona" not in fields:
        merged["actor_persona"] = None

    columns = _validated_columns(
        session, own_identifier=identifier, **merged  # type: ignore[arg-type]
    )
    for key, value in columns.items():
        setattr(row, f"transition_{key}", value)

    if "order" in fields:
        row.transition_order = _require_order(fields["order"])
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.transition_status:
            _check_status_move(row.transition_status, status_v)
            row.transition_status = status_v

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


def reorder_transitions(
    session: Session, process: str, ordered_identifiers: list
) -> list[dict]:
    """Set the order of a process's transitions (REQ-585).

    ``ordered_identifiers`` must name every live transition of the process
    exactly once; each row's ``transition_order`` becomes its position in the
    list. Anything else is refused rather than silently reordering part of the
    list.
    """
    rows = session.scalars(
        select(Transition).where(
            Transition.transition_process == process,
            Transition.transition_deleted_at.is_(None),
        )
    ).all()
    live = {r.transition_identifier for r in rows}
    if not isinstance(ordered_identifiers, list):
        _fail(
            "ordered_identifiers",
            "invalid_value",
            "must be a list of TRN-NNN identifiers",
        )
    supplied = list(ordered_identifiers)
    if len(set(supplied)) != len(supplied) or set(supplied) != live:
        _fail(
            "ordered_identifiers",
            "incomplete_order",
            "must name every live transition of the process exactly once "
            f"(the process has {sorted(live)})",
        )
    by_identifier = {r.transition_identifier: r for r in rows}
    for position, identifier in enumerate(supplied):
        row = by_identifier[identifier]
        if row.transition_order == position:
            continue
        before = to_dict(row)
        row.transition_order = position
        session.flush()
        emit(
            session,
            entity_type=_ENTITY_TYPE,
            entity_identifier=identifier,
            operation="update",
            before=before,
            after=to_dict(row),
        )
    session.flush()
    return list_transitions(session, process=process)


def delete_transition(session: Session, identifier: str) -> dict:
    """Soft-delete the transition. Idempotent (REQ-582, retain not delete)."""
    row = _get_row(session, identifier)
    if row.transition_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.transition_deleted_at = datetime.now(UTC)
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


def restore_transition(session: Session, identifier: str) -> dict:
    """Clear ``transition_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.transition_deleted_at is None:
        _fail(
            "transition_deleted_at",
            "not_deleted",
            "transition is not soft-deleted",
        )
    before = to_dict(row)
    row.transition_deleted_at = None
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
