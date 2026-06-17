"""Reconciliation-conflict resolution endpoint (PI-215, §5.4/§16.5).

A conflict is settled by a governed decision (RC-4). Listing per release lives on
the releases router; this router carries the by-id resolve action.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import reconciliation
from crmbuilder_v2.api.deps import writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import ResolveConflictIn

router = APIRouter(prefix="/reconciliation-conflicts", tags=["reconciliation"])


@router.post("/{conflict_id}/resolve")
def resolve(conflict_id: int, body: ResolveConflictIn):
    """Settle a reconciliation conflict by a governing decision (RC-4)."""
    with writable_session() as s:
        return ok(
            reconciliation.resolve_conflict(
                s,
                conflict_id,
                decision_identifier=body.decision_identifier,
                resolved_value=body.resolved_value,
            )
        )
