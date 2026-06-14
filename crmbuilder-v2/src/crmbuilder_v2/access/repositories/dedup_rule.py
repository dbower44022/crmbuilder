"""Dedup-rule repository — dedup-and-template design record (PRJ-025 PI-189
slice 3).

Per ``engine-neutral-design-model-and-adapters.md`` §8. A ``dedup_rule``
(``DUP-NNN``) is the engine-neutral description of a duplicate-detection rule:
a non-empty ordered list of match-field references, an optional per-field
normalization map, and the on-match action (``block`` / ``warn``). The
module-level functions back the ``/dedup-rules`` REST endpoints and any
access-layer caller (the adapter, MCP tools):

* :func:`list_dedup_rules` / :func:`get_dedup_rule` — reads. ``list`` takes an
  optional ``entity`` filter on the deduped-entity column.
* :func:`create_dedup_rule` — insert with a server-assigned (or explicit)
  identifier. ``entity`` (``ENT-NNN``) is validated live; ``match_fields`` is a
  non-empty list of field references; ``normalize`` (when present) maps a field
  reference to a token in ``NORMALIZE_TOKENS``; ``on_match`` is in
  ``DEDUP_ON_MATCH``.
* :func:`update_dedup_rule` / :func:`patch_dedup_rule` — full / partial update.
* :func:`delete_dedup_rule` / :func:`restore_dedup_rule` — soft-delete
  round-trip.
* :func:`next_dedup_rule_identifier` — the ``DUP-NNN`` allocator helper.

Validation posture mirrors the other design records — bad enum / format /
empty-match-fields / bad-normalize-token / dead-entity raise
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
from crmbuilder_v2.access.models import DedupRule, Entity
from crmbuilder_v2.access.vocab import (
    DEDUP_ON_MATCH,
    DEDUP_RULE_STATUS_TRANSITIONS,
    DEDUP_RULE_STATUSES,
    NORMALIZE_TOKENS,
)

_ENTITY_TYPE = "dedup_rule"
_IDENTIFIER_PREFIX = "DUP"
_IDENTIFIER_RE = re.compile(r"^DUP-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "entity",
        "match_fields",
        "normalize",
        "on_match",
        "message",
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
            "dedup_rule_identifier",
            "invalid_format",
            r"must match ^DUP-\d{3}$ (e.g. DUP-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_status(status: object) -> str:
    if status not in DEDUP_RULE_STATUSES:
        _fail(
            "dedup_rule_status",
            "invalid_value",
            f"must be one of {sorted(DEDUP_RULE_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _require_on_match(on_match: object) -> str:
    if on_match not in DEDUP_ON_MATCH:
        _fail(
            "dedup_rule_on_match",
            "invalid_value",
            f"must be one of {sorted(DEDUP_ON_MATCH)}",
        )
    return on_match  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _require_match_fields(match_fields: object) -> list:
    if not isinstance(match_fields, list) or not match_fields:
        _fail(
            "dedup_rule_match_fields",
            "invalid_value",
            "must be a non-empty list of field references",
        )
    for index, ref in enumerate(match_fields):  # type: ignore[arg-type]
        if not isinstance(ref, str) or not ref.strip():
            _fail(
                "dedup_rule_match_fields",
                "invalid_value",
                f"match_fields[{index}] must be a non-empty field "
                "reference string",
            )
    return match_fields  # type: ignore[return-value]


def _optional_normalize(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        _fail(
            "dedup_rule_normalize",
            "invalid_value",
            "must be an object mapping a field reference to a token, or null",
        )
    for ref, token in value.items():  # type: ignore[union-attr]
        if not isinstance(ref, str) or not ref.strip():
            _fail(
                "dedup_rule_normalize",
                "invalid_value",
                "normalize keys must be non-empty field reference strings",
            )
        if token not in NORMALIZE_TOKENS:
            _fail(
                "dedup_rule_normalize",
                "invalid_value",
                f"normalize[{ref!r}] must be one of {sorted(NORMALIZE_TOKENS)}",
            )
    return value  # type: ignore[return-value]


def _require_live_entity(value: object, *, session: Session) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(
            "dedup_rule_entity",
            "missing_entity",
            "dedup_rule_entity is required",
        )
    identifier = value.strip()  # type: ignore[union-attr]
    row = get_by_identifier(
        session, Entity, Entity.entity_identifier, identifier
    )
    if row is None:
        _fail(
            "dedup_rule_entity",
            "invalid_entity",
            f"entity {identifier!r} not found",
        )
    if row.entity_deleted_at is not None:
        _fail(
            "dedup_rule_entity",
            "invalid_entity",
            f"entity {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in DEDUP_RULE_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> DedupRule:
    row = get_by_identifier(
        session, DedupRule, DedupRule.dedup_rule_identifier, identifier
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


def list_dedup_rules(
    session: Session,
    *,
    entity: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return dedup rules ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``entity`` filters on the deduped-entity column.
    """
    stmt = select(DedupRule).order_by(DedupRule.dedup_rule_identifier)
    if entity is not None:
        stmt = stmt.where(DedupRule.dedup_rule_entity == entity)
    if not include_deleted:
        stmt = stmt.where(DedupRule.dedup_rule_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_dedup_rule(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return a single dedup rule by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session, DedupRule, DedupRule.dedup_rule_identifier, identifier
    )
    if row is None:
        return None
    if row.dedup_rule_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_dedup_rule_identifier(session: Session) -> str:
    """Return the next available ``DUP-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(DedupRule.dedup_rule_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    entity: str,
    match_fields: list,
    normalize: dict | None,
    on_match: str,
    message: str | None,
    description: str | None,
    notes: str | None,
    status: str,
) -> DedupRule:
    return DedupRule(
        dedup_rule_identifier=identifier,
        dedup_rule_name=name,
        dedup_rule_entity=entity,
        dedup_rule_match_fields=match_fields,
        dedup_rule_normalize=normalize,
        dedup_rule_on_match=on_match,
        dedup_rule_message=message,
        dedup_rule_description=description,
        dedup_rule_notes=notes,
        dedup_rule_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> DedupRule:
    candidate = next_dedup_rule_identifier(session)
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
        "could not assign a unique dedup_rule identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_dedup_rule(
    session: Session,
    *,
    name: str,
    entity: str,
    match_fields: list,
    on_match: str,
    normalize: dict | None = None,
    message: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a dedup rule.

    Validation order: ``name`` non-empty; ``status`` defaults to ``candidate``;
    ``match_fields`` a non-empty list of field references; ``normalize`` a valid
    field→token map when present; ``on_match`` in vocab; the deduped ``entity``
    exists and is live; then insert.
    """
    name = _require_nonempty(name, field="dedup_rule_name")
    if status is None:
        status = "candidate"
    status = _require_status(status)
    match_fields = _require_match_fields(match_fields)
    normalize = _optional_normalize(normalize)
    on_match = _require_on_match(on_match)
    message = _optional_text(message, field="dedup_rule_message")
    description = _optional_text(description, field="dedup_rule_description")
    notes = _optional_text(notes, field="dedup_rule_notes")
    entity = _require_live_entity(entity, session=session)

    column_values = {
        "name": name,
        "entity": entity,
        "match_fields": match_fields,
        "normalize": normalize,
        "on_match": on_match,
        "message": message,
        "description": description,
        "notes": notes,
        "status": status,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **column_values)
    else:
        _require_identifier_format(identifier)
        if (
            get_by_identifier(
                session,
                DedupRule,
                DedupRule.dedup_rule_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"dedup_rule {identifier!r} already exists")
        row = _new_row(identifier, **column_values)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.dedup_rule_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_dedup_rule(
    session: Session,
    identifier: str,
    *,
    dedup_rule_identifier: str | None = None,
    name: str,
    entity: str,
    match_fields: list,
    on_match: str,
    normalize: dict | None = None,
    message: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if (
        dedup_rule_identifier is not None
        and dedup_rule_identifier != identifier
    ):
        _fail(
            "dedup_rule_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="dedup_rule_name")
    match_fields = _require_match_fields(match_fields)
    normalize = _optional_normalize(normalize)
    on_match = _require_on_match(on_match)
    message = _optional_text(message, field="dedup_rule_message")
    description = _optional_text(description, field="dedup_rule_description")
    notes = _optional_text(notes, field="dedup_rule_notes")
    entity = _require_live_entity(entity, session=session)

    status_v = _require_status(status)
    if status_v != row.dedup_rule_status:
        _check_transition(row.dedup_rule_status, status_v)
        row.dedup_rule_status = status_v

    row.dedup_rule_name = name
    row.dedup_rule_entity = entity
    row.dedup_rule_match_fields = match_fields
    row.dedup_rule_normalize = normalize
    row.dedup_rule_on_match = on_match
    row.dedup_rule_message = message
    row.dedup_rule_description = description
    row.dedup_rule_notes = notes
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


def patch_dedup_rule(session: Session, identifier: str, **fields) -> dict:
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
        row.dedup_rule_name = _require_nonempty(
            fields["name"], field="dedup_rule_name"
        )
    if "entity" in fields:
        row.dedup_rule_entity = _require_live_entity(
            fields["entity"], session=session
        )
    if "match_fields" in fields:
        row.dedup_rule_match_fields = _require_match_fields(
            fields["match_fields"]
        )
    if "normalize" in fields:
        row.dedup_rule_normalize = _optional_normalize(fields["normalize"])
    if "on_match" in fields:
        row.dedup_rule_on_match = _require_on_match(fields["on_match"])
    if "message" in fields:
        row.dedup_rule_message = _optional_text(
            fields["message"], field="dedup_rule_message"
        )
    if "description" in fields:
        row.dedup_rule_description = _optional_text(
            fields["description"], field="dedup_rule_description"
        )
    if "notes" in fields:
        row.dedup_rule_notes = _optional_text(
            fields["notes"], field="dedup_rule_notes"
        )
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.dedup_rule_status:
            _check_transition(row.dedup_rule_status, status_v)
            row.dedup_rule_status = status_v

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


def delete_dedup_rule(session: Session, identifier: str) -> dict:
    """Soft-delete the dedup rule. Idempotent."""
    row = _get_row(session, identifier)
    if row.dedup_rule_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.dedup_rule_deleted_at = datetime.now(UTC)
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


def restore_dedup_rule(session: Session, identifier: str) -> dict:
    """Clear ``dedup_rule_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.dedup_rule_deleted_at is None:
        _fail(
            "dedup_rule_deleted_at",
            "not_deleted",
            "dedup_rule is not soft-deleted",
        )
    before = to_dict(row)
    row.dedup_rule_deleted_at = None
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
