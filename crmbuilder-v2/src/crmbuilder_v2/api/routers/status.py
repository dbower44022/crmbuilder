"""Status endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access.repositories import status as status_repo
from crmbuilder_v2.access.status_snapshot import build_status_payload
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import StatusGenerateIn, StatusReplaceIn

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


@router.get("/preview")
def preview(narrative: str | None = Query(default=None)):
    """Return the payload ``POST /status/generate`` would write, without writing it (PI-433)."""
    with readonly_session() as s:
        return ok(build_status_payload(s, narrative=narrative))


@router.get("/versions/{version}")
def get_version(version: int):
    with readonly_session() as s:
        return ok(status_repo.get_version(s, version))


@router.put("")
def replace(body: StatusReplaceIn):
    with writable_session() as s:
        return ok(status_repo.replace(s, payload=body.payload))


@router.post("/generate")
def generate(body: StatusGenerateIn):
    """Write a new status version assembled from stored records (PI-433, REQ-527)."""
    with writable_session() as s:
        return ok(status_repo.generate(s, narrative=body.narrative))


@router.patch("/versions/{version}/make-current")
def make_version_current(version: int):
    with writable_session() as s:
        return ok(status_repo.make_version_current(s, version=version))
