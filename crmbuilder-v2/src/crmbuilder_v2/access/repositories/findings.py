"""Finding repository — PI-134 reconciliation-gate governance entity (DEC-400).

A finding (``FND-NNN``) is a cross-area coherence problem recorded at the end of
Design (REQ-031..036 / TOP-010). The standard eight CRUD functions back the
``/findings`` REST endpoints, plus the ``FND-NNN`` allocator. ``finding_type``
and ``finding_severity`` are controlled vocabularies; the lifecycle is
open → referred → resolved (REQ-034/035) — only ``resolved`` is terminal and
opens the Develop gate. ``finding_resolved_at`` is server-set on the transition
to ``resolved``. The specifications a finding involves and what resolved it are
``finding_relates_to`` / ``finding_resolved_by`` edges supplied inline via
``references``.
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
from crmbuilder_v2.access.models import Finding
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    FINDING_RESOLUTION_METHODS,
    FINDING_SEVERITIES,
    FINDING_STATUS_TRANSITIONS,
    FINDING_STATUSES,
    FINDING_TYPES,
)

_ENTITY_TYPE = "finding"
_IDENTIFIER_PREFIX = "FND"
_IDENTIFIER_RE = re.compile(r"^FND-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_STATUS_TIMESTAMP = {"resolved": "finding_resolved_at"}
_PATCHABLE_FIELDS = frozenset(
    {
        "type",
        "severity",
        "summary",
        "description",
        "status",
        "resolution",
        "resolution_method",
        "notes",
    }
)


def _require_type(value: object) -> str:
    return gov.require_in(value, FINDING_TYPES, field="finding_type")


def _require_severity(value: object) -> str:
    return gov.require_in(value, FINDING_SEVERITIES, field="finding_severity")


def _require_status(value: object) -> str:
    return gov.require_in(value, FINDING_STATUSES, field="finding_status")


def _check_resolution_method(value: object) -> str | None:
    if value is None:
        return None
    return gov.require_in(
        value, FINDING_RESOLUTION_METHODS, field="finding_resolution_method"
    )


def _get_row(session: Session, identifier: str) -> Finding:
    row = get_by_identifier(session, Finding, Finding.finding_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_findings(
    session: Session,
    *,
    include_deleted: bool = False,
    status: str | None = None,
    severity: str | None = None,
) -> list[dict]:
    stmt = select(Finding).order_by(Finding.finding_identifier)
    if not include_deleted:
        stmt = stmt.where(Finding.finding_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Finding.finding_status == status)
    if severity is not None:
        stmt = stmt.where(Finding.finding_severity == severity)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_finding(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Finding, Finding.finding_identifier, identifier)
    if row is None:
        return None
    if row.finding_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_finding_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Finding.finding_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _new_row(
    identifier,
    type_,
    severity,
    summary,
    description,
    status,
    resolution,
    resolution_method,
    notes,
) -> Finding:
    return Finding(
        finding_identifier=identifier,
        finding_type=type_,
        finding_severity=severity,
        finding_summary=summary,
        finding_description=description,
        finding_status=status,
        finding_resolution=resolution,
        finding_resolution_method=resolution_method,
        finding_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> Finding:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_finding_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **kw)
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
        "could not assign a unique finding identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_finding(
    session: Session,
    *,
    type: str,
    severity: str,
    summary: str,
    description: str | None = None,
    status: str = "open",
    resolution: str | None = None,
    resolution_method: str | None = None,
    notes: str | None = None,
    identifier: str | None = None,
    references: list[dict] | None = None,
    timestamps: dict | None = None,
) -> dict:
    """Create a coherence finding.

    ``references`` typically carries a ``finding_relates_to`` edge to the
    Planning Item (or its Design Workstream / Work Tasks) the finding involves.
    A non-default ``status`` is the backfill path.
    """
    type_ = _require_type(type)
    severity = _require_severity(severity)
    summary = gov.require_nonempty(summary, field="finding_summary")
    if status is None:
        status = "open"
    _require_status(status)
    resolution_method = _check_resolution_method(resolution_method)

    kw = {
        "type_": type_,
        "severity": severity,
        "summary": summary,
        "description": description,
        "status": status,
        "resolution": resolution,
        "resolution_method": resolution_method,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="finding_identifier",
            example="FND-001",
        )
        if get_by_identifier(
            session, Finding, Finding.finding_identifier, identifier
        ) is not None:
            raise ConflictError(f"finding {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()

    if status != "open":
        gov.apply_timestamps(row, timestamps)
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)
    session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.finding_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_finding(
    session: Session,
    identifier: str,
    *,
    finding_identifier: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    summary: str | None = None,
    description: str | None = None,
    status: str | None = None,
    resolution: str | None = None,
    resolution_method: str | None = None,
    notes: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if finding_identifier is not None and finding_identifier != identifier:
        raise UnprocessableError(
            [
                FieldError(
                    "finding_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    type_ = _require_type(type)
    severity = _require_severity(severity)
    summary = gov.require_nonempty(summary, field="finding_summary")
    resolution_method = _check_resolution_method(resolution_method)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.finding_status:
        _require_status(status)
        gov.check_transition(
            row.finding_status, status, FINDING_STATUS_TRANSITIONS
        )
        row.finding_status = status
        gov.set_status_timestamp(row, status, _STATUS_TIMESTAMP)

    row.finding_type = type_
    row.finding_severity = severity
    row.finding_summary = summary
    row.finding_description = description
    row.finding_resolution = resolution
    row.finding_resolution_method = resolution_method
    row.finding_notes = notes
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


def patch_finding(
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

    if "type" in fields:
        row.finding_type = _require_type(fields["type"])
    if "severity" in fields:
        row.finding_severity = _require_severity(fields["severity"])
    if "summary" in fields:
        row.finding_summary = gov.require_nonempty(
            fields["summary"], field="finding_summary"
        )
    if "description" in fields:
        row.finding_description = fields["description"]
    if "resolution" in fields:
        row.finding_resolution = fields["resolution"]
    if "resolution_method" in fields:
        row.finding_resolution_method = _check_resolution_method(
            fields["resolution_method"]
        )
    if "notes" in fields:
        row.finding_notes = fields["notes"]
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.finding_status:
            gov.check_transition(
                row.finding_status, status, FINDING_STATUS_TRANSITIONS
            )
            row.finding_status = status
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


def delete_finding(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.finding_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.finding_deleted_at = datetime.now(UTC)
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


def restore_finding(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.finding_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "finding_deleted_at",
                    "not_deleted",
                    "finding is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.finding_deleted_at = None
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
