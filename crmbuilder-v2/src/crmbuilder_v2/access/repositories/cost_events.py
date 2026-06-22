"""Cost-event telemetry store — record + aggregate AI spend (PI-263 / PRJ-041, REQ-307).

The cost-measurement foundation (topic Cost & Spend Controls). ``record`` writes one
``cost_events`` row per model call, computing ``cost_usd`` uniformly from the per-model
price table (:mod:`crmbuilder_v2.access.cost_pricing`). ``aggregate`` / ``aggregate_by``
sum cost + tokens over any attribution filter (the basis for per-engagement and
per-release totals); ``recent`` lists the latest events. Engagement scoping is applied
transparently by the active-engagement read filter / write stamp, so callers never pass
``engagement_id`` — totals are already per-active-engagement.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import cost_pricing
from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import CostEvent
from crmbuilder_v2.access.vocab import COST_SOURCES

# Attribution tags the call site may set (all nullable).
_ATTRIBUTION = ("release_identifier", "planning_item", "work_task", "area", "tier", "stage")

# Columns a caller may filter aggregations / listings on.
_FILTER_COLS = {
    "release_identifier": CostEvent.release_identifier,
    "planning_item": CostEvent.planning_item,
    "work_task": CostEvent.work_task,
    "area": CostEvent.area,
    "tier": CostEvent.tier,
    "stage": CostEvent.stage,
    "source": CostEvent.cost_source,
    "model": CostEvent.cost_model,
}

# Dimensions a caller may group a breakdown by.
_DIMENSION_COLS = {
    "release": CostEvent.release_identifier,
    "area": CostEvent.area,
    "tier": CostEvent.tier,
    "stage": CostEvent.stage,
    "source": CostEvent.cost_source,
    "model": CostEvent.cost_model,
}


def _apply_filters(stmt, filters: dict):
    unknown = set(filters) - set(_FILTER_COLS)
    if unknown:
        raise UnprocessableError(
            [FieldError("filters", "invalid", f"unknown filter(s): {sorted(unknown)}")]
        )
    for key, value in filters.items():
        if value is not None:
            stmt = stmt.where(_FILTER_COLS[key] == value)
    return stmt


def record(
    session: Session,
    *,
    source: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
    reported_usd: float | None = None,
    **attribution: str | None,
) -> dict:
    """Record one spend event; returns the created row. ``cost_usd`` is computed from
    the price table. ``attribution`` accepts the keys in :data:`_ATTRIBUTION`."""
    if source not in COST_SOURCES:
        raise UnprocessableError(
            [FieldError("cost_source", "invalid",
                        f"{source!r} is not one of {sorted(COST_SOURCES)}")]
        )
    unknown = set(attribution) - set(_ATTRIBUTION)
    if unknown:
        raise UnprocessableError(
            [FieldError("attribution", "invalid",
                        f"unknown attribution key(s): {sorted(unknown)}")]
        )
    cost_usd = cost_pricing.compute_cost_usd(
        model, input_tokens, output_tokens, cache_write_tokens, cache_read_tokens
    )
    row = CostEvent(
        cost_source=source,
        cost_model=model or "",
        cost_input_tokens=input_tokens or 0,
        cost_output_tokens=output_tokens or 0,
        cost_cache_write_tokens=cache_write_tokens or 0,
        cost_cache_read_tokens=cache_read_tokens or 0,
        cost_usd=cost_usd,
        cost_reported_usd=reported_usd,
        **{key: attribution.get(key) for key in _ATTRIBUTION},
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def aggregate(session: Session, **filters: str | None) -> dict:
    """Summed cost + token totals over the (optional) attribution filter."""
    stmt = _apply_filters(
        select(
            func.coalesce(func.sum(CostEvent.cost_usd), 0.0),
            func.coalesce(func.sum(CostEvent.cost_input_tokens), 0),
            func.coalesce(func.sum(CostEvent.cost_output_tokens), 0),
            func.coalesce(func.sum(CostEvent.cost_cache_write_tokens), 0),
            func.coalesce(func.sum(CostEvent.cost_cache_read_tokens), 0),
            func.count(CostEvent.id),
        ),
        filters,
    )
    cost, ti, to_, cw, cr, n = session.execute(stmt).one()
    return {
        "cost_usd": round(float(cost or 0.0), 6),
        "input_tokens": int(ti or 0),
        "output_tokens": int(to_ or 0),
        "cache_write_tokens": int(cw or 0),
        "cache_read_tokens": int(cr or 0),
        "event_count": int(n or 0),
    }


def aggregate_by(session: Session, dimension: str, **filters: str | None) -> list[dict]:
    """A cost breakdown grouped by one dimension (release / area / tier / stage /
    source / model), highest cost first. ``None`` keys (untagged events) are included."""
    if dimension not in _DIMENSION_COLS:
        raise UnprocessableError(
            [FieldError("dimension", "invalid",
                        f"{dimension!r} is not one of {sorted(_DIMENSION_COLS)}")]
        )
    col = _DIMENSION_COLS[dimension]
    total = func.coalesce(func.sum(CostEvent.cost_usd), 0.0)
    stmt = _apply_filters(select(col, total, func.count(CostEvent.id)), filters)
    stmt = stmt.group_by(col).order_by(total.desc())
    return [
        {"key": key, "cost_usd": round(float(cost or 0.0), 6), "event_count": int(n)}
        for key, cost, n in session.execute(stmt)
    ]


def recent(session: Session, *, limit: int = 50, **filters: str | None) -> list[dict]:
    """The most recent events (optionally filtered), newest first."""
    stmt = _apply_filters(select(CostEvent), filters)
    stmt = stmt.order_by(CostEvent.cost_created_at.desc(), CostEvent.id.desc()).limit(limit)
    return [to_dict(r) for r in session.scalars(stmt)]
