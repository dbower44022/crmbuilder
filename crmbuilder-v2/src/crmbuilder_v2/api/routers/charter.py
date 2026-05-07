"""Charter endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import charter
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import CharterReplaceIn

router = APIRouter(prefix="/charter", tags=["charter"])


@router.get("")
def get_current():
    with readonly_session() as s:
        return ok(charter.get_current(s))


@router.get("/versions")
def list_versions():
    with readonly_session() as s:
        return ok(charter.list_versions(s))


@router.get("/versions/{version}")
def get_version(version: int):
    with readonly_session() as s:
        return ok(charter.get_version(s, version))


@router.put("")
def replace(body: CharterReplaceIn):
    with writable_session() as s:
        return ok(charter.replace(s, payload=body.payload))
