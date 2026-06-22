"""Field mapping endpoints — PI-255 (PRJ-027).

Field-level source-mapping decisions (``FMP-NNN``) subordinate to an
entity-level ``source_mapping``. The standard methodology routes plus a
``/{identifier}/mark-stale`` lifecycle action. Each delegates to
:mod:`crmbuilder_v2.access.repositories.field_mapping`; bodies use the
parent-prefixed ``field_mapping_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``layouts.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import field_mapping
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FieldMappingCreateIn,
    FieldMappingPatchIn,
    FieldMappingReplaceIn,
    MarkStaleIn,
)

router = APIRouter(prefix="/field-mappings", tags=["field-mappings"])

_PREFIX = "field_mapping_"


@router.get("")
def list_all(
    source_mapping_identifier: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            field_mapping.list_field_mappings(
                s,
                source_mapping_identifier=source_mapping_identifier,
                status=status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FMP-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": field_mapping.next_field_mapping_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = field_mapping.get_field_mapping(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("field_mapping", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FieldMappingCreateIn):
    with writable_session() as s:
        return ok(
            field_mapping.create_field_mapping(
                s,
                source_mapping_identifier=(
                    body.field_mapping_source_mapping_identifier
                ),
                source_field_name=body.field_mapping_source_field_name,
                decision_type=body.field_mapping_decision_type,
                target_entity_identifier=(
                    body.field_mapping_target_entity_identifier
                ),
                target_field_identifier=(
                    body.field_mapping_target_field_identifier
                ),
                notes=body.field_mapping_notes,
                identifier=body.field_mapping_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FieldMappingReplaceIn):
    with writable_session() as s:
        return ok(
            field_mapping.update_field_mapping(
                s,
                identifier,
                source_field_name=body.field_mapping_source_field_name,
                decision_type=body.field_mapping_decision_type,
                status=body.field_mapping_status,
                target_entity_identifier=(
                    body.field_mapping_target_entity_identifier
                ),
                target_field_identifier=(
                    body.field_mapping_target_field_identifier
                ),
                notes=body.field_mapping_notes,
                stale_reason=body.field_mapping_stale_reason,
                stale_severity=body.field_mapping_stale_severity,
                superseded_by=body.field_mapping_superseded_by,
                resolved_at=body.field_mapping_resolved_at,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FieldMappingPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged). The prefix is stripped to the repo's
    # patchable kwargs.
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_PREFIX):] if key.startswith(_PREFIX) else key: value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(field_mapping.patch_field_mapping(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(field_mapping.delete_field_mapping(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(field_mapping.restore_field_mapping(s, identifier))


@router.post("/{identifier}/mark-stale")
def mark_stale(identifier: str, body: MarkStaleIn):
    """Transition the mapping to ``stale`` with a graded reason + severity."""
    with writable_session() as s:
        return ok(
            field_mapping.mark_stale(
                s, identifier, reason=body.reason, severity=body.severity
            )
        )
