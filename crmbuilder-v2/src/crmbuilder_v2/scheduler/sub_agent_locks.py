"""Sub-agent file-lock coordination — the dev-org lock runtime (PI-220, PRJ-030).

Wraps the PI-203 lock substrate (:mod:`crmbuilder_v2.access.locks`, FL-1..6) into
the protocol the intra-area sub-agent fan-out follows (AL-6):

- **acquire** declared resources before a sub-agent edits (FL-2, all-or-nothing);
- **verify** the actual diff at merge-back — retroactively acquire undeclared
  touches, report any touch held by another sub-agent (the mis-judged overlap),
  then **release** the holder's locks (FL-5);
- **reclaim** a dead sub-agent's locks (FL-6).

DB-transactional in-process (FL-4: locks live in a V2 table with atomic
``BEGIN IMMEDIATE`` acquire — doing this over HTTP would lose the savepoint-retry
atomicity ``acquire_many`` needs). It is a **no-op outside a dev-lane release**:
the file lock is the seatbelt for the ONE judgment-based grain — intra-area
parallel sub-agents within the single release in the development lane — so it only
engages when the work task belongs to a release in a lane state. Single-occupancy
(one release in the lane, REQ-188) means resource names need no release scoping:
there is no second release to collide with (§7.1).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import coordination, locks
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.vocab import RELEASE_LANE_STATUSES


def dev_lane_release(session: Session, work_task_id: str) -> str | None:
    """The release this work task belongs to **iff** it is in the development lane,
    else None — the no-op gate. The lock backstop engages only inside the dev lane.
    """
    rid = coordination.release_of_work_task(session, work_task_id)
    if rid is None:
        return None
    row = session.scalars(
        select(Release).where(Release.release_identifier == rid)
    ).first()
    if row is None or row.release_status not in RELEASE_LANE_STATUSES:
        return None
    return rid


def acquire_declared(
    session: Session, work_task_id: str, declared_paths: list[str]
) -> list[dict] | None:
    """FL-2: declare + check out the resources a sub-agent will touch before it
    edits (all-or-nothing). No-op outside a dev-lane release (returns None). Raises
    ``ConflictError`` if a declared resource is held by another sub-agent — the
    structural refusal that forces the two serial.
    """
    if dev_lane_release(session, work_task_id) is None:
        return None
    resources = locks.detect_resources(list(declared_paths))
    if not resources:
        return []
    return locks.acquire_many(session, resources, work_task_id)


def verify_and_release(
    session: Session, work_task_id: str, touched_paths: list[str]
) -> dict | None:
    """FL-5: at merge-back, recompute touched resources from the real diff,
    retroactively acquire undeclared touches, report any held by another sub-agent
    (the mis-judged overlap, for the caller to serialize/flag), then release all of
    this holder's locks. No-op outside a dev-lane release (returns None). Returns
    ``{held, retroactively_acquired, conflicts}``.
    """
    if dev_lane_release(session, work_task_id) is None:
        return None
    report = locks.verify(session, work_task_id, list(touched_paths))
    locks.release_all(session, work_task_id)
    return report


def reclaim(session: Session, work_task_id: str) -> list[dict]:
    """FL-6: release a dead sub-agent's locks (owner-supervised reclaim). Idempotent
    and safe to call unconditionally — releases whatever the holder still holds.
    """
    return locks.reclaim(session, work_task_id)
