"""Value mapping repository — PI-255 value-level decision (PRJ-027 / SES-230).

A value-level mapping decision for an individual source enum value under an
interpreted field mapping. A lightweight child-table repository (integer PK, no
prefixed identifier, no change_log / refs participation), mirroring the
``instance_membership`` pattern. A replaced value mapping is kept and linked via
``superseded_by`` rather than deleted (DEC-579); the access layer enforces a
single active (``superseded_by IS NULL``) row per (field mapping, source value),
since a portable partial-unique index is not available across dialects.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import ValueMapping
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    SOURCE_MAPPING_STATUSES,
    VALUE_MAPPING_DECISION_TYPES,
)

_ENTITY_TYPE = "value_mapping"


def _require_decision_type(value: object) -> str:
    return gov.require_in(
        value, VALUE_MAPPING_DECISION_TYPES, field="decision_type"
    )


def _require_status(value: object) -> str:
    return gov.require_in(value, SOURCE_MAPPING_STATUSES, field="status")


def _get_row(session: Session, id_: int) -> ValueMapping:
    row = session.get(ValueMapping, id_)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, str(id_))
    return row


def _active_for(
    session: Session, field_mapping_identifier: str, source_value: str
) -> ValueMapping | None:
    stmt = select(ValueMapping).where(
        ValueMapping.field_mapping_identifier == field_mapping_identifier,
        ValueMapping.source_value == source_value,
        ValueMapping.superseded_by.is_(None),
    )
    return session.scalars(stmt).first()


def list_value_mappings(
    session: Session,
    *,
    field_mapping_identifier: str,
    include_superseded: bool = False,
) -> list[dict]:
    stmt = (
        select(ValueMapping)
        .where(
            ValueMapping.field_mapping_identifier == field_mapping_identifier
        )
        .order_by(ValueMapping.id)
    )
    if not include_superseded:
        stmt = stmt.where(ValueMapping.superseded_by.is_(None))
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_value_mapping(session: Session, id_: int) -> dict | None:
    row = session.get(ValueMapping, id_)
    return to_dict(row) if row is not None else None


def create_value_mapping(
    session: Session,
    *,
    field_mapping_identifier: str,
    source_value: str,
    decision_type: str,
    target_value: str | None = None,
    notes: str | None = None,
) -> dict:
    field_mapping_identifier = gov.require_nonempty(
        field_mapping_identifier, field="field_mapping_identifier"
    )
    source_value = gov.require_nonempty(source_value, field="source_value")
    decision_type = _require_decision_type(decision_type)

    if _active_for(session, field_mapping_identifier, source_value) is not None:
        raise ConflictError(
            "an active value_mapping already exists for "
            f"{field_mapping_identifier!r} value {source_value!r}"
        )

    row = ValueMapping(
        field_mapping_identifier=field_mapping_identifier,
        source_value=source_value,
        decision_type=decision_type,
        target_value=target_value,
        status="unresolved",
        notes=notes,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def update_value_mapping(
    session: Session,
    id_: int,
    *,
    decision_type: str,
    target_value: str | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> dict:
    row = _get_row(session, id_)
    row.decision_type = _require_decision_type(decision_type)
    row.target_value = target_value
    row.notes = notes
    if status is not None:
        row.status = _require_status(status)
    session.flush()
    return to_dict(row)


def supersede_value_mapping(
    session: Session, id_: int, *, replacement_id: int
) -> dict:
    """Mark a value mapping superseded by a newer row (the chain is preserved)."""
    row = _get_row(session, id_)
    if row.superseded_by is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "superseded_by",
                    "already_superseded",
                    "value_mapping is already superseded",
                )
            ]
        )
    # The replacement must exist.
    _get_row(session, replacement_id)
    row.superseded_by = replacement_id
    row.status = "superseded"
    session.flush()
    return to_dict(row)
