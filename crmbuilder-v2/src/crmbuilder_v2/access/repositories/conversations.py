"""Conversation repository — the second governance entity type (UI v0.7).

Per ``governance-schema-specs/conversation.md``. Seven-status workflow
lifecycle (forward-only planning line plus three truly-terminal terminals).
Access-layer edge rules:

* **Workstream membership** — exactly one outbound
  ``conversation_belongs_to_workstream`` edge is required on every live
  record (DEC-120).
* **Complete-requires-session-edge** — ``complete`` requires an outbound
  ``conversation_records_session`` edge (DEC-131).
* **Supersession-requires-edge** — ``superseded`` requires an outbound
  ``supersedes`` edge.

Per-status lifecycle timestamps are server-set on transition; the membership
and terminal edges may be supplied in the same request's ``references`` array
and are validated together at commit time.
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
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Conversation
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    CONVERSATION_STATUS_TRANSITIONS,
    CONVERSATION_STATUSES,
)

_ENTITY_TYPE = "conversation"
_IDENTIFIER_PREFIX = "CONV"
_IDENTIFIER_RE = re.compile(r"^CONV-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"title", "purpose", "description", "notes", "status"}
)

_STATUS_TIMESTAMP = {
    "kickoff_drafted": "conversation_kickoff_drafted_at",
    "ready": "conversation_ready_at",
    "in_flight": "conversation_started_at",
    "complete": "conversation_completed_at",
    "cancelled": "conversation_cancelled_at",
    "superseded": "conversation_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(
        status, CONVERSATION_STATUSES, field="conversation_status"
    )


def _reject_duplicate_title(
    session: Session, title: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(Conversation).where(
        func.lower(Conversation.conversation_title) == title.lower(),
        Conversation.conversation_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            Conversation.conversation_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "conversation_title",
                    "duplicate",
                    f"a conversation titled {title!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Conversation:
    row = session.get(Conversation, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_edges(session: Session, identifier: str, status: str) -> None:
    """Enforce membership, complete, and supersession edge rules."""
    membership = gov.outbound_edges(
        session,
        source_type=_ENTITY_TYPE,
        source_id=identifier,
        relationship="conversation_belongs_to_workstream",
    )
    if len(membership) != 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "missing_workstream_membership_edge",
                    "exactly one conversation_belongs_to_workstream edge is required",
                )
            ]
        )
    if status == "complete":
        edges = gov.outbound_edges(
            session,
            source_type=_ENTITY_TYPE,
            source_id=identifier,
            relationship="conversation_records_session",
        )
        if not edges:
            raise UnprocessableError(
                [
                    FieldError(
                        "status",
                        "complete_conversation_requires_session_edge",
                        "an outbound 'conversation_records_session' edge is required",
                    )
                ]
            )
    if status == "superseded":
        gov.reject_missing_supersedes_edge(
            session, entity_type=_ENTITY_TYPE, identifier=identifier
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_conversations(
    session: Session,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    workstream_identifier: str | None = None,
) -> list[dict]:
    stmt = select(Conversation).order_by(Conversation.conversation_identifier)
    if not include_deleted:
        stmt = stmt.where(Conversation.conversation_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Conversation.conversation_status == status)
    rows = [to_dict(r) for r in session.scalars(stmt).all()]
    if workstream_identifier is not None:
        members = {
            e.source_id
            for e in gov.inbound_edges(
                session,
                target_type="workstream",
                target_id=workstream_identifier,
                relationship="conversation_belongs_to_workstream",
            )
        }
        rows = [r for r in rows if r["conversation_identifier"] in members]
    return rows


def get_conversation(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = session.get(Conversation, identifier)
    if row is None:
        return None
    if row.conversation_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_conversation_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(Conversation.conversation_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier, title, purpose, description, notes, status):
    return Conversation(
        conversation_identifier=identifier,
        conversation_title=title,
        conversation_purpose=purpose,
        conversation_description=description,
        conversation_notes=notes,
        conversation_status=status,
    )


def _insert_with_autoassign(session, title, purpose, description, notes, status):
    candidate = next_conversation_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, title, purpose, description, notes, status)
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
        "could not assign a unique conversation identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_conversation(
    session: Session,
    *,
    title: str,
    purpose: str,
    description: str,
    notes: str | None = None,
    status: str = "planned",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="conversation_title")
    purpose = gov.require_nonempty(purpose, field="conversation_purpose")
    description = gov.require_nonempty(
        description, field="conversation_description"
    )
    if status is None:
        status = "planned"
    _require_status(status)
    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, purpose, description, notes, status
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="conversation_identifier", example="CONV-001",
        )
        if session.get(Conversation, identifier) is not None:
            raise ConflictError(f"conversation {identifier!r} already exists")
        row = _new_row(identifier, title, purpose, description, notes, status)
        session.add(row)
        session.flush()

    if status != "planned":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_edges(session, row.conversation_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.conversation_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_conversation(
    session: Session,
    identifier: str,
    *,
    conversation_identifier: str | None = None,
    title: str | None = None,
    purpose: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if (
        conversation_identifier is not None
        and conversation_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "conversation_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="conversation_title")
    purpose = gov.require_nonempty(purpose, field="conversation_purpose")
    description = gov.require_nonempty(
        description, field="conversation_description"
    )
    if title.lower() != row.conversation_title.lower():
        _reject_duplicate_title(session, title, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.conversation_status:
        _require_status(status)
        gov.check_transition(
            row.conversation_status, status, CONVERSATION_STATUS_TRANSITIONS
        )
        row.conversation_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.conversation_title = title
    row.conversation_purpose = purpose
    row.conversation_description = description
    row.conversation_notes = notes
    session.flush()
    _validate_edges(session, identifier, row.conversation_status)

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


def patch_conversation(
    session: Session, identifier: str, *, references: list[dict] | None = None, **fields
) -> dict:
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

    gov.apply_reference_list(session, references)

    if "title" in fields:
        title = gov.require_nonempty(fields["title"], field="conversation_title")
        if title.lower() != row.conversation_title.lower():
            _reject_duplicate_title(session, title, exclude_identifier=identifier)
        row.conversation_title = title
    if "purpose" in fields:
        row.conversation_purpose = gov.require_nonempty(
            fields["purpose"], field="conversation_purpose"
        )
    if "description" in fields:
        row.conversation_description = gov.require_nonempty(
            fields["description"], field="conversation_description"
        )
    if "notes" in fields:
        row.conversation_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.conversation_status:
            gov.check_transition(
                row.conversation_status, status, CONVERSATION_STATUS_TRANSITIONS
            )
            row.conversation_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    session.flush()
    _validate_edges(session, identifier, row.conversation_status)

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


def delete_conversation(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.conversation_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.conversation_deleted_at = datetime.now(UTC)
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


def restore_conversation(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.conversation_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "conversation_deleted_at",
                    "not_deleted",
                    "conversation is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.conversation_deleted_at = None
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
