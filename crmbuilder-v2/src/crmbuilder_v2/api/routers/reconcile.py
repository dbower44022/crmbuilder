"""Three-way reconciliation comparison endpoints — PI-316 (REL-024).

Read-only endpoints over :mod:`crmbuilder_v2.access.reconcile_compare`. The
comparison is served from already-stored audit data (the canonical design plus
each instance's ``instance_membership`` snapshot), so it returns without a live
re-audit. All responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access import reconcile_compare
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import instances
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


@router.get("/compare")
def compare(
    instance_a: str = Query(..., description="First instance identifier"),
    instance_b: str = Query(..., description="Second instance identifier"),
    entity: str | None = Query(
        None, description="Scope to one entity (the per-entity drill); omit for the full scan"
    ),
):
    """Three-way diff across the canonical design and two instances (REQ-352/353).

    Returns differing rows grouped by entity. Supply ``entity`` to scope to one
    entity (the drill); omit it for the full scan across every member type.
    """
    with readonly_session() as s:
        for inst in (instance_a, instance_b):
            if instances.get_instance(s, inst, include_deleted=True) is None:
                raise NotFoundError("instance", inst)
        return ok(
            reconcile_compare.three_way_compare(
                s,
                instance_a=instance_a,
                instance_b=instance_b,
                entity_identifier=entity,
            )
        )
