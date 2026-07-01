"""Close-out payload repository — the fifth governance entity type (UI v0.7).

Per ``governance-schema-specs/close_out_payload.md`` v1.1. Five-status
workflow lifecycle (drafted → ready → applied plus two terminals).
Access-layer edge rules:

* **Production edge** — exactly one outbound
  ``close_out_payload_produced_by_conversation`` edge is required at every
  status (DEC-117 family-3 definition); zero returns
  ``payload_requires_producing_conversation_edge``, more than one returns
  ``payload_single_producer_violation``.
* **Applied-requires-edge** — ``applied`` requires at least one inbound
  ``deposit_event_applies_close_out_payload`` edge from a ``success``
  deposit_event (DEC-149). The canonical transition is driven atomically by
  the deposit_event POST (see :mod:`deposit_events`); this rule guards
  direct manipulation.
* **Supersession-requires-edge** — ``superseded`` requires an outbound
  ``supersedes`` edge.
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
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import CloseOutPayload, DepositEvent
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS,
    CLOSE_OUT_PAYLOAD_STATUSES,
)

_ENTITY_TYPE = "close_out_payload"
_IDENTIFIER_PREFIX = "COP"
_IDENTIFIER_RE = re.compile(r"^COP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PRODUCTION_KIND = "close_out_payload_produced_by_conversation"
_APPLY_KIND = "deposit_event_applies_close_out_payload"
_PATCHABLE_FIELDS = frozenset(
    {"title", "description", "notes", "status", "file_path"}
)

_STATUS_TIMESTAMP = {
    "ready": "close_out_payload_ready_at",
    "applied": "close_out_payload_applied_at",
    "cancelled": "close_out_payload_cancelled_at",
    "superseded": "close_out_payload_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(
        status, CLOSE_OUT_PAYLOAD_STATUSES, field="close_out_payload_status"
    )


def _reject_duplicate_title(
    session: Session, title: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(CloseOutPayload).where(
        func.lower(CloseOutPayload.close_out_payload_title) == title.lower(),
        CloseOutPayload.close_out_payload_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            CloseOutPayload.close_out_payload_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "close_out_payload_title",
                    "duplicate",
                    f"a close_out_payload titled {title!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> CloseOutPayload:
    row = get_by_identifier(session, CloseOutPayload, CloseOutPayload.close_out_payload_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _has_successful_apply_edge(session: Session, identifier: str) -> bool:
    edges = gov.inbound_edges(
        session,
        target_type=_ENTITY_TYPE,
        target_id=identifier,
        relationship=_APPLY_KIND,
    )
    for edge in edges:
        dep = get_by_identifier(session, DepositEvent, DepositEvent.deposit_event_identifier, edge.source_id)
        if dep is not None and dep.deposit_event_outcome == "success":
            return True
    return False


def _validate_edges(session: Session, identifier: str, status: str) -> None:
    production = gov.outbound_edges(
        session,
        source_type=_ENTITY_TYPE,
        source_id=identifier,
        relationship=_PRODUCTION_KIND,
    )
    if len(production) == 0:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "payload_requires_producing_conversation_edge",
                    "an outbound 'close_out_payload_produced_by_conversation' edge is required",
                )
            ]
        )
    if len(production) > 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "payload_single_producer_violation",
                    "a payload is produced by exactly one conversation",
                )
            ]
        )
    if status == "applied" and not _has_successful_apply_edge(session, identifier):
        raise UnprocessableError(
            [
                FieldError(
                    "status",
                    "applied_payload_requires_successful_deposit_event_edge",
                    "an inbound success 'deposit_event_applies_close_out_payload' edge is required",
                )
            ]
        )
    if status == "superseded":
        gov.reject_missing_supersedes_edge(
            session,
            entity_type=_ENTITY_TYPE,
            identifier=identifier,
            error_code="superseded_payload_requires_successor_edge",
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_close_out_payloads(
    session: Session, *, include_deleted: bool = False, status: str | None = None
) -> list[dict]:
    stmt = select(CloseOutPayload).order_by(
        CloseOutPayload.close_out_payload_identifier
    )
    if not include_deleted:
        stmt = stmt.where(CloseOutPayload.close_out_payload_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(CloseOutPayload.close_out_payload_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_close_out_payload(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, CloseOutPayload, CloseOutPayload.close_out_payload_identifier, identifier)
    if row is None:
        return None
    if row.close_out_payload_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_close_out_payload_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(CloseOutPayload.close_out_payload_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier, title, description, notes, status, file_path):
    return CloseOutPayload(
        close_out_payload_identifier=identifier,
        close_out_payload_title=title,
        close_out_payload_description=description,
        close_out_payload_notes=notes,
        close_out_payload_status=status,
        close_out_payload_file_path=file_path,
    )


def _insert_with_autoassign(session, title, description, notes, status, file_path):
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_close_out_payload_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, title, description, notes, status, file_path)
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
        "could not assign a unique close_out_payload identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_close_out_payload(
    session: Session,
    *,
    title: str,
    description: str,
    file_path: str,
    notes: str | None = None,
    status: str = "drafted",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="close_out_payload_title")
    description = gov.require_nonempty(
        description, field="close_out_payload_description"
    )
    file_path = gov.require_repo_relative_path(
        file_path, field="close_out_payload_file_path"
    )
    if status is None:
        status = "drafted"
    _require_status(status)
    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, notes, status, file_path
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="close_out_payload_identifier", example="COP-001",
        )
        if get_by_identifier(session, CloseOutPayload, CloseOutPayload.close_out_payload_identifier, identifier) is not None:
            raise ConflictError(
                f"close_out_payload {identifier!r} already exists"
            )
        row = _new_row(identifier, title, description, notes, status, file_path)
        session.add(row)
        session.flush()

    if status != "drafted":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_edges(session, row.close_out_payload_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.close_out_payload_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_close_out_payload(
    session: Session,
    identifier: str,
    *,
    close_out_payload_identifier: str | None = None,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    file_path: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if (
        close_out_payload_identifier is not None
        and close_out_payload_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "close_out_payload_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="close_out_payload_title")
    description = gov.require_nonempty(
        description, field="close_out_payload_description"
    )
    file_path = gov.require_repo_relative_path(
        file_path, field="close_out_payload_file_path"
    )
    if title.lower() != row.close_out_payload_title.lower():
        _reject_duplicate_title(session, title, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.close_out_payload_status:
        _require_status(status)
        gov.check_transition(
            row.close_out_payload_status,
            status,
            CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS,
        )
        row.close_out_payload_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.close_out_payload_title = title
    row.close_out_payload_description = description
    row.close_out_payload_notes = notes
    row.close_out_payload_file_path = file_path
    session.flush()
    _validate_edges(session, identifier, row.close_out_payload_status)

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


def patch_close_out_payload(
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
        title = gov.require_nonempty(
            fields["title"], field="close_out_payload_title"
        )
        if title.lower() != row.close_out_payload_title.lower():
            _reject_duplicate_title(session, title, exclude_identifier=identifier)
        row.close_out_payload_title = title
    if "description" in fields:
        row.close_out_payload_description = gov.require_nonempty(
            fields["description"], field="close_out_payload_description"
        )
    if "notes" in fields:
        row.close_out_payload_notes = fields["notes"]
    if "file_path" in fields:
        row.close_out_payload_file_path = gov.require_repo_relative_path(
            fields["file_path"], field="close_out_payload_file_path"
        )
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.close_out_payload_status:
            gov.check_transition(
                row.close_out_payload_status,
                status,
                CLOSE_OUT_PAYLOAD_STATUS_TRANSITIONS,
            )
            row.close_out_payload_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    session.flush()
    _validate_edges(session, identifier, row.close_out_payload_status)

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


def delete_close_out_payload(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.close_out_payload_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.close_out_payload_deleted_at = datetime.now(UTC)
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


def restore_close_out_payload(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.close_out_payload_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "close_out_payload_deleted_at",
                    "not_deleted",
                    "close_out_payload is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.close_out_payload_deleted_at = None
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
