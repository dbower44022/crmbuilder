"""Rule repository — condition-carrying design record (PRJ-025 PI-189 slice 2).

Per ``engine-neutral-design-model-and-adapters.md`` §8. A ``rule`` (``RUL-NNN``)
governs one design construct — a ``field`` (required/visible gate) or an
``entity`` (a valid-when invariant) — with a neutral condition AST. The
module-level functions back the ``/rules`` REST endpoints and any access-layer
caller (the adapter, MCP tools):

* :func:`list_rules` / :func:`get_rule` — reads. ``list`` takes optional
  ``subject_type`` / ``subject_identifier`` / ``effect`` filters.
* :func:`create_rule` — insert with a server-assigned (or explicit)
  identifier. The subject (``FLD-NNN`` / ``ENT-NNN``) is validated to exist,
  be live, and match ``subject_type``; ``condition`` is validated as a neutral
  condition AST.
* :func:`update_rule` / :func:`patch_rule` — full / partial update. Subject,
  condition, effect, and status changes are re-validated.
* :func:`delete_rule` / :func:`restore_rule` — soft-delete round-trip.
* :func:`next_rule_identifier` — the ``RUL-NNN`` allocator helper.

Validation posture: identifier-format, subject-type / effect / status enum,
PUT identifier/path mismatch, a malformed condition, and a non-existent /
soft-deleted / wrong-type subject raise :class:`UnprocessableError` (422);
disallowed status transitions raise :class:`StatusTransitionError` (422); a
missing record raises :class:`NotFoundError` (404); an explicit-identifier
collision on create raises :class:`ConflictError` (409).
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
from crmbuilder_v2.access.conditions import ConditionError, validate_condition
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Entity, Field, Rule
from crmbuilder_v2.access.vocab import (
    RULE_EFFECTS,
    RULE_STATUS_TRANSITIONS,
    RULE_STATUSES,
    RULE_SUBJECT_TYPES,
)

_ENTITY_TYPE = "rule"
_IDENTIFIER_PREFIX = "RUL"
_IDENTIFIER_RE = re.compile(r"^RUL-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "subject_type",
        "subject_identifier",
        "effect",
        "condition",
        "message",
        "description",
        "notes",
        "status",
    }
)

# Per subject_type, the model + identifier-column + deleted-column used to
# resolve and liveness-check the rule's subject.
_SUBJECT_RESOLVERS = {
    "field": (Field, Field.field_identifier, "field_deleted_at"),
    "entity": (Entity, Entity.entity_identifier, "entity_deleted_at"),
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _fail(field: str, code: str, message: str) -> None:
    raise UnprocessableError([FieldError(field, code, message)])


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        _fail(
            "rule_identifier",
            "invalid_format",
            r"must match ^RUL-\d{3}$ (e.g. RUL-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_subject_type(subject_type: object) -> str:
    if subject_type not in RULE_SUBJECT_TYPES:
        _fail(
            "rule_subject_type",
            "invalid_value",
            f"must be one of {sorted(RULE_SUBJECT_TYPES)}",
        )
    return subject_type  # type: ignore[return-value]


def _require_effect(effect: object) -> str:
    if effect not in RULE_EFFECTS:
        _fail(
            "rule_effect",
            "invalid_value",
            f"must be one of {sorted(RULE_EFFECTS)}",
        )
    return effect  # type: ignore[return-value]


def _require_status(status: object) -> str:
    if status not in RULE_STATUSES:
        _fail(
            "rule_status",
            "invalid_value",
            f"must be one of {sorted(RULE_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_condition(condition: object) -> dict:
    if not isinstance(condition, dict):
        _fail(
            "rule_condition",
            "invalid_value",
            "must be a neutral condition object",
        )
    try:
        validate_condition(condition)
    except ConditionError as exc:
        _fail("rule_condition", "invalid_condition", str(exc))
    return condition  # type: ignore[return-value]


def _require_live_subject(
    subject_type: str, subject_identifier: object, *, session: Session
) -> str:
    """Resolve the rule subject, requiring it to exist, be live, and match."""
    if not isinstance(subject_identifier, str) or not subject_identifier.strip():
        _fail(
            "rule_subject_identifier",
            "missing_subject",
            "rule_subject_identifier is required",
        )
    identifier = subject_identifier.strip()  # type: ignore[union-attr]
    model, id_col, deleted_attr = _SUBJECT_RESOLVERS[subject_type]
    row = get_by_identifier(session, model, id_col, identifier)
    if row is None:
        _fail(
            "rule_subject_identifier",
            "invalid_subject",
            f"{subject_type} {identifier!r} not found",
        )
    if getattr(row, deleted_attr) is not None:
        _fail(
            "rule_subject_identifier",
            "invalid_subject",
            f"{subject_type} {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in RULE_STATUS_TRANSITIONS.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> Rule:
    row = get_by_identifier(session, Rule, Rule.rule_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_rules(
    session: Session,
    *,
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    effect: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return rules ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``subject_type`` / ``subject_identifier`` / ``effect`` filter the columns.
    """
    stmt = select(Rule).order_by(Rule.rule_identifier)
    if subject_type is not None:
        stmt = stmt.where(Rule.rule_subject_type == subject_type)
    if subject_identifier is not None:
        stmt = stmt.where(Rule.rule_subject_identifier == subject_identifier)
    if effect is not None:
        stmt = stmt.where(Rule.rule_effect == effect)
    if not include_deleted:
        stmt = stmt.where(Rule.rule_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_rule(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single rule by identifier, or ``None`` if not visible."""
    row = get_by_identifier(session, Rule, Rule.rule_identifier, identifier)
    if row is None:
        return None
    if row.rule_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_rule_identifier(session: Session) -> str:
    """Return the next available ``RUL-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(select(Rule.rule_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    subject_type: str,
    subject_identifier: str,
    effect: str,
    condition: dict,
    message: str | None,
    description: str | None,
    notes: str | None,
    status: str,
) -> Rule:
    return Rule(
        rule_identifier=identifier,
        rule_name=name,
        rule_subject_type=subject_type,
        rule_subject_identifier=subject_identifier,
        rule_effect=effect,
        rule_condition=condition,
        rule_message=message,
        rule_description=description,
        rule_notes=notes,
        rule_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> Rule:
    candidate = next_rule_identifier(session)
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
        "could not assign a unique rule identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_rule(
    session: Session,
    *,
    name: str,
    subject_type: str,
    subject_identifier: str,
    effect: str,
    condition: dict,
    message: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a rule.

    Validation order: ``name`` non-empty; ``subject_type`` / ``effect`` in
    vocab; ``status`` defaults to ``candidate``, validated; ``condition`` a
    valid neutral AST; the subject exists, is live, and matches the type;
    then insert (server-assigned id when ``identifier`` is ``None``).
    """
    name = _require_nonempty(name, field="rule_name")
    subject_type = _require_subject_type(subject_type)
    effect = _require_effect(effect)
    if status is None:
        status = "candidate"
    status = _require_status(status)
    condition = _require_condition(condition)
    message = _optional_text(message, field="rule_message")
    description = _optional_text(description, field="rule_description")
    notes = _optional_text(notes, field="rule_notes")
    subject_identifier = _require_live_subject(
        subject_type, subject_identifier, session=session
    )

    columns = {
        "name": name,
        "subject_type": subject_type,
        "subject_identifier": subject_identifier,
        "effect": effect,
        "condition": condition,
        "message": message,
        "description": description,
        "notes": notes,
        "status": status,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **columns)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(session, Rule, Rule.rule_identifier, identifier)
            is not None
        ):
            raise ConflictError(f"rule {identifier!r} already exists")
        row = _new_row(identifier, **columns)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.rule_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_rule(
    session: Session,
    identifier: str,
    *,
    rule_identifier: str | None = None,
    name: str,
    subject_type: str,
    subject_identifier: str,
    effect: str,
    condition: dict,
    message: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT).

    ``rule_identifier`` (the body identifier) must match the path; the subject
    is re-validated; a status change is transition-validated.
    """
    row = _get_row(session, identifier)
    if rule_identifier is not None and rule_identifier != identifier:
        _fail(
            "rule_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="rule_name")
    subject_type = _require_subject_type(subject_type)
    effect = _require_effect(effect)
    condition = _require_condition(condition)
    message = _optional_text(message, field="rule_message")
    description = _optional_text(description, field="rule_description")
    notes = _optional_text(notes, field="rule_notes")
    subject_identifier = _require_live_subject(
        subject_type, subject_identifier, session=session
    )

    status_v = _require_status(status)
    if status_v != row.rule_status:
        _check_transition(row.rule_status, status_v)
        row.rule_status = status_v

    row.rule_name = name
    row.rule_subject_type = subject_type
    row.rule_subject_identifier = subject_identifier
    row.rule_effect = effect
    row.rule_condition = condition
    row.rule_message = message
    row.rule_description = description
    row.rule_notes = notes
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


def patch_rule(session: Session, identifier: str, **fields) -> dict:
    """Partial update (PATCH). Only the supplied fields are touched.

    A ``subject_type`` / ``subject_identifier`` change re-validates the subject
    against the (possibly new) type; a ``condition`` change re-validates the
    AST; a ``status`` change is transition-validated.
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
        row.rule_name = _require_nonempty(fields["name"], field="rule_name")
    if "effect" in fields:
        row.rule_effect = _require_effect(fields["effect"])
    if "condition" in fields:
        row.rule_condition = _require_condition(fields["condition"])
    if "message" in fields:
        row.rule_message = _optional_text(
            fields["message"], field="rule_message"
        )
    if "description" in fields:
        row.rule_description = _optional_text(
            fields["description"], field="rule_description"
        )
    if "notes" in fields:
        row.rule_notes = _optional_text(fields["notes"], field="rule_notes")

    # subject_type and subject_identifier are co-validated: a change to either
    # re-resolves the subject against the effective type.
    if "subject_type" in fields or "subject_identifier" in fields:
        subject_type = _require_subject_type(
            fields.get("subject_type", row.rule_subject_type)
        )
        subject_identifier = _require_live_subject(
            subject_type,
            fields.get("subject_identifier", row.rule_subject_identifier),
            session=session,
        )
        row.rule_subject_type = subject_type
        row.rule_subject_identifier = subject_identifier

    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.rule_status:
            _check_transition(row.rule_status, status_v)
            row.rule_status = status_v

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


def delete_rule(session: Session, identifier: str) -> dict:
    """Soft-delete the rule. Idempotent."""
    row = _get_row(session, identifier)
    if row.rule_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.rule_deleted_at = datetime.now(UTC)
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


def restore_rule(session: Session, identifier: str) -> dict:
    """Clear ``rule_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.rule_deleted_at is None:
        _fail("rule_deleted_at", "not_deleted", "rule is not soft-deleted")
    before = to_dict(row)
    row.rule_deleted_at = None
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
