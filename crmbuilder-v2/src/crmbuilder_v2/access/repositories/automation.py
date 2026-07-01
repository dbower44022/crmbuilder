"""Automation repository — condition-carrying design record (PRJ-025 PI-189
slice 2).

Per ``engine-neutral-design-model-and-adapters.md`` §8. An ``automation``
(``AUT-NNN``) is the engine-neutral description of a workflow on one entity: a
firing trigger, an optional neutral-condition gate, and a non-empty ordered
list of action objects. The module-level functions back the ``/automations``
REST endpoints and any access-layer caller (the adapter, MCP tools):

* :func:`list_automations` / :func:`get_automation` — reads. ``list`` takes
  optional ``entity`` / ``trigger`` filters.
* :func:`create_automation` — insert with a server-assigned (or explicit)
  identifier. ``entity`` (``ENT-NNN``) is validated live; ``trigger`` is in
  vocab; ``condition`` (when present) is a valid neutral AST; ``actions`` is a
  non-empty list of objects each carrying a ``"type"`` in
  ``AUTOMATION_ACTION_TYPES``.
* :func:`update_automation` / :func:`patch_automation` — full / partial update.
* :func:`delete_automation` / :func:`restore_automation` — soft-delete
  round-trip.
* :func:`next_automation_identifier` — the ``AUT-NNN`` allocator helper.

Validation posture mirrors the other design records — bad enum / format /
condition / empty-or-malformed actions / dead-entity raise
:class:`UnprocessableError` (422); disallowed status transitions raise
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
from crmbuilder_v2.access.conditions import ConditionError, validate_condition
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Automation, Entity
from crmbuilder_v2.access.vocab import (
    AUTOMATION_ACTION_TYPES,
    AUTOMATION_STATUS_TRANSITIONS,
    AUTOMATION_STATUSES,
    AUTOMATION_TRIGGERS,
)

_ENTITY_TYPE = "automation"
_IDENTIFIER_PREFIX = "AUT"
_IDENTIFIER_RE = re.compile(r"^AUT-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "entity",
        "trigger",
        "condition",
        "actions",
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
            "automation_identifier",
            "invalid_format",
            r"must match ^AUT-\d{3}$ (e.g. AUT-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_trigger(trigger: object) -> str:
    if trigger not in AUTOMATION_TRIGGERS:
        _fail(
            "automation_trigger",
            "invalid_value",
            f"must be one of {sorted(AUTOMATION_TRIGGERS)}",
        )
    return trigger  # type: ignore[return-value]


def _require_status(status: object) -> str:
    if status not in AUTOMATION_STATUSES:
        _fail(
            "automation_status",
            "invalid_value",
            f"must be one of {sorted(AUTOMATION_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_actions(actions: object) -> list:
    if not isinstance(actions, list) or not actions:
        _fail(
            "automation_actions",
            "invalid_value",
            "must be a non-empty list of action objects",
        )
    for index, action in enumerate(actions):  # type: ignore[arg-type]
        if not isinstance(action, dict):
            _fail(
                "automation_actions",
                "invalid_value",
                f"action[{index}] must be an object with a 'type'",
            )
        action_type = action.get("type")
        if action_type not in AUTOMATION_ACTION_TYPES:
            _fail(
                "automation_actions",
                "invalid_value",
                f"action[{index}].type must be one of "
                f"{sorted(AUTOMATION_ACTION_TYPES)}",
            )
    return actions  # type: ignore[return-value]


def _optional_condition(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(
            "automation_condition",
            "invalid_value",
            "must be a neutral condition object or null",
        )
    try:
        validate_condition(value)
    except ConditionError as exc:
        _fail("automation_condition", "invalid_condition", str(exc))
    return value  # type: ignore[return-value]


def _require_live_entity(value: object, *, session: Session) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(
            "automation_entity",
            "missing_entity",
            "automation_entity is required",
        )
    identifier = value.strip()  # type: ignore[union-attr]
    row = get_by_identifier(
        session, Entity, Entity.entity_identifier, identifier
    )
    if row is None:
        _fail(
            "automation_entity",
            "invalid_entity",
            f"entity {identifier!r} not found",
        )
    if row.entity_deleted_at is not None:
        _fail(
            "automation_entity",
            "invalid_entity",
            f"entity {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in AUTOMATION_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> Automation:
    row = get_by_identifier(
        session, Automation, Automation.automation_identifier, identifier
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


def list_automations(
    session: Session,
    *,
    entity: str | None = None,
    trigger: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return automations ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``entity`` / ``trigger`` filter on the columns.
    """
    stmt = select(Automation).order_by(Automation.automation_identifier)
    if entity is not None:
        stmt = stmt.where(Automation.automation_entity == entity)
    if trigger is not None:
        stmt = stmt.where(Automation.automation_trigger == trigger)
    if not include_deleted:
        stmt = stmt.where(Automation.automation_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_automation(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single automation by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session, Automation, Automation.automation_identifier, identifier
    )
    if row is None:
        return None
    if row.automation_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_automation_identifier(session: Session) -> str:
    """Return the next available ``AUT-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(Automation.automation_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    entity: str,
    trigger: str,
    condition: dict | None,
    actions: list,
    description: str | None,
    notes: str | None,
    status: str,
) -> Automation:
    return Automation(
        automation_identifier=identifier,
        automation_name=name,
        automation_entity=entity,
        automation_trigger=trigger,
        automation_condition=condition,
        automation_actions=actions,
        automation_description=description,
        automation_notes=notes,
        automation_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> Automation:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_automation_identifier(session)
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
        "could not assign a unique automation identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_automation(
    session: Session,
    *,
    name: str,
    entity: str,
    trigger: str,
    actions: list,
    condition: dict | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create an automation.

    Validation order: ``name`` non-empty; ``trigger`` in vocab; ``status``
    defaults to ``candidate``; ``condition`` a valid neutral AST when present;
    ``actions`` a non-empty list of typed action objects; the ``entity`` exists
    and is live; then insert.
    """
    name = _require_nonempty(name, field="automation_name")
    trigger = _require_trigger(trigger)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    condition = _optional_condition(condition)
    actions = _require_actions(actions)
    description = _optional_text(description, field="automation_description")
    notes = _optional_text(notes, field="automation_notes")
    entity = _require_live_entity(entity, session=session)

    columns = {
        "name": name,
        "entity": entity,
        "trigger": trigger,
        "condition": condition,
        "actions": actions,
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
                Automation,
                Automation.automation_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"automation {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.automation_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_automation(
    session: Session,
    identifier: str,
    *,
    automation_identifier: str | None = None,
    name: str,
    entity: str,
    trigger: str,
    actions: list,
    condition: dict | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if (
        automation_identifier is not None
        and automation_identifier != identifier
    ):
        _fail(
            "automation_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="automation_name")
    trigger = _require_trigger(trigger)
    condition = _optional_condition(condition)
    actions = _require_actions(actions)
    description = _optional_text(description, field="automation_description")
    notes = _optional_text(notes, field="automation_notes")
    entity = _require_live_entity(entity, session=session)

    status_v = _require_status(status)
    if status_v != row.automation_status:
        _check_transition(row.automation_status, status_v)
        row.automation_status = status_v

    row.automation_name = name
    row.automation_entity = entity
    row.automation_trigger = trigger
    row.automation_condition = condition
    row.automation_actions = actions
    row.automation_description = description
    row.automation_notes = notes
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


def patch_automation(session: Session, identifier: str, **fields) -> dict:
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
        row.automation_name = _require_nonempty(
            fields["name"], field="automation_name"
        )
    if "entity" in fields:
        row.automation_entity = _require_live_entity(
            fields["entity"], session=session
        )
    if "trigger" in fields:
        row.automation_trigger = _require_trigger(fields["trigger"])
    if "condition" in fields:
        row.automation_condition = _optional_condition(fields["condition"])
    if "actions" in fields:
        row.automation_actions = _require_actions(fields["actions"])
    if "description" in fields:
        row.automation_description = _optional_text(
            fields["description"], field="automation_description"
        )
    if "notes" in fields:
        row.automation_notes = _optional_text(
            fields["notes"], field="automation_notes"
        )
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.automation_status:
            _check_transition(row.automation_status, status_v)
            row.automation_status = status_v

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


def delete_automation(session: Session, identifier: str) -> dict:
    """Soft-delete the automation. Idempotent."""
    row = _get_row(session, identifier)
    if row.automation_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.automation_deleted_at = datetime.now(UTC)
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


def restore_automation(session: Session, identifier: str) -> dict:
    """Clear ``automation_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.automation_deleted_at is None:
        _fail(
            "automation_deleted_at",
            "not_deleted",
            "automation is not soft-deleted",
        )
    before = to_dict(row)
    row.automation_deleted_at = None
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
