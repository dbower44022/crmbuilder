"""Orchestration endpoints for the parallel-agent orchestrator (PI-079)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access import orchestration
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.get("/ready-batches")
def ready_batches(
    area: list[str] | None = Query(
        default=None,
        description="Filter to items whose area set intersects these areas "
        "(repeat the param for multiple areas).",
    ),
    max_depth: int | None = Query(
        default=None, ge=0, description="Drop batches deeper than this cutoff."
    ),
):
    """Open planning items grouped by dependency depth for one engagement.

    Returns ``{batches: [{depth, items}], cyclic: [...], warnings: [...]}``
    where each item carries ``identifier``, ``title``,
    ``executive_summary``, ``area``, and ``claimed_by`` (PI-079).
    """
    with readonly_session() as s:
        return ok(
            orchestration.compute_ready_batches(s, areas=area, max_depth=max_depth)
        )
