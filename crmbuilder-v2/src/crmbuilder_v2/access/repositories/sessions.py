"""Sessions repository — the medium-agnostic communication container.

Redesigned in PI-073 / DEC-314 (supersedes DEC-013's append-only rule).
Per ``governance-schema-specs/session-v2.md`` v1.0.

A session represents one Claude.ai chat, one email, one phone call, one
Zoom meeting, one in-person meeting, or one Slack thread. Sessions are now
schedulable and stateful through a six-status lifecycle (forward-only
``planned → in_flight`` plus four terminals: ``complete``, ``cancelled``,
``not_started``, ``superseded``).

Access-layer edge rules:

* **Project membership** — exactly one outbound
  ``session_belongs_to_project`` edge is required on every live record
  per session-v2.md §3.3.1.
* **Complete-requires-conversation** — ``complete`` requires at least one
  inbound ``conversation_belongs_to_session`` edge per session-v2.md
  §3.4.3 (a complete session contains 1..N conversations; a not_started
  session has zero).
* **Supersession-requires-edge** — ``superseded`` requires an outbound
  ``supersedes`` edge to the successor session.

Per-status lifecycle timestamps are server-set on transition; membership
and terminal edges may be supplied in the same request's ``references``
array and are validated together at commit time.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
    validate_required_length,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Session as SessionModel
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    SESSION_MEDIUMS,
    SESSION_STATUS_TRANSITIONS,
    SESSION_STATUSES,
)

_ENTITY_TYPE = "session"
_IDENTIFIER_PREFIX = "SES"
_IDENTIFIER_RE = re.compile(r"^SES-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
# PI-074 length bounds; column is NOT NULL since PI-075 (migration 0023).
_EXECUTIVE_SUMMARY_MIN = 200
_EXECUTIVE_SUMMARY_MAX = 800
_PATCHABLE_FIELDS = frozenset(
    {
        "title",
        "description",
        "notes",
        "status",
        "medium",
        "scheduled_for",
        "started_at",
        "ended_at",
        "participants",
        "medium_metadata",
        "executive_summary",  # PI-074
    }
)

_STATUS_TIMESTAMP = {
    "in_flight": "session_in_flight_at",
    "complete": "session_completed_at",
    "cancelled": "session_cancelled_at",
    "not_started": "session_not_started_at",
    "superseded": "session_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, SESSION_STATUSES, field="session_status")


def _require_medium(medium: object) -> str:
    return gov.require_in(medium, SESSION_MEDIUMS, field="session_medium")


def _reject_duplicate_title(
    session: DbSession, title: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(SessionModel).where(
        func.lower(SessionModel.session_title) == title.lower(),
        SessionModel.session_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(SessionModel.session_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "session_title",
                    "duplicate",
                    f"a session titled {title!r} already exists",
                )
            ]
        )


def _get_row(session: DbSession, identifier: str) -> SessionModel:
    row = get_by_identifier(session, SessionModel, SessionModel.session_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_edges(session: DbSession, identifier: str, status: str) -> None:
    """Enforce membership, complete, and supersession edge rules."""
    membership = gov.outbound_edges(
        session,
        source_type=_ENTITY_TYPE,
        source_id=identifier,
        relationship="session_belongs_to_project",
    )
    if len(membership) != 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "missing_project_membership_edge",
                    "exactly one session_belongs_to_project edge is required",
                )
            ]
        )
    if status == "complete":
        # Complete sessions must contain at least one conversation
        # (inbound conversation_belongs_to_session edge). Per session-v2.md §3.4.3.
        edges = gov.inbound_edges(
            session,
            target_type=_ENTITY_TYPE,
            target_id=identifier,
            relationship="conversation_belongs_to_session",
        )
        if not edges:
            raise UnprocessableError(
                [
                    FieldError(
                        "session_status",
                        "complete_session_requires_conversation",
                        "a complete session requires at least one inbound 'conversation_belongs_to_session' edge",
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


def list_sessions(
    session: DbSession,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    medium: str | None = None,
    project_identifier: str | None = None,
) -> list[dict]:
    stmt = select(SessionModel).order_by(SessionModel.session_identifier)
    if not include_deleted:
        stmt = stmt.where(SessionModel.session_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(SessionModel.session_status == status)
    if medium is not None:
        stmt = stmt.where(SessionModel.session_medium == medium)
    rows = [to_dict(r) for r in session.scalars(stmt).all()]
    if project_identifier is not None:
        members = {
            e.source_id
            for e in gov.inbound_edges(
                session,
                target_type="project",
                target_id=project_identifier,
                relationship="session_belongs_to_project",
            )
        }
        rows = [r for r in rows if r["session_identifier"] in members]
    return rows


def get_session(
    session: DbSession, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, SessionModel, SessionModel.session_identifier, identifier)
    if row is None:
        return None
    if row.session_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_session_identifier(session: DbSession) -> str:
    identifiers = session.scalars(select(SessionModel.session_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier: str,
    title: str,
    description: str,
    notes: str | None,
    status: str,
    medium: str,
    scheduled_for: datetime | None,
    started_at: datetime | None,
    ended_at: datetime | None,
    participants: list,
    medium_metadata: dict,
    executive_summary: str,
) -> SessionModel:
    return SessionModel(
        session_identifier=identifier,
        session_title=title,
        session_description=description,
        session_notes=notes,
        session_status=status,
        session_medium=medium,
        session_scheduled_for=scheduled_for,
        session_started_at=started_at,
        session_ended_at=ended_at,
        session_participants=participants,
        session_medium_metadata=medium_metadata,
        session_executive_summary=executive_summary,
    )


def _insert_with_autoassign(
    session: DbSession,
    title: str,
    description: str,
    notes: str | None,
    status: str,
    medium: str,
    scheduled_for: datetime | None,
    started_at: datetime | None,
    ended_at: datetime | None,
    participants: list,
    medium_metadata: dict,
    executive_summary: str,
) -> SessionModel:
    candidate = next_session_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate,
            title,
            description,
            notes,
            status,
            medium,
            scheduled_for,
            started_at,
            ended_at,
            participants,
            medium_metadata,
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
        "could not assign a unique session identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def _coerce_datetime_optional(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    return gov.coerce_datetime(value, field=field)


def _coerce_participants(value: object) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise UnprocessableError(
            [
                FieldError(
                    "session_participants",
                    "invalid_type",
                    "must be a JSON array",
                )
            ]
        )
    return value


def _coerce_medium_metadata(value: object) -> dict:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "session_medium_metadata",
                    "invalid_type",
                    "must be a JSON object",
                )
            ]
        )
    return value


def create_session(
    session: DbSession,
    *,
    title: str,
    description: str,
    medium: str,
    notes: str | None = None,
    status: str = "planned",
    scheduled_for: object = None,
    started_at: object = None,
    ended_at: object = None,
    participants: object = None,
    medium_metadata: object = None,
    executive_summary: str,
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a session.

    ``identifier`` is server-assigned when omitted (``None``). When
    supplied it must match ``^SES-\\d{3}$`` and not already exist.

    ``session_executive_summary`` (PI-074) is required since PI-075
    (migration 0023 tightened the column to NOT NULL): a 200-800
    character audience-facing summary.
    """
    title = gov.require_nonempty(title, field="session_title")
    description = gov.require_nonempty(description, field="session_description")
    medium = _require_medium(medium)
    executive_summary = validate_required_length(
        executive_summary,
        field="session_executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )
    if status is None:
        status = "planned"
    _require_status(status)

    scheduled_for_dt = _coerce_datetime_optional(scheduled_for, "session_scheduled_for")
    started_at_dt = _coerce_datetime_optional(started_at, "session_started_at")
    ended_at_dt = _coerce_datetime_optional(ended_at, "session_ended_at")
    participants_list = _coerce_participants(participants)
    medium_metadata_dict = _coerce_medium_metadata(medium_metadata)

    # Identifier-collision check before duplicate-title check, so a re-apply
    # of the same payload SKIPs cleanly rather than 422-ing on title.
    if identifier is not None:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="session_identifier",
            example="SES-001",
        )
        if get_by_identifier(session, SessionModel, SessionModel.session_identifier, identifier) is not None:
            raise ConflictError(f"session {identifier!r} already exists")

    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session,
            title,
            description,
            notes,
            status,
            medium,
            scheduled_for_dt,
            started_at_dt,
            ended_at_dt,
            participants_list,
            medium_metadata_dict,
            executive_summary,
        )
    else:
        row = _new_row(
            identifier,
            title,
            description,
            notes,
            status,
            medium,
            scheduled_for_dt,
            started_at_dt,
            ended_at_dt,
            participants_list,
            medium_metadata_dict,
            executive_summary,
        )
        session.add(row)
        session.flush()

    if status != "planned":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_edges(session, row.session_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.session_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_session(
    session: DbSession,
    identifier: str,
    *,
    session_identifier: str | None = None,
    title: str | None = None,
    description: str | None = None,
    medium: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    scheduled_for: object = None,
    started_at: object = None,
    ended_at: object = None,
    participants: object = None,
    medium_metadata: object = None,
    executive_summary: str,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if session_identifier is not None and session_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "session_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="session_title")
    description = gov.require_nonempty(description, field="session_description")
    medium = _require_medium(medium)
    executive_summary = validate_required_length(
        executive_summary,
        field="session_executive_summary",
        min_len=_EXECUTIVE_SUMMARY_MIN,
        max_len=_EXECUTIVE_SUMMARY_MAX,
    )
    if title.lower() != row.session_title.lower():
        _reject_duplicate_title(session, title, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.session_status:
        _require_status(status)
        gov.check_transition(
            row.session_status, status, SESSION_STATUS_TRANSITIONS
        )
        row.session_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.session_title = title
    row.session_description = description
    row.session_medium = medium
    row.session_notes = notes
    row.session_scheduled_for = _coerce_datetime_optional(scheduled_for, "session_scheduled_for")
    row.session_started_at = _coerce_datetime_optional(started_at, "session_started_at")
    row.session_ended_at = _coerce_datetime_optional(ended_at, "session_ended_at")
    row.session_participants = _coerce_participants(participants)
    row.session_medium_metadata = _coerce_medium_metadata(medium_metadata)
    row.session_executive_summary = executive_summary
    session.flush()
    _validate_edges(session, identifier, row.session_status)

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


def patch_session(
    session: DbSession,
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
        title = gov.require_nonempty(fields["title"], field="session_title")
        if title.lower() != row.session_title.lower():
            _reject_duplicate_title(session, title, exclude_identifier=identifier)
        row.session_title = title
    if "description" in fields:
        row.session_description = gov.require_nonempty(
            fields["description"], field="session_description"
        )
    if "medium" in fields:
        row.session_medium = _require_medium(fields["medium"])
    if "notes" in fields:
        row.session_notes = fields["notes"]
    if "scheduled_for" in fields:
        row.session_scheduled_for = _coerce_datetime_optional(
            fields["scheduled_for"], "session_scheduled_for"
        )
    if "started_at" in fields:
        row.session_started_at = _coerce_datetime_optional(
            fields["started_at"], "session_started_at"
        )
    if "ended_at" in fields:
        row.session_ended_at = _coerce_datetime_optional(
            fields["ended_at"], "session_ended_at"
        )
    if "participants" in fields:
        row.session_participants = _coerce_participants(fields["participants"])
    if "medium_metadata" in fields:
        row.session_medium_metadata = _coerce_medium_metadata(fields["medium_metadata"])
    if "executive_summary" in fields:
        # NOT NULL since PI-075 — a present value must be a valid
        # 200-800 char string; the column cannot be cleared via patch.
        row.session_executive_summary = validate_required_length(
            fields["executive_summary"],
            field="session_executive_summary",
            min_len=_EXECUTIVE_SUMMARY_MIN,
            max_len=_EXECUTIVE_SUMMARY_MAX,
        )
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.session_status:
            gov.check_transition(
                row.session_status, status, SESSION_STATUS_TRANSITIONS
            )
            row.session_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    session.flush()
    _validate_edges(session, identifier, row.session_status)

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


def delete_session(session: DbSession, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.session_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.session_deleted_at = datetime.now(UTC)
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


def restore_session(session: DbSession, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.session_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "session_deleted_at",
                    "not_deleted",
                    "session is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.session_deleted_at = None
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


# ---------------------------------------------------------------------------
# Legacy compatibility shims (for callers still on the pre-redesign API)
# ---------------------------------------------------------------------------
# The pre-redesign sessions repo exposed `create(...)`, `get(...)`, `list_all(...)`,
# `delete(...)`, `upsert(...)`, and `compute_next_identifier(...)`. The API
# routers and CLI callers will be ported to the new names in Phase C; until
# then these shims keep imports valid. They raise NotImplementedError so any
# accidental use surfaces loudly rather than silently writing wrong data.


def compute_next_identifier(session: DbSession) -> str:
    return next_session_identifier(session)


def get(session: DbSession, identifier: str) -> dict:
    row = get_session(session, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def list_all(session: DbSession, *, limit: int | None = None) -> list[dict]:
    rows = list_sessions(session)
    if limit is not None:
        rows = rows[:limit]
    return rows


def create(session: DbSession, **kwargs) -> dict:
    """Pre-redesign signature shim — raises to make breakage loud.

    The pre-redesign create accepted (title, session_date, status,
    conversation_reference, topics_covered, summary, artifacts_produced,
    in_flight_at_end). The new shape is different. Callers must port to
    ``create_session(title=..., description=..., medium=..., ...)``.
    """
    raise NotImplementedError(
        "sessions.create() is removed in PI-073. Use create_session() with "
        "the new shape: title, description, medium, [status, scheduled_for, "
        "started_at, ended_at, participants, medium_metadata, identifier, "
        "references, timestamps]."
    )


def delete(session: DbSession, identifier: str) -> dict:
    return delete_session(session, identifier)


def upsert(session: DbSession, *, identifier: str, **fields) -> dict:
    """Bootstrap-only idempotent insert. Raises on new-shape callers."""
    raise NotImplementedError(
        "sessions.upsert() is removed in PI-073. Use create_session() with "
        "identifier= and the new shape, or get_session() first to check existence."
    )
