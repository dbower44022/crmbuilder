"""Best-effort pipeline-event capture (PI-273 / REQ-312/313/314).

The schedulers call :func:`emit` at each step they take (a stage transition, an
agent dispatch, a verify, a merge, a halt, a no-op) and once per agent invocation
(``kind="agent_outcome"``) so the run leaves a durable, queryable account in the
``pipeline_events`` table instead of only on the console. Mirrors
:mod:`cost_capture`: a thin wrapper around ``session_scope`` that sets the active
engagement and **never raises** — observability must not break the work it observes.
"""

from __future__ import annotations

import contextlib
import logging

log = logging.getLogger(__name__)


def _engagement_ctx(engagement: str | None):
    if engagement is None:
        return contextlib.nullcontext()
    from crmbuilder_v2.access.engagement_scope import active_engagement

    return active_engagement(engagement)


def emit(
    engagement: str | None,
    *,
    kind: str,
    outcome: str | None = None,
    summary: str | None = None,
    detail: dict | None = None,
    **correlation: str | None,
) -> None:
    """Persist one pipeline event; swallow and log any failure (best-effort).

    ``kind`` is a :data:`crmbuilder_v2.access.models.PIPELINE_EVENT_KINDS`;
    ``outcome`` (for an ``agent_outcome``) a
    :data:`crmbuilder_v2.access.models.AGENT_OUTCOMES`; ``correlation`` the nullable
    release / planning_item / workstream / work_task / area / tier tags.
    """
    try:
        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.repositories import pipeline_events

        clean = {k: v for k, v in correlation.items() if v is not None}
        with _engagement_ctx(engagement), session_scope() as s:
            pipeline_events.record(
                s, kind=kind, outcome=outcome, summary=summary,
                detail=detail, **clean,
            )
    except Exception as exc:  # noqa: BLE001 — capture must never break the work
        log.warning("pipeline event capture skipped: %s", exc)
