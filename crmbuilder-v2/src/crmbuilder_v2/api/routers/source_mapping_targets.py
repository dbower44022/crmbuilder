"""Source mapping target endpoints — PI-255 (PRJ-027).

The design-entity targets of an entity-level source mapping (child table, no
prefixed identifier, no soft-delete). The parent ``source_mapping_identifier``
is a required query param on the read and a body field on the writes. Each
delegates to :mod:`crmbuilder_v2.access.repositories.source_mapping_targets`;
responses use the v2 ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import source_mapping_targets
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    SourceMappingTargetAddIn,
    SourceMappingTargetRemoveIn,
    SourceMappingTargetSetIn,
)

router = APIRouter(
    prefix="/source-mapping-targets", tags=["source-mapping-targets"]
)


@router.get("")
def list_all(source_mapping_identifier: str):
    with readonly_session() as s:
        return ok(
            source_mapping_targets.list_targets(
                s, source_mapping_identifier=source_mapping_identifier
            )
        )


@router.post("", status_code=201)
def add(body: SourceMappingTargetAddIn):
    """Add one design-entity target (idempotent on the (mapping, entity) pair)."""
    with writable_session() as s:
        return ok(
            source_mapping_targets.add_target(
                s,
                source_mapping_identifier=body.source_mapping_identifier,
                entity_identifier=body.entity_identifier,
            )
        )


@router.put("")
def set_all(body: SourceMappingTargetSetIn):
    """Replace all targets of a source mapping atomically."""
    with writable_session() as s:
        return ok(
            source_mapping_targets.set_targets(
                s,
                source_mapping_identifier=body.source_mapping_identifier,
                entity_identifiers=body.entity_identifiers,
            )
        )


@router.delete("")
def remove(body: SourceMappingTargetRemoveIn):
    with writable_session() as s:
        source_mapping_targets.remove_target(
            s,
            source_mapping_identifier=body.source_mapping_identifier,
            entity_identifier=body.entity_identifier,
        )
        return ok(None)
