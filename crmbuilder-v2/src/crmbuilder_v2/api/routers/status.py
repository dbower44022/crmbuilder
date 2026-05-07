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


@router.get("/versions/{version}")
def get_version(version: int):
    with readonly_session() as s:
        return ok(status_repo.get_version(s, version))


@router.put("")
def replace(body: StatusReplaceIn):
    with writable_session() as s:
        return ok(status_repo.replace(s, payload=body.payload))
