"""Workstream (delivery-phase) repository — PI-112 Phase 4 governance entity.

The NEW "Workstream": a single delivery phase of one Planning Item (the old
thematic container was renamed Project). Eight functions back the
``/workstreams`` REST endpoints, plus the ``WSK-NNN`` allocator. Lifecycle is
Planned → In Progress → Complete with a Blocked side-state; the two active
timestamps are server-set on transition. Membership in a Planning Item is a
``workstream_belongs_to_planning_item`` edge supplied inline via ``references``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
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
from crmbuilder_v2.access.models import Workstream
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    WORKSTREAM_PHASE_TYPES,
    WORKSTREAM_STATUS_TRANSITIONS,
    WORKSTREAM_STATUSES,
)

_ENTITY_TYPE = "workstream"
_IDENTIFIER_PREFIX = "WSK"
_IDENTIFIER_RE = re.compile(r"^WSK-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"phase_type", "title", "description", "notes", "status"}
)
_STATUS_TIMESTAMP = {
    "In Progress": "workstream_started_at",
    "Complete": "workstream_completed_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, WORKSTREAM_STATUSES, field="workstream_status")


def _require_phase_type(phase_type: object) -> str:
    return gov.require_in(
        phase_type, WORKSTREAM_PHASE_TYPES, field="workstream_phase_type"
    )


def _get_row(session: Session, identifier: str) -> Workstream:
    row = session.get(Workstream, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_workstreams(
    session: Session, *, include_deleted: bool = False, status: str | None = None
) -> list[dict]:
    stmt = select(Workstream).order_by(Workstream.workstream_identifier)
    if not include_deleted:
        stmt = stmt.where(Workstream.workstream_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Workstream.workstream_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_workstream(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = session.get(Workstream, identifier)
    if row is None:
        return None
    if row.workstream_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_workstream_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Workstream.workstream_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _new_row(identifier, phase_type, title, description, notes, status) -> Workstream:
    return Workstream(
        workstream_identifier=identifier,
        workstream_phase_type=phase_type,
        workstream_title=title,
        workstream_description=description,
        workstream_notes=notes,
        workstream_status=status,
    )


def _insert_with_autoassign(session, phase_type, title, description, notes, status):
    candidate = next_workstream_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, phase_type, title, description, notes, status)
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
        "could not assign a unique workstream identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_workstream(
    session: Session,
    *,
    phase_type: str,
    title: str,
    description: str | None = None,
    notes: str | None = None,
    status: str = "Planned",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a delivery-phase workstream.

    ``references`` typically carries the
    ``workstream_belongs_to_planning_item`` edge to its parent Planning Item.
    A non-default ``status`` is the backfill path (matching lifecycle
    timestamps applied verbatim from ``timestamps`` or server-set to now).
    """
    phase_type = _require_phase_type(phase_type)
    title = gov.require_nonempty(title, field="workstream_title")
    if status is None:
        status = "Planned"
    _require_status(status)

    if identifier is None:
        row = _insert_with_autoassign(
            session, phase_type, title, description, notes, status
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="workstream_identifier",
            example="WSK-001",
        )
        if session.get(Workstream, identifier) is not None:
            raise ConflictError(f"workstream {identifier!r} already exists")
        row = _new_row(identifier, phase_type, title, description, notes, status)
        session.add(row)
        session.flush()

    if status != "Planned":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.workstream_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_workstream(
    session: Session,
    identifier: str,
    *,
    workstream_identifier: str | None = None,
    phase_type: str | None = None,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    status: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if workstream_identifier is not None and workstream_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "workstream_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    phase_type = _require_phase_type(phase_type)
    title = gov.require_nonempty(title, field="workstream_title")

    gov.apply_reference_list(session, references)

    if status is not None and status != row.workstream_status:
        _require_status(status)
        gov.check_transition(
            row.workstream_status, status, WORKSTREAM_STATUS_TRANSITIONS
        )
        row.workstream_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.workstream_phase_type = phase_type
    row.workstream_title = title
    row.workstream_description = description
    row.workstream_notes = notes
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


def patch_workstream(
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

    if "phase_type" in fields:
        row.workstream_phase_type = _require_phase_type(fields["phase_type"])
    if "title" in fields:
        row.workstream_title = gov.require_nonempty(
            fields["title"], field="workstream_title"
        )
    if "description" in fields:
        row.workstream_description = fields["description"]
    if "notes" in fields:
        row.workstream_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.workstream_status:
            gov.check_transition(
                row.workstream_status, status, WORKSTREAM_STATUS_TRANSITIONS
            )
            row.workstream_status = status
            gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

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


def delete_workstream(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.workstream_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.workstream_deleted_at = datetime.now(UTC)
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


def restore_workstream(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.workstream_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "workstream_deleted_at",
                    "not_deleted",
                    "workstream is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.workstream_deleted_at = None
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
