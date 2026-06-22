"""Cost aggregation endpoints — AI spend visibility (PI-265 / PRJ-041, REQ-307).

Read-only views over the ``cost_events`` telemetry the spend surfaces record (PI-263 /
PI-264): a summed total, a breakdown by one dimension, and the recent events — each over
the active engagement and an optional attribution filter. The basis for the desktop Cost
panel and any later estimate / budget feature.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access.repositories import cost_events
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/cost", tags=["cost"])


def _filters(
    release_identifier: str | None,
    area: str | None,
    stage: str | None,
    source: str | None,
    model: str | None,
    work_task: str | None,
    planning_item: str | None,
) -> dict:
    raw = {
        "release_identifier": release_identifier,
        "area": area,
        "stage": stage,
        "source": source,
        "model": model,
        "work_task": work_task,
        "planning_item": planning_item,
    }
    return {k: v for k, v in raw.items() if v is not None}


@router.get("/summary")
def cost_summary(
    release_identifier: str | None = Query(default=None),
    area: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    source: str | None = Query(default=None),
    model: str | None = Query(default=None),
    work_task: str | None = Query(default=None),
    planning_item: str | None = Query(default=None),
):
    """Summed cost + token totals over the active engagement and optional filter."""
    filters = _filters(release_identifier, area, stage, source, model, work_task,
                        planning_item)
    with readonly_session() as s:
        return ok(cost_events.aggregate(s, **filters))


@router.get("/by/{dimension}")
def cost_by(
    dimension: str,
    release_identifier: str | None = Query(default=None),
    area: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    source: str | None = Query(default=None),
    model: str | None = Query(default=None),
    work_task: str | None = Query(default=None),
    planning_item: str | None = Query(default=None),
):
    """A cost breakdown grouped by one dimension (release / area / tier / stage /
    source / model), highest cost first. An invalid dimension is a 422."""
    filters = _filters(release_identifier, area, stage, source, model, work_task,
                        planning_item)
    with readonly_session() as s:
        return ok(cost_events.aggregate_by(s, dimension, **filters))


@router.get("/events")
def cost_events_list(
    limit: int = Query(default=50, ge=1, le=500),
    release_identifier: str | None = Query(default=None),
    area: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    source: str | None = Query(default=None),
    model: str | None = Query(default=None),
    work_task: str | None = Query(default=None),
    planning_item: str | None = Query(default=None),
):
    """The most recent cost events (optionally filtered), newest first."""
    filters = _filters(release_identifier, area, stage, source, model, work_task,
                        planning_item)
    with readonly_session() as s:
        return ok(cost_events.recent(s, limit=limit, **filters))
