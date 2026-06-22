"""Pipeline-event log — durable pipeline progress + agent activity (PI-273).

A telemetry-satellite repository (the :mod:`cost_events` pattern): append one row
per pipeline step / agent invocation, then read them back ordered by time. The
active-engagement filter/stamp is applied transparently, so callers never pass
``engagement_id``. Three concerns, three requirements:

* :func:`record` — persist one durable event (REQ-312 agent outcomes / REQ-313
  pipeline steps), surviving the process that produced it;
* :func:`history` — reconstruct, for one release, the ordered account of how it
  got to where it is, drillable to each agent invocation (REQ-314);
* :func:`recent` — the newest events over any correlation filter.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import (
    AGENT_OUTCOMES,
    PIPELINE_EVENT_KINDS,
    PipelineEvent,
)

# The nullable correlation tags a call site may attach to an event (REQ-314).
_CORRELATION = ("release_identifier", "planning_item", "workstream",
                "work_task", "area", "tier")
_FILTER_COLS = {k: getattr(PipelineEvent, k) for k in _CORRELATION}


def record(
    session: Session,
    *,
    kind: str,
    outcome: str | None = None,
    summary: str | None = None,
    detail: dict | None = None,
    **correlation: str | None,
) -> dict:
    """Persist one pipeline event; returns the created row.

    ``kind`` must be a known :data:`PIPELINE_EVENT_KINDS`; ``outcome`` (only
    meaningful for an ``agent_outcome`` event) must be a known
    :data:`AGENT_OUTCOMES`. ``correlation`` accepts the keys in
    :data:`_CORRELATION` — each a nullable tag the call site fills with what it
    knows. Recording never raises on a scheduler's hot path beyond these
    validations, so the caller is expected to guard its own call.
    """
    if kind not in PIPELINE_EVENT_KINDS:
        raise UnprocessableError(
            [FieldError("event_kind", "invalid",
                        f"{kind!r} is not one of {sorted(PIPELINE_EVENT_KINDS)}")]
        )
    if outcome is not None and outcome not in AGENT_OUTCOMES:
        raise UnprocessableError(
            [FieldError("outcome", "invalid",
                        f"{outcome!r} is not one of {sorted(AGENT_OUTCOMES)}")]
        )
    unknown = set(correlation) - set(_CORRELATION)
    if unknown:
        raise UnprocessableError(
            [FieldError("correlation", "invalid",
                        f"unknown correlation key(s): {sorted(unknown)}")]
        )
    row = PipelineEvent(
        event_kind=kind,
        outcome=outcome,
        summary=summary,
        detail=detail,
        **{key: correlation.get(key) for key in _CORRELATION},
    )
    session.add(row)
    session.flush()
    return to_dict(row)


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


def recent(session: Session, *, limit: int = 200, **filters: str | None) -> list[dict]:
    """The most recent events (optionally filtered by correlation), newest first."""
    stmt = _apply_filters(select(PipelineEvent), filters)
    stmt = stmt.order_by(
        PipelineEvent.pipeline_event_created_at.desc(), PipelineEvent.id.desc()
    ).limit(limit)
    return [to_dict(r) for r in session.scalars(stmt)]


def history(session: Session, release_identifier: str, *, limit: int = 1000) -> list[dict]:
    """The ordered progress account for one release (REQ-314), oldest first.

    Unions the events tagged directly with this release (the conductor's stage
    transitions and per-PI dispatches) with the per-work-task events the area
    scheduler emits (dispatch, verify, merge, halt, no-op, and the per-agent
    ``agent_outcome`` records), found by traversing the release down to its
    planning items, workstreams, and work tasks. The result reads as how the
    release got to where it is and drills into each single agent invocation.
    """
    from sqlalchemy import or_

    from crmbuilder_v2.access.repositories import releases

    pis = [
        pi
        for prj in releases._in_scope_projects(session, release_identifier)
        for pi in releases._in_scope_planning_items(session, prj)
    ]
    wss = [ws for pi in pis for ws in releases._pi_workstreams(session, pi)]
    wts = [wt for ws in wss for wt in releases._ws_work_tasks(session, ws)]

    clauses = [PipelineEvent.release_identifier == release_identifier]
    if pis:
        clauses.append(PipelineEvent.planning_item.in_(pis))
    if wss:
        clauses.append(PipelineEvent.workstream.in_(wss))
    if wts:
        clauses.append(PipelineEvent.work_task.in_(wts))

    stmt = (
        select(PipelineEvent)
        .where(or_(*clauses))
        .order_by(
            PipelineEvent.pipeline_event_created_at.asc(), PipelineEvent.id.asc()
        )
        .limit(limit)
    )
    return [to_dict(r) for r in session.scalars(stmt)]
