"""Source mapping endpoints — PI-255 (PRJ-027).

Entity-level source-mapping decisions (``SMG-NNN``). The standard methodology
routes plus a ``/{identifier}/mark-stale`` lifecycle action. Each delegates to
:mod:`crmbuilder_v2.access.repositories.source_mapping`; bodies use the
parent-prefixed ``source_mapping_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``layouts.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import source_mapping
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    MarkStaleIn,
    SourceMappingCreateIn,
    SourceMappingPatchIn,
    SourceMappingReplaceIn,
)

router = APIRouter(prefix="/source-mappings", tags=["source-mappings"])

_PREFIX = "source_mapping_"


@router.get("")
def list_all(
    instance_identifier: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            source_mapping.list_source_mappings(
                s,
                instance_identifier=instance_identifier,
                status=status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``SMG-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": source_mapping.next_source_mapping_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = source_mapping.get_source_mapping(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("source_mapping", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: SourceMappingCreateIn):
    with writable_session() as s:
        return ok(
            source_mapping.create_source_mapping(
                s,
                instance_identifier=body.source_mapping_instance_identifier,
                source_entity_name=body.source_mapping_source_entity_name,
                decision_type=body.source_mapping_decision_type,
                notes=body.source_mapping_notes,
                identifier=body.source_mapping_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: SourceMappingReplaceIn):
    with writable_session() as s:
        return ok(
            source_mapping.update_source_mapping(
                s,
                identifier,
                source_entity_name=body.source_mapping_source_entity_name,
                decision_type=body.source_mapping_decision_type,
                status=body.source_mapping_status,
                notes=body.source_mapping_notes,
                stale_reason=body.source_mapping_stale_reason,
                stale_severity=body.source_mapping_stale_severity,
                superseded_by=body.source_mapping_superseded_by,
                resolved_at=body.source_mapping_resolved_at,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: SourceMappingPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged). The prefix is stripped to the repo's
    # patchable kwargs.
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_PREFIX):] if key.startswith(_PREFIX) else key: value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(source_mapping.patch_source_mapping(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(source_mapping.delete_source_mapping(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(source_mapping.restore_source_mapping(s, identifier))


@router.post("/{identifier}/mark-stale")
def mark_stale(identifier: str, body: MarkStaleIn):
    """Transition the mapping to ``stale`` with a graded reason + severity."""
    with writable_session() as s:
        return ok(
            source_mapping.mark_stale(
                s, identifier, reason=body.reason, severity=body.severity
            )
        )
