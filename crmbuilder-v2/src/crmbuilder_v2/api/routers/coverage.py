"""Capability-coverage report endpoint (requirements-provenance Phase 3)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from crmbuilder_v2.access import coverage
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.config import get_settings

router = APIRouter(prefix="/coverage", tags=["coverage"])


def _resolve_since(since: str | None, default: str | None = None) -> datetime | None:
    """Resolve the baseline cutoff: the ``?since=`` param, else config default.

    Returns ``None`` when neither is set (no cutoff). A malformed value (param
    or config) raises 422 rather than silently disabling the cutoff.
    """
    raw = since if since is not None else (default or None)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw).replace(tzinfo=None)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="since must be ISO-8601 (e.g. 2026-06-13 or 2026-06-13T00:00:00)",
        ) from exc


@router.get("/capabilities")
def capability_coverage(
    since: str | None = Query(
        default=None,
        description=(
            "ISO-8601 baseline cutoff. Gaps on records created before it are "
            "reported as legacy baseline debt, not live gaps. Overrides the "
            "CRMBUILDER_V2_PROVENANCE_BASELINE default."
        ),
    ),
):
    """The no-orphan-capability report for the active engagement.

    Returns ``{orphan_planning_items, unbuilt_requirements,
    conversations_without_requirement, summary, baseline_since,
    baseline_summary}`` — planned/built work with no requirement above it,
    active requirements with no planned work below them, and completed
    conversations that produced no requirement. With a baseline cutoff in
    effect, the lists + ``summary`` hold only live (post-cutoff) gaps and
    ``baseline_summary`` counts the excluded legacy debt.
    """
    cutoff = _resolve_since(since, get_settings().provenance_baseline)
    with readonly_session() as s:
        return ok(coverage.capability_coverage(s, since=cutoff))


@router.get("/provenance")
def provenance_gaps(
    since: str | None = Query(
        default=None,
        description=(
            "ISO-8601 baseline cutoff. Records created before it that lack an "
            "audit-deposit link are counted as pre-capability legacy debt, not "
            "live gaps. Overrides the CRMBUILDER_V2_PROVENANCE_DEPOSIT_BASELINE "
            "default."
        ),
    ),
):
    """Audit-deposit provenance gaps for the active engagement (REQ-339).

    Returns the live design records (entities, fields, personas) with no
    inbound ``deposit_event_wrote_record`` edge — candidates that entered the
    design without a traceable link to the audit deposit that produced them,
    which the migration-mapping model rejects as a source. With a baseline
    cutoff in effect, records created before it are counted in
    ``baseline_summary`` as legacy debt rather than flagged live.
    """
    cutoff = _resolve_since(since, get_settings().provenance_deposit_baseline)
    with readonly_session() as s:
        return ok(coverage.provenance_gaps(s, since=cutoff))
