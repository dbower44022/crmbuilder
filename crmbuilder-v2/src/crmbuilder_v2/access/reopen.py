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


def reopen_area(
    session: Session, release_id: str, area: str, reason: str
) -> dict:
    """Reopen a frozen area in-lane (RW2). Its downstream areas are now paused."""
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
    row = AreaReopen(
        release_identifier=release_id, area=area, reason=reason, status="open"
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
