"""Value mapping endpoints — PI-255 (PRJ-027).

Value-level mapping decisions for individual source enum values under an
interpreted field mapping (child table, integer PK, no soft-delete). A replaced
value mapping is kept and linked via ``superseded_by`` (DEC-579). Each delegates
to :mod:`crmbuilder_v2.access.repositories.value_mapping`; responses use the v2
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import value_mapping
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ValueMappingCreateIn,
    ValueMappingSupersedeIn,
    ValueMappingUpdateIn,
)

router = APIRouter(prefix="/value-mappings", tags=["value-mappings"])


@router.get("")
def list_all(field_mapping_identifier: str, include_superseded: bool = False):
    with readonly_session() as s:
        return ok(
            value_mapping.list_value_mappings(
                s,
                field_mapping_identifier=field_mapping_identifier,
                include_superseded=include_superseded,
            )
        )


@router.get("/{id_}")
def get(id_: int):
    with readonly_session() as s:
        record = value_mapping.get_value_mapping(s, id_)
        if record is None:
            raise NotFoundError("value_mapping", str(id_))
        return ok(record)


@router.post("", status_code=201)
def create(body: ValueMappingCreateIn):
    with writable_session() as s:
        return ok(
            value_mapping.create_value_mapping(
                s,
                field_mapping_identifier=body.field_mapping_identifier,
                source_value=body.source_value,
                decision_type=body.decision_type,
                target_value=body.target_value,
                notes=body.notes,
            )
        )


@router.put("/{id_}")
def replace(id_: int, body: ValueMappingUpdateIn):
    with writable_session() as s:
        return ok(
            value_mapping.update_value_mapping(
                s,
                id_,
                decision_type=body.decision_type,
                target_value=body.target_value,
                notes=body.notes,
                status=body.status,
            )
        )


@router.post("/{id_}/supersede")
def supersede(id_: int, body: ValueMappingSupersedeIn):
    """Mark this value mapping superseded by a newer row (chain preserved)."""
    with writable_session() as s:
        return ok(
            value_mapping.supersede_value_mapping(
                s, id_, replacement_id=body.replacement_id
            )
        )
