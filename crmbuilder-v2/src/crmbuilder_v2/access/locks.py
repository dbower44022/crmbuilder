"""File-level / named-resource check-out locks (PI-203 / PRJ-030, §7.3).

The backstop under an area owner's intra-area parallel sub-agent fan-out
(FL-1..FL-6). Sub-agents acquire locks on named resources (file paths or logical
resources like ``migration-chain``) before working; overlapping acquires are
refused (forced serial); ``verify`` recomputes the touched resources from the real
diff and retroactively acquires any undeclared touch. This is the substrate; the
worktree-per-sub-agent + serialized merge-back runtime drives it.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import ResourceLock
from crmbuilder_v2.access.repositories import _governance as gov

# FL-2 detection rules: a path matching the pattern also locks the logical
# resource (two migrations are different files but collide on the chain). Module
# defaults with a clear seam for per-engagement extension.
_DETECTION_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"migrations/.*\.py$"), "migration-chain"),
]


def detect_resources(paths: list[str]) -> list[str]:
    """Map a diff's paths to the full set of named resources to lock (FL-2)."""
    out: set[str] = set()
    for path in paths:
        if not path:
            continue
        out.add(path)
        for pattern, logical in _DETECTION_RULES:
            if pattern.search(path):
                out.add(logical)
    return sorted(out)


def _active(session: Session, resource_name: str) -> ResourceLock | None:
    return session.scalars(
        select(ResourceLock).where(
            ResourceLock.resource_name == resource_name,
            ResourceLock.released_at.is_(None),
        )
    ).first()


def held_locks(
    session: Session, *, resource_name: str | None = None, holder: str | None = None
) -> list[dict]:
    stmt = select(ResourceLock).where(ResourceLock.released_at.is_(None))
    if resource_name is not None:
        stmt = stmt.where(ResourceLock.resource_name == resource_name)
    if holder is not None:
        stmt = stmt.where(ResourceLock.holder == holder)
    stmt = stmt.order_by(ResourceLock.resource_name)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def acquire(session: Session, resource_name: str, holder: str) -> dict:
    """Acquire a lock. Idempotent for the same holder; refused (forced serial) if
    held by another (FL-1)."""
    resource_name = gov.require_nonempty(resource_name, field="resource_name")
    holder = gov.require_nonempty(holder, field="holder")
    active = _active(session, resource_name)
    if active is not None:
        if active.holder == holder:
            return to_dict(active)
        raise ConflictError(
            f"resource {resource_name!r} is held by {active.holder!r}; the "
            f"overlapping check-out is refused — run serial (FL-1)."
        )
    savepoint = session.begin_nested()
    row = ResourceLock(resource_name=resource_name, holder=holder)
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        savepoint.rollback()
        raise ConflictError(
            f"resource {resource_name!r} was acquired concurrently; run serial."
        ) from exc
    savepoint.commit()
    return to_dict(row)


def acquire_many(
    session: Session, resources: list[str], holder: str
) -> list[dict]:
    """All-or-nothing acquire over a set (a planned overlap on any resource
    serializes the whole fan-out; FL-2 acquire)."""
    savepoint = session.begin_nested()
    acquired: list[dict] = []
    try:
        for r in resources:
            acquired.append(acquire(session, r, holder))
    except ConflictError:
        savepoint.rollback()
        raise
    savepoint.commit()
    return acquired


def release(session: Session, resource_name: str, holder: str) -> dict:
    """Release one lock (holder-only)."""
    active = _active(session, resource_name)
    if active is None:
        raise NotFoundError("resource_lock", resource_name)
    if active.holder != holder:
        raise ConflictError(
            f"resource {resource_name!r} is held by {active.holder!r}, not "
            f"{holder!r}; only the holder may release it."
        )
    active.released_at = datetime.now(UTC)
    session.flush()
    return to_dict(active)


def release_all(session: Session, holder: str) -> list[dict]:
    """Release every active lock a holder holds (merge-back / end)."""
    rows = session.scalars(
        select(ResourceLock).where(
            ResourceLock.holder == holder, ResourceLock.released_at.is_(None)
        )
    ).all()
    now = datetime.now(UTC)
    for r in rows:
        r.released_at = now
    session.flush()
    return [to_dict(r) for r in rows]


def reclaim(session: Session, holder: str) -> list[dict]:
    """Owner-supervised reclaim of a dead sub-agent's locks (FL-6)."""
    return release_all(session, holder)


def reclaim_stale(session: Session, ttl_seconds: int) -> list[dict]:
    """TTL backstop (FL-6): release active locks older than ``ttl_seconds``."""
    cutoff = datetime.now(UTC) - timedelta(seconds=ttl_seconds)
    rows = session.scalars(
        select(ResourceLock).where(
            ResourceLock.released_at.is_(None), ResourceLock.acquired_at < cutoff
        )
    ).all()
    now = datetime.now(UTC)
    for r in rows:
        r.released_at = now
    session.flush()
    return [to_dict(r) for r in rows]


def verify(session: Session, holder: str, touched_paths: list[str]) -> dict:
    """The FL-2/FL-5 verify moment: recompute touched resources from the real diff,
    confirm the holder held each, retroactively acquire any undeclared touch.

    Returns ``{held, retroactively_acquired, conflicts}``. A conflict (a touch on a
    resource held by another) is reported, not silently merged — it feeds learning.
    """
    held: list[str] = []
    retro: list[str] = []
    conflicts: list[dict] = []
    for resource in detect_resources(touched_paths):
        active = _active(session, resource)
        if active is not None and active.holder == holder:
            held.append(resource)
        elif active is None:
            acquire(session, resource, holder)
            retro.append(resource)
        else:
            conflicts.append({"resource": resource, "holder": active.holder})
    return {
        "holder": holder,
        "held": sorted(held),
        "retroactively_acquired": sorted(retro),
        "conflicts": conflicts,
    }
