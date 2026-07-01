"""Source mapping repository — PI-255 entity-level decision (PRJ-027 / SES-230).

An entity-level source mapping (``SMG-NNN``) records how one source entity
discovered by audit relates to the canonical design. Backs the
``/source-mappings`` REST endpoints (Slice 2). Follows the ``instances.py``
pattern: identifier-as-PK, savepoint-retry auto-assignment, change_log emission,
soft-delete / restore. ``status`` moves through a gated lifecycle
(``unresolved`` → ``resolved`` / ``stale`` / ``superseded``); the reconciler
never writes here — candidates do (see ``mapping_candidate.py``).
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
from crmbuilder_v2.access.models import SourceMapping
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    SOURCE_MAPPING_DECISION_TYPES,
    SOURCE_MAPPING_STALE_REASONS,
    SOURCE_MAPPING_STALE_SEVERITIES,
    SOURCE_MAPPING_STATUSES,
)

_ENTITY_TYPE = "source_mapping"
_IDENTIFIER_PREFIX = "SMG"
_IDENTIFIER_RE = re.compile(r"^SMG-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset({"source_entity_name", "decision_type", "notes"})

# unresolved → {resolved, stale, superseded}; resolved → {stale, superseded};
# stale → {resolved, superseded}; superseded is terminal (DEC-454/579).
_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "unresolved": frozenset({"resolved", "stale", "superseded"}),
    "resolved": frozenset({"stale", "superseded"}),
    "stale": frozenset({"resolved", "superseded"}),
    "superseded": frozenset(),
}
_STATUS_TIMESTAMP = {"resolved": "resolved_at"}


def _require_decision_type(value: object) -> str:
    return gov.require_in(
        value, SOURCE_MAPPING_DECISION_TYPES, field="decision_type"
    )


def _require_status(value: object) -> str:
    return gov.require_in(value, SOURCE_MAPPING_STATUSES, field="status")


def _require_stale_reason(value: object) -> str:
    return gov.require_in(
        value, SOURCE_MAPPING_STALE_REASONS, field="stale_reason"
    )


def _require_stale_severity(value: object) -> str:
    return gov.require_in(
        value, SOURCE_MAPPING_STALE_SEVERITIES, field="stale_severity"
    )


def _get_row(session: Session, identifier: str) -> SourceMapping:
    row = get_by_identifier(
        session, SourceMapping, SourceMapping.source_mapping_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_source_mappings(
    session: Session,
    *,
    instance_identifier: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    stmt = select(SourceMapping).order_by(SourceMapping.source_mapping_identifier)
    if not include_deleted:
        stmt = stmt.where(SourceMapping.deleted_at.is_(None))
    if instance_identifier is not None:
        stmt = stmt.where(SourceMapping.instance_identifier == instance_identifier)
    if status is not None:
        stmt = stmt.where(SourceMapping.status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_source_mapping(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(
        session, SourceMapping, SourceMapping.source_mapping_identifier, identifier
    )
    if row is None:
        return None
    if row.deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_source_mapping_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(SourceMapping.source_mapping_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _insert_with_autoassign(session: Session, **kw) -> SourceMapping:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_source_mapping_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = SourceMapping(source_mapping_identifier=candidate, **kw)
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
        "could not assign a unique source_mapping identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_source_mapping(
    session: Session,
    *,
    instance_identifier: str,
    source_entity_name: str,
    decision_type: str,
    notes: str | None = None,
    identifier: str | None = None,
    timestamps: dict | None = None,
) -> dict:
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    source_entity_name = gov.require_nonempty(
        source_entity_name, field="source_entity_name"
    )
    decision_type = _require_decision_type(decision_type)

    kw = {
        "instance_identifier": instance_identifier,
        "source_entity_name": source_entity_name,
        "decision_type": decision_type,
        "status": "unresolved",
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="source_mapping_identifier",
            example="SMG-001",
        )
        if (
            get_by_identifier(
                session,
                SourceMapping,
                SourceMapping.source_mapping_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"source_mapping {identifier!r} already exists")
        row = SourceMapping(source_mapping_identifier=identifier, **kw)
        session.add(row)
        session.flush()

    gov.apply_timestamps(row, timestamps)
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.source_mapping_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_source_mapping(
    session: Session,
    identifier: str,
    *,
    source_entity_name: str,
    decision_type: str,
    status: str,
    notes: str | None = None,
    stale_reason: str | None = None,
    stale_severity: str | None = None,
    superseded_by: str | None = None,
    resolved_at: object | None = None,
) -> dict:
    row = _get_row(session, identifier)
    before = to_dict(row)

    requested_status = _require_status(status)
    gov.check_transition(row.status, requested_status, _STATUS_TRANSITIONS)

    row.source_entity_name = gov.require_nonempty(
        source_entity_name, field="source_entity_name"
    )
    row.decision_type = _require_decision_type(decision_type)
    row.status = requested_status
    row.notes = notes
    row.stale_reason = (
        _require_stale_reason(stale_reason) if stale_reason is not None else None
    )
    row.stale_severity = (
        _require_stale_severity(stale_severity)
        if stale_severity is not None
        else None
    )
    row.superseded_by = superseded_by
    if resolved_at is not None:
        row.resolved_at = gov.coerce_datetime(resolved_at, field="resolved_at")
    gov.set_status_timestamp(row, requested_status, _STATUS_TIMESTAMP)
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


def patch_source_mapping(
    session: Session, identifier: str, **fields
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

    if "source_entity_name" in fields:
        row.source_entity_name = gov.require_nonempty(
            fields["source_entity_name"], field="source_entity_name"
        )
    if "decision_type" in fields:
        row.decision_type = _require_decision_type(fields["decision_type"])
    if "notes" in fields:
        row.notes = fields["notes"]

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


def mark_stale(
    session: Session, identifier: str, *, reason: str, severity: str
) -> dict:
    row = _get_row(session, identifier)
    before = to_dict(row)
    gov.check_transition(row.status, "stale", _STATUS_TRANSITIONS)
    row.status = "stale"
    row.stale_reason = _require_stale_reason(reason)
    row.stale_severity = _require_stale_severity(severity)
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


def delete_source_mapping(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.deleted_at = datetime.now(UTC)
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


def restore_source_mapping(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "deleted_at",
                    "not_deleted",
                    "source_mapping is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.deleted_at = None
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
