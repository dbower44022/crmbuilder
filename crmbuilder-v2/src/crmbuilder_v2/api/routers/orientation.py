"""Orientation endpoints — Tier 2 reads per DEC-011.

Convenience aggregations layered above the per-entity routers. Each
endpoint maps onto a need in the session orientation protocol:

* ``GET /orientation/recent-sessions`` — last N sessions
* ``GET /orientation/decisions-for-session/{id}`` — decisions referenced by a
  given session via the universal references table

The current charter and current status are already exposed at
``GET /charter`` and ``GET /status`` and are not duplicated here.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access.repositories import decisions, references, sessions
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/orientation", tags=["orientation"])


@router.get("/recent-sessions")
def recent_sessions(limit: int = Query(default=3, ge=1, le=50)):
    with readonly_session() as s:
        return ok(sessions.list_all(s, limit=limit))


@router.get("/decisions-for-session/{identifier}")
def decisions_for_session(identifier: str):
    """Return all decisions reachable from a given session via the references table."""
    with readonly_session() as s:
        # Confirm the session exists; this raises NotFoundError → 404 mapping.
        sessions.get(s, identifier)
        refs = references.list_from(
            s, source_type="session", source_id=identifier
        )
        decision_ids = [
            r["target_id"] for r in refs if r["target_type"] == "decision"
        ]
        rows = []
        for did in decision_ids:
            try:
                rows.append(decisions.get(s, did))
            except Exception:  # pragma: no cover — references should be intact
                continue
        return ok(rows, count=len(rows))
