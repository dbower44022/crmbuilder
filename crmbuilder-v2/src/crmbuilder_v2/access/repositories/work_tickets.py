"""Work ticket repository — the fourth governance entity type (UI v0.7).

Per ``governance-schema-specs/work_ticket.md``. Five-status workflow
lifecycle (drafted → ready → consumed plus two terminals). Access-layer
edge rules:

* **Single-use** — a work_ticket may carry at most one inbound
  ``conversation_opens_against_work_ticket`` edge at any status (DEC-117
  family-2 definition); a second returns ``work_ticket_single_use_violation``.
* **Consumed-requires-edge** — ``consumed`` requires that inbound edge to be
  present (DEC-143, the inverse of supersession-requires-edge).
* **Supersession-requires-edge** — ``superseded`` requires an outbound
  ``supersedes`` edge.

Closed four-value kind enum; repo-relative ``work_ticket_file_path``.
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
from crmbuilder_v2.access.models import WorkTicket
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    WORK_TICKET_KINDS,
    WORK_TICKET_STATUS_TRANSITIONS,
    WORK_TICKET_STATUSES,
)

_ENTITY_TYPE = "work_ticket"
_IDENTIFIER_PREFIX = "WT"
_IDENTIFIER_RE = re.compile(r"^WT-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_CONSUMPTION_KIND = "conversation_opens_against_work_ticket"
_PATCHABLE_FIELDS = frozenset(
    {"title", "description", "notes", "kind", "status", "file_path"}
)

_STATUS_TIMESTAMP = {
    "ready": "work_ticket_ready_at",
    "consumed": "work_ticket_consumed_at",
    "cancelled": "work_ticket_cancelled_at",
    "superseded": "work_ticket_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, WORK_TICKET_STATUSES, field="work_ticket_status")


def _require_kind(kind: object) -> str:
    return gov.require_in(kind, WORK_TICKET_KINDS, field="work_ticket_kind")


def _reject_duplicate_title(
    session: Session, title: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(WorkTicket).where(
        func.lower(WorkTicket.work_ticket_title) == title.lower(),
        WorkTicket.work_ticket_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(WorkTicket.work_ticket_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "work_ticket_title",
                    "duplicate",
                    f"a work_ticket titled {title!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> WorkTicket:
    row = session.get(WorkTicket, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_edges(session: Session, identifier: str, status: str) -> None:
    consumption = gov.inbound_edges(
        session,
        target_type=_ENTITY_TYPE,
        target_id=identifier,
        relationship=_CONSUMPTION_KIND,
    )
    if len(consumption) > 1:
        raise UnprocessableError(
            [
                FieldError(
                    "references",
                    "work_ticket_single_use_violation",
                    "a work_ticket admits at most one consumption edge",
                )
            ]
        )
    if status == "consumed" and len(consumption) != 1:
        raise UnprocessableError(
            [
                FieldError(
                    "status",
                    "consumed_work_ticket_requires_consumption_edge",
                    "an inbound 'conversation_opens_against_work_ticket' edge is required",
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


def list_work_tickets(
    session: Session,
    *,
    include_deleted: bool = False,
    kind: str | None = None,
    status: str | None = None,
) -> list[dict]:
    stmt = select(WorkTicket).order_by(WorkTicket.work_ticket_identifier)
    if not include_deleted:
        stmt = stmt.where(WorkTicket.work_ticket_deleted_at.is_(None))
    if kind is not None:
        stmt = stmt.where(WorkTicket.work_ticket_kind == kind)
    if status is not None:
        stmt = stmt.where(WorkTicket.work_ticket_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_work_ticket(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = session.get(WorkTicket, identifier)
    if row is None:
        return None
    if row.work_ticket_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_work_ticket_identifier(session: Session) -> str:
    identifiers = session.scalars(select(WorkTicket.work_ticket_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier, title, description, notes, kind, status, file_path):
    return WorkTicket(
        work_ticket_identifier=identifier,
        work_ticket_title=title,
        work_ticket_description=description,
        work_ticket_notes=notes,
        work_ticket_kind=kind,
        work_ticket_status=status,
        work_ticket_file_path=file_path,
    )


def _insert_with_autoassign(
    session, title, description, notes, kind, status, file_path
):
    candidate = next_work_ticket_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate, title, description, notes, kind, status, file_path
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
        "could not assign a unique work_ticket identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_work_ticket(
    session: Session,
    *,
    title: str,
    description: str,
    kind: str,
    file_path: str,
    notes: str | None = None,
    status: str = "drafted",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="work_ticket_title")
    description = gov.require_nonempty(description, field="work_ticket_description")
    kind = _require_kind(kind)
    file_path = gov.require_repo_relative_path(
        file_path, field="work_ticket_file_path"
    )
    if status is None:
        status = "drafted"
    _require_status(status)
    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, notes, kind, status, file_path
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="work_ticket_identifier", example="WT-001",
        )
        if session.get(WorkTicket, identifier) is not None:
            raise ConflictError(f"work_ticket {identifier!r} already exists")
        row = _new_row(
            identifier, title, description, notes, kind, status, file_path
        )
        session.add(row)
        session.flush()

    if status != "drafted":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_edges(session, row.work_ticket_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.work_ticket_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_work_ticket(
    session: Session,
    identifier: str,
    *,
    work_ticket_identifier: str | None = None,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    file_path: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if (
        work_ticket_identifier is not None
        and work_ticket_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "work_ticket_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="work_ticket_title")
    description = gov.require_nonempty(description, field="work_ticket_description")
    kind = _require_kind(kind)
    file_path = gov.require_repo_relative_path(
        file_path, field="work_ticket_file_path"
    )
    if title.lower() != row.work_ticket_title.lower():
        _reject_duplicate_title(session, title, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.work_ticket_status:
        _require_status(status)
        gov.check_transition(
            row.work_ticket_status, status, WORK_TICKET_STATUS_TRANSITIONS
        )
        row.work_ticket_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.work_ticket_title = title
    row.work_ticket_description = description
    row.work_ticket_notes = notes
    row.work_ticket_kind = kind
    row.work_ticket_file_path = file_path
    session.flush()
    _validate_edges(session, identifier, row.work_ticket_status)

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


def patch_work_ticket(
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
        title = gov.require_nonempty(fields["title"], field="work_ticket_title")
        if title.lower() != row.work_ticket_title.lower():
            _reject_duplicate_title(session, title, exclude_identifier=identifier)
        row.work_ticket_title = title
    if "description" in fields:
        row.work_ticket_description = gov.require_nonempty(
            fields["description"], field="work_ticket_description"
        )
    if "notes" in fields:
        row.work_ticket_notes = fields["notes"]
    if "kind" in fields:
        row.work_ticket_kind = _require_kind(fields["kind"])
    if "file_path" in fields:
        row.work_ticket_file_path = gov.require_repo_relative_path(
            fields["file_path"], field="work_ticket_file_path"
        )
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.work_ticket_status:
            gov.check_transition(
                row.work_ticket_status, status, WORK_TICKET_STATUS_TRANSITIONS
            )
            row.work_ticket_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    session.flush()
    _validate_edges(session, identifier, row.work_ticket_status)

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


def delete_work_ticket(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.work_ticket_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.work_ticket_deleted_at = datetime.now(UTC)
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


def restore_work_ticket(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.work_ticket_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "work_ticket_deleted_at",
                    "not_deleted",
                    "work_ticket is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.work_ticket_deleted_at = None
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
