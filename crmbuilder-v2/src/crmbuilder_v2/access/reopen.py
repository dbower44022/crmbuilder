"""In-lane frozen-area reopen (PI-212 / PRJ-034, RW2/RW3).

The §14 D2 reopen: a frozen area is reopened in-lane on a downstream area's
discovered need; while it is thawing, its downstream areas (higher
``SYSTEM_AREA_RANKS`` rank) are paused until it re-freezes. This is the
pause/resume mechanic; the cascade re-validation (PI-213) and blast-radius
approval (PI-214) are Wave 3.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import coordination
from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import AreaReopen, Release, WorkTask
from crmbuilder_v2.access.vocab import RELEASE_LANE_STATUSES, SYSTEM_AREA_RANKS

_TIERS = ("lead_auto", "lead", "pm", "human")
# Breadth thresholds (count of downstream areas) → tier index. Module defaults;
# per-engagement override is a thin follow-on (PI-214 §2).
_BREADTH_PM_THRESHOLD = 3  # 3+ downstream areas → PM
_BREADTH_LEAD_THRESHOLD = 1  # 1–2 → Lead; 0 → lead_auto
_FOUNDATIONAL_RANK = 1  # storage — depth override → Human


def downstream_areas(area: str) -> frozenset[str]:
    """Spine areas strictly downstream of ``area`` (higher rank). Empty for an
    unranked or top-rank area."""
    rank = SYSTEM_AREA_RANKS.get(area)
    if rank is None:
        return frozenset()
    return frozenset(
        a for a, r in SYSTEM_AREA_RANKS.items() if r is not None and r > rank
    )


def _release(session: Session, release_id: str) -> Release:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    if row is None:
        raise NotFoundError("release", release_id)
    return row


def _open_reopen(session: Session, release_id: str, area: str) -> AreaReopen | None:
    return session.scalars(
        select(AreaReopen).where(
            AreaReopen.release_identifier == release_id,
            AreaReopen.area == area,
            AreaReopen.status == "open",
        )
    ).first()


def list_reopens(
    session: Session, release_id: str, *, status: str | None = None
) -> list[dict]:
    stmt = (
        select(AreaReopen)
        .where(AreaReopen.release_identifier == release_id)
        .order_by(AreaReopen.area, AreaReopen.created_at)
    )
    if status is not None:
        stmt = stmt.where(AreaReopen.status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def paused_areas(session: Session, release_id: str) -> set[str]:
    """The areas paused by every open reopen of this release (the downstream set)."""
    out: set[str] = set()
    for r in session.scalars(
        select(AreaReopen).where(
            AreaReopen.release_identifier == release_id,
            AreaReopen.status == "open",
        )
    ).all():
        out |= downstream_areas(r.area)
    return out


def is_area_paused(session: Session, release_id: str, area: str) -> bool:
    return area in paused_areas(session, release_id)


def _prior_reopen_count(session: Session, release_id: str, area: str) -> int:
    return len(session.scalars(
        select(AreaReopen.id).where(
            AreaReopen.release_identifier == release_id,
            AreaReopen.area == area,
        )
    ).all())


def reopen_tier(session: Session, release_id: str, area: str) -> str:
    """The blast-radius-derived approval tier (PI-214, RA-3). tier =
    max(breadth, depth), then +1 for a repeat reopen of the same area."""
    n = len(downstream_areas(area))
    if n == 0:
        breadth = 0
    elif n >= _BREADTH_PM_THRESHOLD:
        breadth = 2
    else:
        breadth = 1
    depth = 3 if SYSTEM_AREA_RANKS.get(area) == _FOUNDATIONAL_RANK else 0
    idx = max(breadth, depth)
    if _prior_reopen_count(session, release_id, area) >= 1:  # repeat (RA-4)
        idx = min(idx + 1, 3)
    return _TIERS[idx]


def reopen_impact(session: Session, release_id: str, area: str) -> dict:
    """The deterministic impact report surfaced before approval (PI-214, RA-5)."""
    down = sorted(downstream_areas(area))
    return {
        "release_identifier": release_id,
        "reopen_point": area,
        "downstream_areas": down,
        "count": len(down),
        "tier": reopen_tier(session, release_id, area),
        "is_repeat": _prior_reopen_count(session, release_id, area) >= 1,
    }


def reopen_area(
    session: Session,
    release_id: str,
    area: str,
    reason: str,
    *,
    approval_decision_identifier: str | None = None,
    triggering_finding_identifier: str | None = None,
) -> dict:
    """Reopen a frozen area in-lane (RW2). Its downstream areas are now paused.

    PI-214 (RW5): the reopen is gated by a recorded approval decision at the
    blast-radius-derived tier; ``lead_auto`` (empty radius) is Lead-self-authorized
    and needs no decision.
    """
    rel = _release(session, release_id)
    if rel.release_status not in RELEASE_LANE_STATUSES:
        raise ConflictError(
            f"release {release_id!r} is {rel.release_status!r}, not in the "
            f"development lane; an area reopen is in-lane only (RW2)."
        )
    if SYSTEM_AREA_RANKS.get(area) is None:
        raise ConflictError(
            f"{area!r} is not a ranked dependency-spine area; only spine areas "
            f"(storage/access/api/mcp/ui) reopen with a downstream cascade."
        )
    if not isinstance(reason, str) or not reason.strip():
        raise ConflictError("a reason (the downstream need) is required (RW2).")
    if _open_reopen(session, release_id, area) is not None:
        raise ConflictError(
            f"area {area!r} of release {release_id!r} already has an open reopen."
        )
    tier = reopen_tier(session, release_id, area)
    if tier != "lead_auto" and not approval_decision_identifier:
        raise ConflictError(
            f"reopening area {area!r} of release {release_id!r} is tier {tier!r} "
            f"(blast radius {sorted(downstream_areas(area))}); it requires a "
            f"recorded approval decision (RW5)."
        )
    row = AreaReopen(
        release_identifier=release_id, area=area, reason=reason, status="open",
        # PI-213 (RW4): the full downstream set must re-validate — no exemption.
        cascade_areas=sorted(downstream_areas(area)),
        revalidated_areas=[],
        approval_tier=tier,
        approval_decision_identifier=approval_decision_identifier,
        triggering_finding_identifier=triggering_finding_identifier,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def refreeze_area(session: Session, release_id: str, area: str) -> dict:
    """Re-freeze a reopened area (RW3 resume): resolve its open reopen."""
    row = _open_reopen(session, release_id, area)
    if row is None:
        raise NotFoundError("area_reopen", f"{release_id}/{area}")
    row.status = "resolved"
    row.resolved_at = datetime.now(UTC)
    session.flush()
    return to_dict(row)


def revalidate_area(
    session: Session, reopen_id: int, area: str
) -> dict:
    """Record that a downstream area re-passed its QA/test gate (PI-213, RW4)."""
    row = session.get(AreaReopen, reopen_id)
    if row is None:
        raise NotFoundError("area_reopen", str(reopen_id))
    if area not in (row.cascade_areas or []):
        raise ConflictError(
            f"{area!r} is not in the cascade of reopen {reopen_id} "
            f"({sorted(row.cascade_areas or [])}); only downstream areas "
            f"re-validate."
        )
    done = list(row.revalidated_areas or [])
    if area in done:
        raise ConflictError(
            f"area {area!r} is already re-validated for reopen {reopen_id}."
        )
    done.append(area)
    row.revalidated_areas = sorted(done)
    session.flush()
    return to_dict(row)


def outstanding_revalidations(session: Session, release_id: str) -> set[str]:
    """Downstream areas still owed a re-validation across the release's reopens
    (RW4). The release cannot ship while this is non-empty."""
    out: set[str] = set()
    for r in session.scalars(
        select(AreaReopen).where(AreaReopen.release_identifier == release_id)
    ).all():
        out |= set(r.cascade_areas or []) - set(r.revalidated_areas or [])
    return out


def assert_area_not_paused(session: Session, work_task_id: str) -> None:
    """Refuse work on a paused (downstream-of-an-open-reopen) area (RW3).

    A no-op when the Work Task is not under a release. Called from
    ``claim_work_task`` beside PI-204's single-owner-per-area gate.
    """
    release_id = coordination.release_of_work_task(session, work_task_id)
    if release_id is None:
        return
    wt = session.scalars(
        select(WorkTask).where(WorkTask.work_task_identifier == work_task_id)
    ).first()
    if wt is None:
        return
    if is_area_paused(session, release_id, wt.work_task_area):
        raise ConflictError(
            f"area {wt.work_task_area!r} of release {release_id!r} is paused: an "
            f"upstream area is reopened and thawing (RW3 — never build on thawing "
            f"ground). It resumes when the upstream re-freezes."
        )
