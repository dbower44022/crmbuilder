"""Message-template repository — dedup-and-template design record (PRJ-025
PI-189 slice 3).

Per ``engine-neutral-design-model-and-adapters.md`` §8. A ``message_template``
(``MSG-NNN``) is the engine-neutral description of a notification/communication:
a required body (content/intent), an optional subject (both may carry
merge-field placeholders), an optional merge-field list, an optional channel,
an optional free-text audience, and an optional subject ``ENT-NNN`` the
template is about. The module-level functions back the ``/message-templates``
REST endpoints and any access-layer caller (the adapter, MCP tools):

* :func:`list_message_templates` / :func:`get_message_template` — reads.
  ``list`` takes an optional ``entity`` filter and an optional ``channel``
  filter.
* :func:`create_message_template` — insert with a server-assigned (or explicit)
  identifier. ``body`` is non-empty; ``channel`` (when present) is in
  ``MESSAGE_CHANNELS``; ``entity`` (when present) is validated live;
  ``merge_fields`` (when present) is a list of merge-field reference strings.
* :func:`update_message_template` / :func:`patch_message_template` — full /
  partial update.
* :func:`delete_message_template` / :func:`restore_message_template` —
  soft-delete round-trip.
* :func:`next_message_template_identifier` — the ``MSG-NNN`` allocator helper.

Validation posture mirrors the other design records — empty body / bad channel
/ bad merge-fields / dead-entity raise :class:`UnprocessableError` (422);
disallowed status transitions raise :class:`StatusTransitionError` (422); a
missing record raises :class:`NotFoundError` (404); an explicit-identifier
collision raises :class:`ConflictError` (409).
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
from crmbuilder_v2.access.models import Entity, MessageTemplate
from crmbuilder_v2.access.vocab import (
    MESSAGE_CHANNELS,
    MESSAGE_TEMPLATE_STATUS_TRANSITIONS,
    MESSAGE_TEMPLATE_STATUSES,
)

_ENTITY_TYPE = "message_template"
_IDENTIFIER_PREFIX = "MSG"
_IDENTIFIER_RE = re.compile(r"^MSG-\d{3}$")

_MAX_AUTOASSIGN_ATTEMPTS = 50

_PATCHABLE_FIELDS = frozenset(
    {
        "name",
        "entity",
        "channel",
        "subject",
        "body",
        "merge_fields",
        "audience",
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
            "message_template_identifier",
            "invalid_format",
            r"must match ^MSG-\d{3}$ (e.g. MSG-001)",
        )
    return identifier


def _require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail(field, "missing_or_empty", "must be a non-empty string")
    return value.strip()  # type: ignore[union-attr]


def _require_status(status: object) -> str:
    if status not in MESSAGE_TEMPLATE_STATUSES:
        _fail(
            "message_template_status",
            "invalid_value",
            f"must be one of {sorted(MESSAGE_TEMPLATE_STATUSES)}",
        )
    return status  # type: ignore[return-value]


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(field, "invalid_value", "must be a string or null")
    return value


def _optional_channel(value: object) -> str | None:
    if value is None:
        return None
    if value not in MESSAGE_CHANNELS:
        _fail(
            "message_template_channel",
            "invalid_value",
            f"must be one of {sorted(MESSAGE_CHANNELS)} or null",
        )
    return value  # type: ignore[return-value]


def _optional_merge_fields(value: object) -> list | None:
    if value is None:
        return None
    if not isinstance(value, list):
        _fail(
            "message_template_merge_fields",
            "invalid_value",
            "must be a list of merge-field reference strings or null",
        )
    for index, ref in enumerate(value):  # type: ignore[arg-type]
        if not isinstance(ref, str) or not ref.strip():
            _fail(
                "message_template_merge_fields",
                "invalid_value",
                f"merge_fields[{index}] must be a non-empty "
                "merge-field reference string",
            )
    return value  # type: ignore[return-value]


def _optional_live_entity(value: object, *, session: Session) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        _fail(
            "message_template_entity",
            "invalid_entity",
            "must be an ENT-NNN identifier or null",
        )
    identifier = value.strip()  # type: ignore[union-attr]
    row = get_by_identifier(
        session, Entity, Entity.entity_identifier, identifier
    )
    if row is None:
        _fail(
            "message_template_entity",
            "invalid_entity",
            f"entity {identifier!r} not found",
        )
    if row.entity_deleted_at is not None:
        _fail(
            "message_template_entity",
            "invalid_entity",
            f"entity {identifier!r} is soft-deleted",
        )
    return identifier


def _check_transition(current: str, requested: str) -> None:
    if requested == current:
        return
    if requested not in MESSAGE_TEMPLATE_STATUS_TRANSITIONS.get(
        current, frozenset()
    ):
        raise StatusTransitionError(current, requested)


def _get_row(session: Session, identifier: str) -> MessageTemplate:
    row = get_by_identifier(
        session,
        MessageTemplate,
        MessageTemplate.message_template_identifier,
        identifier,
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


def list_message_templates(
    session: Session,
    *,
    entity: str | None = None,
    channel: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    """Return message templates ordered by identifier ascending.

    Soft-deleted rows are excluded unless ``include_deleted`` is True.
    ``entity`` and ``channel`` filter on their respective columns.
    """
    stmt = select(MessageTemplate).order_by(
        MessageTemplate.message_template_identifier
    )
    if entity is not None:
        stmt = stmt.where(MessageTemplate.message_template_entity == entity)
    if channel is not None:
        stmt = stmt.where(MessageTemplate.message_template_channel == channel)
    if not include_deleted:
        stmt = stmt.where(MessageTemplate.message_template_deleted_at.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_message_template(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    """Return one message template by identifier, or ``None`` if not visible."""
    row = get_by_identifier(
        session,
        MessageTemplate,
        MessageTemplate.message_template_identifier,
        identifier,
    )
    if row is None:
        return None
    if row.message_template_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_message_template_identifier(session: Session) -> str:
    """Return the next available ``MSG-NNN`` (soft-deleted rows included)."""
    identifiers = session.scalars(
        select(MessageTemplate.message_template_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    name: str,
    entity: str | None,
    channel: str | None,
    subject: str | None,
    body: str,
    merge_fields: list | None,
    audience: str | None,
    description: str | None,
    notes: str | None,
    status: str,
) -> MessageTemplate:
    return MessageTemplate(
        message_template_identifier=identifier,
        message_template_name=name,
        message_template_entity=entity,
        message_template_channel=channel,
        message_template_subject=subject,
        message_template_body=body,
        message_template_merge_fields=merge_fields,
        message_template_audience=audience,
        message_template_description=description,
        message_template_notes=notes,
        message_template_status=status,
    )


def _insert_with_autoassign(session: Session, **columns) -> MessageTemplate:
    candidate = next_message_template_identifier(session)
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
        "could not assign a unique message_template identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_message_template(
    session: Session,
    *,
    name: str,
    body: str,
    entity: str | None = None,
    channel: str | None = None,
    subject: str | None = None,
    merge_fields: list | None = None,
    audience: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    identifier: str | None = None,
) -> dict:
    """Create a message template.

    Validation order: ``name`` non-empty; ``status`` defaults to ``candidate``;
    ``body`` non-empty; ``channel`` in vocab when present; ``merge_fields`` a
    valid reference list when present; the subject ``entity`` exists and is live
    when present; then insert.
    """
    name = _require_nonempty(name, field="message_template_name")
    if status is None:
        status = "candidate"
    status = _require_status(status)
    body = _require_nonempty(body, field="message_template_body")
    channel = _optional_channel(channel)
    subject = _optional_text(subject, field="message_template_subject")
    merge_fields = _optional_merge_fields(merge_fields)
    audience = _optional_text(audience, field="message_template_audience")
    description = _optional_text(
        description, field="message_template_description"
    )
    notes = _optional_text(notes, field="message_template_notes")
    entity = _optional_live_entity(entity, session=session)

    column_values = {
        "name": name,
        "entity": entity,
        "channel": channel,
        "subject": subject,
        "body": body,
        "merge_fields": merge_fields,
        "audience": audience,
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
                MessageTemplate,
                MessageTemplate.message_template_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(
                f"message_template {identifier!r} already exists"
            )
        row = _new_row(identifier, **column_values)
        session.add(row)
        session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.message_template_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_message_template(
    session: Session,
    identifier: str,
    *,
    message_template_identifier: str | None = None,
    name: str,
    body: str,
    entity: str | None = None,
    channel: str | None = None,
    subject: str | None = None,
    merge_fields: list | None = None,
    audience: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str,
) -> dict:
    """Full-replace update (PUT)."""
    row = _get_row(session, identifier)
    if (
        message_template_identifier is not None
        and message_template_identifier != identifier
    ):
        _fail(
            "message_template_identifier",
            "path_mismatch",
            "identifier in body must match the path",
        )
    before = to_dict(row)

    name = _require_nonempty(name, field="message_template_name")
    body = _require_nonempty(body, field="message_template_body")
    channel = _optional_channel(channel)
    subject = _optional_text(subject, field="message_template_subject")
    merge_fields = _optional_merge_fields(merge_fields)
    audience = _optional_text(audience, field="message_template_audience")
    description = _optional_text(
        description, field="message_template_description"
    )
    notes = _optional_text(notes, field="message_template_notes")
    entity = _optional_live_entity(entity, session=session)

    status_v = _require_status(status)
    if status_v != row.message_template_status:
        _check_transition(row.message_template_status, status_v)
        row.message_template_status = status_v

    row.message_template_name = name
    row.message_template_entity = entity
    row.message_template_channel = channel
    row.message_template_subject = subject
    row.message_template_body = body
    row.message_template_merge_fields = merge_fields
    row.message_template_audience = audience
    row.message_template_description = description
    row.message_template_notes = notes
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


def patch_message_template(
    session: Session, identifier: str, **fields
) -> dict:
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
        row.message_template_name = _require_nonempty(
            fields["name"], field="message_template_name"
        )
    if "entity" in fields:
        row.message_template_entity = _optional_live_entity(
            fields["entity"], session=session
        )
    if "channel" in fields:
        row.message_template_channel = _optional_channel(fields["channel"])
    if "subject" in fields:
        row.message_template_subject = _optional_text(
            fields["subject"], field="message_template_subject"
        )
    if "body" in fields:
        row.message_template_body = _require_nonempty(
            fields["body"], field="message_template_body"
        )
    if "merge_fields" in fields:
        row.message_template_merge_fields = _optional_merge_fields(
            fields["merge_fields"]
        )
    if "audience" in fields:
        row.message_template_audience = _optional_text(
            fields["audience"], field="message_template_audience"
        )
    if "description" in fields:
        row.message_template_description = _optional_text(
            fields["description"], field="message_template_description"
        )
    if "notes" in fields:
        row.message_template_notes = _optional_text(
            fields["notes"], field="message_template_notes"
        )
    if "status" in fields:
        status_v = _require_status(fields["status"])
        if status_v != row.message_template_status:
            _check_transition(row.message_template_status, status_v)
            row.message_template_status = status_v

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


def delete_message_template(session: Session, identifier: str) -> dict:
    """Soft-delete the message template. Idempotent."""
    row = _get_row(session, identifier)
    if row.message_template_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.message_template_deleted_at = datetime.now(UTC)
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


def restore_message_template(session: Session, identifier: str) -> dict:
    """Clear ``message_template_deleted_at``. Raises 422 if the row is live."""
    row = _get_row(session, identifier)
    if row.message_template_deleted_at is None:
        _fail(
            "message_template_deleted_at",
            "not_deleted",
            "message_template is not soft-deleted",
        )
    before = to_dict(row)
    row.message_template_deleted_at = None
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
