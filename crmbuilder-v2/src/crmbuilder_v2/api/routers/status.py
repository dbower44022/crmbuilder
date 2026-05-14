"""Status endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import status as status_repo
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import StatusReplaceIn

router = APIRouter(prefix="/status", tags=["status"])


@router.get("")
def get_current():
    with readonly_session() as s:
        return ok(status_repo.get_current(s))


@router.get("/versions")
def list_versions():
    with readonly_session() as s:
        return ok(status_repo.list_versions(s))


@router.get("/next-identifier")
def next_identifier():
    """Return the next status version number (DEC-043).

    Status uses versioned-identifier semantics, so the "next
    identifier" is the integer version a new ``PUT /status`` would
    assign.
    """
    with readonly_session() as s:
        return ok({"next": status_repo.compute_next_version(s)})


@router.get("/versions/{version}")
def get_version(version: int):
    with readonly_session() as s:
        return ok(status_repo.get_version(s, version))


@router.put("")
def replace(body: StatusReplaceIn):
    with writable_session() as s:
        return ok(status_repo.replace(s, payload=body.payload))


@router.patch("/versions/{version}/make-current")
def make_version_current(version: int):
    with writable_session() as s:
        return ok(status_repo.make_version_current(s, version=version))
