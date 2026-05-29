"""Identifier reservation endpoint for the orchestrator (PI-078)."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import identifier_reservations
from crmbuilder_v2.api.deps import writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import IdentifierReserveIn

router = APIRouter(prefix="/identifiers", tags=["identifiers"])


@router.post("/reserve")
def reserve(body: IdentifierReserveIn):
    """Atomically reserve a block of identifiers for one entity type."""
    with writable_session() as s:
        return ok(
            identifier_reservations.reserve(
                s,
                entity_type=body.entity_type,
                count=body.count,
                reserved_by=body.reserved_by,
                ttl_seconds=body.ttl_seconds,
            )
        )
