"""Workstream repository — the first governance entity type (UI v0.7).

Per ``governance-schema-specs/workstream.md``. Eight module-level functions
back the ``/workstreams`` REST endpoints and the desktop panel, plus the
``WS-NNN`` allocator helper. Five-status workflow lifecycle with truly
-terminal terminals; the ``superseded`` terminal requires an outbound
``supersedes`` edge (DEC-125). Per-status lifecycle timestamps are server
-set on transition; client-supplied values are ignored except on a
backfill create (a create with a non-default status accepts the matching
lifecycle timestamps verbatim).
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
from crmbuilder_v2.access.models import Workstream
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    WORKSTREAM_STATUS_TRANSITIONS,
    WORKSTREAM_STATUSES,
)

_ENTITY_TYPE = "workstream"
_IDENTIFIER_PREFIX = "WS"
_IDENTIFIER_RE = re.compile(r"^WS-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"name", "purpose", "description", "notes", "status"}
)

# status value -> per-status lifecycle timestamp column.
_STATUS_TIMESTAMP = {
    "in_flight": "workstream_started_at",
    "complete": "workstream_completed_at",
    "cancelled": "workstream_cancelled_at",
    "superseded": "workstream_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, WORKSTREAM_STATUSES, field="workstream_status")


def _reject_duplicate_name(
    session: Session, name: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(Workstream).where(
        func.lower(Workstream.workstream_name) == name.lower(),
        Workstream.workstream_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(Workstream.workstream_identifier != exclude_identifier)
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "workstream_name",
                    "duplicate",
                    f"a workstream named {name!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> Workstream:
    row = session.get(Workstream, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _validate_terminal_edges(session: Session, identifier: str, status: str) -> None:
    """Enforce the supersession-requires-edge rule at the access layer."""
    if status == "superseded":
        gov.reject_missing_supersedes_edge(
            session, entity_type=_ENTITY_TYPE, identifier=identifier
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier, name, purpose, description, notes, status) -> Workstream:
    return Workstream(
        workstream_identifier=identifier,
        workstream_name=name,
        workstream_purpose=purpose,
        workstream_description=description,
        workstream_notes=notes,
        workstream_status=status,
    )


def _insert_with_autoassign(session, name, purpose, description, notes, status):
    candidate = next_workstream_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, name, purpose, description, notes, status)
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
    name: str,
    purpose: str,
    description: str,
    notes: str | None = None,
    status: str = "planned",
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a workstream.

    ``status`` defaults to ``planned``. A create with a non-default status
    is the backfill path: the matching lifecycle timestamps may be supplied
    in ``timestamps`` (a dict of column-name → ISO/datetime) and are applied
    verbatim; otherwise the matching status timestamp is server-set to now.
    ``references`` is an optional list of edge specs created in the same
    transaction (used to supply the ``supersedes`` edge for a ``superseded``
    create).
    """
    name = gov.require_nonempty(name, field="workstream_name")
    purpose = gov.require_nonempty(purpose, field="workstream_purpose")
    description = gov.require_nonempty(description, field="workstream_description")
    if status is None:
        status = "planned"
    _require_status(status)
    _reject_duplicate_name(session, name)

    if identifier is None:
        row = _insert_with_autoassign(
            session, name, purpose, description, notes, status
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="workstream_identifier",
            example="WS-001",
        )
        if session.get(Workstream, identifier) is not None:
            raise ConflictError(f"workstream {identifier!r} already exists")
        row = _new_row(identifier, name, purpose, description, notes, status)
        session.add(row)
        session.flush()

    # Backfill lifecycle timestamps (verbatim) or server-set the matching one.
    if status != "planned":
        if timestamps:
            for column, value in timestamps.items():
                setattr(row, column, value)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)
    _validate_terminal_edges(session, row.workstream_identifier, status)

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
    name: str | None = None,
    purpose: str | None = None,
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

    name = gov.require_nonempty(name, field="workstream_name")
    purpose = gov.require_nonempty(purpose, field="workstream_purpose")
    description = gov.require_nonempty(description, field="workstream_description")
    if name.lower() != row.workstream_name.lower():
        _reject_duplicate_name(session, name, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.workstream_status:
        _require_status(status)
        gov.check_transition(
            row.workstream_status, status, WORKSTREAM_STATUS_TRANSITIONS
        )
        row.workstream_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.workstream_name = name
    row.workstream_purpose = purpose
    row.workstream_description = description
    row.workstream_notes = notes
    session.flush()
    _validate_terminal_edges(session, identifier, row.workstream_status)

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

    if "name" in fields:
        name = gov.require_nonempty(fields["name"], field="workstream_name")
        if name.lower() != row.workstream_name.lower():
            _reject_duplicate_name(session, name, exclude_identifier=identifier)
        row.workstream_name = name
    if "purpose" in fields:
        row.workstream_purpose = gov.require_nonempty(
            fields["purpose"], field="workstream_purpose"
        )
    if "description" in fields:
        row.workstream_description = gov.require_nonempty(
            fields["description"], field="workstream_description"
        )
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
    _validate_terminal_edges(session, identifier, row.workstream_status)

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
