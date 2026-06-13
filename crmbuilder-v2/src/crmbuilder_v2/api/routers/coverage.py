"""Capability-coverage report endpoint (requirements-provenance Phase 3)."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access import coverage
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/coverage", tags=["coverage"])


@router.get("/capabilities")
def capability_coverage():
    """The no-orphan-capability report for the active engagement.

    Returns ``{orphan_planning_items, unbuilt_requirements,
    conversations_without_requirement, summary}`` — planned/built work with no
    requirement above it, active requirements with no planned work below them,
    and completed conversations that produced no requirement.
    """
    with readonly_session() as s:
        return ok(coverage.capability_coverage(s))
