"""Resource-lock endpoints — the file-level check-out backstop (PI-203 / PRJ-030).

Sub-agents acquire/verify/release named-resource locks; the owner reclaims a dead
child's locks. Delegates to :mod:`crmbuilder_v2.access.locks`. All responses use
the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access import locks
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    AcquireLocksIn,
    ReclaimLocksIn,
    ReleaseLockIn,
    VerifyLocksIn,
)

router = APIRouter(prefix="/locks", tags=["locks"])


@router.get("")
def list_held(resource: str | None = None, holder: str | None = None):
    with readonly_session() as s:
        return ok(locks.held_locks(s, resource_name=resource, holder=holder))


@router.post("/acquire")
def acquire(body: AcquireLocksIn):
    """All-or-nothing acquire over a set of resources (FL-2)."""
    with writable_session() as s:
        return ok(locks.acquire_many(s, body.resources, body.holder))


@router.post("/release")
def release(body: ReleaseLockIn):
    """Release one lock, or all of a holder's locks when no resource is given."""
    with writable_session() as s:
        if body.resource is not None:
            return ok(locks.release(s, body.resource, body.holder))
        return ok(locks.release_all(s, body.holder))


@router.post("/verify")
def verify(body: VerifyLocksIn):
    """Verify the holder held every touched resource; retroactively acquire any
    undeclared touch (FL-2/FL-5)."""
    with writable_session() as s:
        return ok(locks.verify(s, body.holder, body.touched_paths))


@router.post("/reclaim")
def reclaim(body: ReclaimLocksIn):
    """Owner-supervised reclaim of a dead sub-agent's locks (FL-6)."""
    with writable_session() as s:
        return ok(locks.reclaim(s, body.holder))
