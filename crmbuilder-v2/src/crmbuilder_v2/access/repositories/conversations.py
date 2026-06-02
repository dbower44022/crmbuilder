"""Conversations repository — the topical sub-unit within a session.

Redesigned in PI-073 / DEC-314. Per
``governance-schema-specs/conversation-v2.md`` v1.0.

A conversation is a focused topical discussion within a session — one
session contains 1..N conversations. The new entity uses the ``CNV-NNN``
identifier prefix (distinct from the legacy ``CONV-NNN`` which now
identifies sessions in the redesigned model — see migration 0020).

Six-status lifecycle (forward-only ``planned → in_flight`` plus four
terminals: ``complete``, ``cancelled``, ``not_started``, ``superseded``).

Access-layer edge rules:

* **Session membership** — exactly one outbound
  ``conversation_belongs_to_session`` edge is required on every live
  record per conversation-v2.md §3.3.1.
* **Supersession-requires-edge** — ``superseded`` requires an outbound
  ``supersedes`` edge to the successor conversation.

Cross-session continuity is optional and expressed via two edge kinds:

* ``conversation_follows_from`` — direct successor of a topic carried
  over from a prior conversation (in this or a prior session).
* ``conversation_relates_to`` — looser relation; same topical area, prior
  context, sibling discussion.

These are NOT enforced at create/update time — they're queryable
metadata that operators populate when the topical link exists.
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
    validate_optional_length,
)
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
_IDENTIFIER_PREFIX = "CNV"
_IDENTIFIER_RE = re.compile(r"^CNV-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"title", "purpose", "description", "summary", "notes", "status",
     "executive_summary"}  # PI-105
)

_STATUS_TIMESTAMP = {
    "in_flight": "conversation_in_flight_at",
    "complete": "conversation_completed_at",
    "cancelled": "conversation_cancelled_at",
    "not_started": "conversation_not_started_at",
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
    row = get_by_identifier(session, Conversation, Conversation.conversation_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_edges(session: Session, identifier: str, status: str) -> None:
    """Enforce session membership and supersession edge rules.

    The new conversation entity requires mandatory parent linkage at all
    non-terminal states (and stays linked through the terminal states for
    historical query-ability). Per conversation-v2.md §3.3.1: exactly one
    outbound ``conversation_belongs_to_session`` edge.

    The supersession rule applies only when status == 'superseded'.

    Note: there is no "complete-requires-session-edge" rule (which the
    v0.7 conversation had via ``conversation_records_session``). Under
    the redesign, a conversation belongs to a session at all statuses
    via ``conversation_belongs_to_session`` — the membership IS the
    session linkage, and it's mandatory from create, not deferred to
    complete.
    """
    membership = gov.outbound_edges(
        session,
        source_type=_ENTITY_TYPE,
        source_id=identifier,
        relationship="conversation_belongs_to_session",
    )
    if len(membership) != 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "missing_session_membership_edge",
                    "exactly one conversation_belongs_to_session edge is required",
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
    session_identifier: str | None = None,
) -> list[dict]:
    """List conversations.

    Filters: ``status`` (lifecycle), ``session_identifier`` (resolves the
    inbound conversation_belongs_to_session edge to filter conversations
    that belong to a specific session).
    """
    stmt = select(Conversation).order_by(Conversation.conversation_identifier)
    if not include_deleted:
        stmt = stmt.where(Conversation.conversation_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Conversation.conversation_status == status)
    rows = [to_dict(r) for r in session.scalars(stmt).all()]
    if session_identifier is not None:
        # Find conversations whose conversation_belongs_to_session edge
        # targets the named session.
        members = {
            e.source_id
            for e in gov.inbound_edges(
                session,
                target_type="session",
                target_id=session_identifier,
                relationship="conversation_belongs_to_session",
            )
        }
        rows = [r for r in rows if r["conversation_identifier"] in members]
    return rows


def get_conversation(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Conversation, Conversation.conversation_identifier, identifier)
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


def _new_row(
    identifier: str,
    title: str,
    purpose: str,
    description: str,
    summary: str | None,
    notes: str | None,
    status: str,
    executive_summary: str | None = None,
) -> Conversation:
    return Conversation(
        conversation_identifier=identifier,
        conversation_title=title,
        conversation_purpose=purpose,
        conversation_description=description,
        conversation_summary=summary,
        conversation_notes=notes,
        conversation_status=status,
        conversation_executive_summary=executive_summary,
    )


def _insert_with_autoassign(
    session: Session,
    title: str,
    purpose: str,
    description: str,
    summary: str | None,
    notes: str | None,
    status: str,
    executive_summary: str | None = None,
) -> Conversation:
    candidate = next_conversation_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate, title, purpose, description, summary, notes, status,
            executive_summary,
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
        "could not assign a unique conversation identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_conversation(
    session: Session,
    *,
    title: str,
    purpose: str,
    description: str,
    summary: str | None = None,
    notes: str | None = None,
    status: str = "planned",
    identifier: str | None = None,
    executive_summary: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="conversation_title")
    purpose = gov.require_nonempty(purpose, field="conversation_purpose")
    description = gov.require_nonempty(
        description, field="conversation_description"
    )
    # PI-105: conversation_executive_summary is nullable but length-checked
    # (200-800) when provided — the API schema accepts it but the create
    # path previously dropped it silently.
    executive_summary = validate_optional_length(
        executive_summary,
        field="conversation_executive_summary",
        min_len=200,
        max_len=800,
    )
    if status is None:
        status = "planned"
    _require_status(status)

    if identifier is not None:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="conversation_identifier",
            example="CNV-001",
        )
        if get_by_identifier(session, Conversation, Conversation.conversation_identifier, identifier) is not None:
            raise ConflictError(f"conversation {identifier!r} already exists")

    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, purpose, description, summary, notes, status,
            executive_summary,
        )
    else:
        row = _new_row(
            identifier, title, purpose, description, summary, notes, status,
            executive_summary,
        )
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
    summary: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    executive_summary: str | None = None,
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
    row.conversation_summary = summary
    row.conversation_notes = notes
    # PI-105: PUT replaces the executive summary (nullable, length-checked).
    row.conversation_executive_summary = validate_optional_length(
        executive_summary,
        field="conversation_executive_summary",
        min_len=200,
        max_len=800,
    )
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
    session: Session,
    identifier: str,
    *,
    references: list[dict] | None = None,
    **fields,
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
    if "summary" in fields:
        row.conversation_summary = fields["summary"]
    if "executive_summary" in fields:  # PI-105
        row.conversation_executive_summary = validate_optional_length(
            fields["executive_summary"],
            field="conversation_executive_summary",
            min_len=200,
            max_len=800,
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
