"""Association mapping repository — PI-255 relationship-level decision (DEC-654).

A relationship-level source mapping (``AMP-NNN``), parallel to ``field_mapping``
but top-level: keyed to the source instance (not a parent ``source_mapping``),
it declares which canonical association a discovered source relationship maps to,
via one of three decision types (direct / referential / rejected — no
decomposition). Mirrors ``source_mapping.py`` / ``field_mapping.py``
(identifier-as-PK, savepoint-retry auto-assignment, change_log, soft-delete) and
shares the source-mapping gated status lifecycle.
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
    UnprocessableError,
)
from crmbuilder_v2.access.models import AssociationMapping
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    ASSOCIATION_MAPPING_DECISION_TYPES,
    SOURCE_MAPPING_STALE_REASONS,
    SOURCE_MAPPING_STALE_SEVERITIES,
    SOURCE_MAPPING_STATUSES,
)

_ENTITY_TYPE = "association_mapping"
_IDENTIFIER_PREFIX = "AMP"
_IDENTIFIER_RE = re.compile(r"^AMP-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {
        "source_association_name",
        "decision_type",
        "target_association_identifier",
        "notes",
    }
)

_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "unresolved": frozenset({"resolved", "stale", "superseded"}),
    "resolved": frozenset({"stale", "superseded"}),
    "stale": frozenset({"resolved", "superseded"}),
    "superseded": frozenset(),
}
_STATUS_TIMESTAMP = {"resolved": "resolved_at"}


def _require_decision_type(value: object) -> str:
    return gov.require_in(
        value, ASSOCIATION_MAPPING_DECISION_TYPES, field="decision_type"
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


def _get_row(session: Session, identifier: str) -> AssociationMapping:
    row = get_by_identifier(
        session,
        AssociationMapping,
        AssociationMapping.association_mapping_identifier,
        identifier,
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# --- reads ------------------------------------------------------------------


def list_association_mappings(
    session: Session,
    *,
    instance_identifier: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    stmt = select(AssociationMapping).order_by(
        AssociationMapping.association_mapping_identifier
    )
    if not include_deleted:
        stmt = stmt.where(AssociationMapping.deleted_at.is_(None))
    if instance_identifier is not None:
        stmt = stmt.where(
            AssociationMapping.instance_identifier == instance_identifier
        )
    if status is not None:
        stmt = stmt.where(AssociationMapping.status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_association_mapping(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(
        session,
        AssociationMapping,
        AssociationMapping.association_mapping_identifier,
        identifier,
    )
    if row is None:
        return None
    if row.deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_association_mapping_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(AssociationMapping.association_mapping_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# --- writes -----------------------------------------------------------------


def _insert_with_autoassign(session: Session, **kw) -> AssociationMapping:
    candidate = next_association_mapping_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = AssociationMapping(association_mapping_identifier=candidate, **kw)
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
        "could not assign a unique association_mapping identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_association_mapping(
    session: Session,
    *,
    instance_identifier: str,
    source_association_name: str,
    decision_type: str,
    target_association_identifier: str | None = None,
    notes: str | None = None,
    identifier: str | None = None,
    timestamps: dict | None = None,
) -> dict:
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    source_association_name = gov.require_nonempty(
        source_association_name, field="source_association_name"
    )
    decision_type = _require_decision_type(decision_type)

    kw = {
        "instance_identifier": instance_identifier,
        "source_association_name": source_association_name,
        "decision_type": decision_type,
        "status": "unresolved",
        "target_association_identifier": target_association_identifier,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="association_mapping_identifier",
            example="AMP-001",
        )
        if (
            get_by_identifier(
                session,
                AssociationMapping,
                AssociationMapping.association_mapping_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(
                f"association_mapping {identifier!r} already exists"
            )
        row = AssociationMapping(
            association_mapping_identifier=identifier, **kw
        )
        session.add(row)
        session.flush()

    gov.apply_timestamps(row, timestamps)
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.association_mapping_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_association_mapping(
    session: Session,
    identifier: str,
    *,
    source_association_name: str,
    decision_type: str,
    status: str,
    target_association_identifier: str | None = None,
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

    row.source_association_name = gov.require_nonempty(
        source_association_name, field="source_association_name"
    )
    row.decision_type = _require_decision_type(decision_type)
    row.status = requested_status
    row.target_association_identifier = target_association_identifier
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


def patch_association_mapping(
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

    if "source_association_name" in fields:
        row.source_association_name = gov.require_nonempty(
            fields["source_association_name"], field="source_association_name"
        )
    if "decision_type" in fields:
        row.decision_type = _require_decision_type(fields["decision_type"])
    if "target_association_identifier" in fields:
        row.target_association_identifier = fields[
            "target_association_identifier"
        ]
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


def delete_association_mapping(session: Session, identifier: str) -> dict:
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


def restore_association_mapping(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "deleted_at",
                    "not_deleted",
                    "association_mapping is not soft-deleted",
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
