"""Multi-agent coordination — lane occupancy & single-owner-per-area (PI-204).

PRJ-029, §6/§7.1/§7.2 (REQ-188, REQ-191). Single-occupancy of the development
lane is enforced by PI-205 (the ``ready → development`` gate + the
``uq_releases_one_in_lane`` index); this module adds the **read** (``lane_holder``)
and the **single-owner-per-area** gate (REQ-191): within a release that is in the
lane, every claimed Work Task of one area must share one owner — derived from the
existing Work Task claims, not a new store.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release, WorkTask
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import RELEASE_LANE_STATUSES


def lane_holder(session: Session) -> dict | None:
    """The release currently holding the development lane, or ``None`` (REQ-188)."""
    row = session.scalars(
        select(Release).where(
            Release.release_deleted_at.is_(None),
            Release.release_status.in_(sorted(RELEASE_LANE_STATUSES)),
        )
    ).first()
    return to_dict(row) if row is not None else None


def _one_step_up(session, *, source_type, source_id, relationship, target_type):
    edges = gov.outbound_edges(
        session,
        source_type=source_type,
        source_id=source_id,
        relationship=relationship,
        target_type=target_type,
    )
    return edges[0].target_id if edges else None


def release_of_work_task(session: Session, work_task_id: str) -> str | None:
    """Up-traverse work_task → workstream → planning_item → project → release."""
    ws = _one_step_up(
        session, source_type="work_task", source_id=work_task_id,
        relationship="work_task_belongs_to_workstream", target_type="workstream",
    )
    if ws is None:
        return None
    pi = _one_step_up(
        session, source_type="workstream", source_id=ws,
        relationship="workstream_belongs_to_planning_item",
        target_type="planning_item",
    )
    if pi is None:
        return None
    proj = _one_step_up(
        session, source_type="planning_item", source_id=pi,
        relationship="planning_item_belongs_to_project", target_type="project",
    )
    if proj is None:
        return None
    return _one_step_up(
        session, source_type="project", source_id=proj,
        relationship="project_belongs_to_release", target_type="release",
    )


def _release_status(session, release_id: str) -> str | None:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    return row.release_status if row is not None else None


def _work_tasks_of_release(session, release_id: str) -> list[WorkTask]:
    """Down-traverse release → projects → PIs → workstreams → work_tasks."""
    out: list[WorkTask] = []
    for prj in gov.inbound_edges(
        session, target_type="release", target_id=release_id,
        relationship="project_belongs_to_release", source_type="project",
    ):
        for pi in gov.inbound_edges(
            session, target_type="project", target_id=prj.source_id,
            relationship="planning_item_belongs_to_project",
            source_type="planning_item",
        ):
            for ws in gov.inbound_edges(
                session, target_type="planning_item", target_id=pi.source_id,
                relationship="workstream_belongs_to_planning_item",
                source_type="workstream",
            ):
                for wt in gov.inbound_edges(
                    session, target_type="workstream", target_id=ws.source_id,
                    relationship="work_task_belongs_to_workstream",
                    source_type="work_task",
                ):
                    row = session.scalars(
                        select(WorkTask).where(
                            WorkTask.work_task_identifier == wt.source_id
                        )
                    ).first()
                    if row is not None:
                        out.append(row)
    return out


def area_ownership(session: Session, release_id: str) -> dict[str, str]:
    """``{area: owner}`` for a release's claimed Work Tasks (coordination read)."""
    owners: dict[str, str] = {}
    for wt in _work_tasks_of_release(session, release_id):
        if wt.work_task_claimed_by is not None:
            owners.setdefault(wt.work_task_area, wt.work_task_claimed_by)
    return owners


def area_owner(session: Session, release_id: str, area: str) -> str | None:
    """The single owner of a ``(release, area)``'s claimed Work Tasks, or None."""
    for wt in _work_tasks_of_release(session, release_id):
        if wt.work_task_area == area and wt.work_task_claimed_by is not None:
            return wt.work_task_claimed_by
    return None


def assert_area_owner(session: Session, work_task_id: str, claimed_by: str) -> None:
    """Single-owner-per-area gate (REQ-191).

    A no-op unless the Work Task's release is in the development lane. Within the
    lane, a claim on a task whose ``(release, area)`` is already owned by a
    different agent is refused — an area has one owner that fans out sub-agents.
    """
    release_id = release_of_work_task(session, work_task_id)
    if release_id is None:
        return  # not release-scoped — existing ADO behaviour unchanged.
    status = _release_status(session, release_id)
    if status not in RELEASE_LANE_STATUSES:
        return
    wt = session.scalars(
        select(WorkTask).where(WorkTask.work_task_identifier == work_task_id)
    ).first()
    if wt is None:
        return
    for sibling in _work_tasks_of_release(session, release_id):
        if (
            sibling.work_task_area == wt.work_task_area
            and sibling.work_task_claimed_by is not None
            and sibling.work_task_claimed_by != claimed_by
        ):
            raise ConflictError(
                f"area {wt.work_task_area!r} of release {release_id!r} is already "
                f"owned by {sibling.work_task_claimed_by!r}; an area has a single "
                f"owner that fans out sub-agents (REQ-191). It cannot be claimed "
                f"by {claimed_by!r}."
            )
