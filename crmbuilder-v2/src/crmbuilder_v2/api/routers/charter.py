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


@router.get("/next-identifier")
def next_identifier():
    """Return the next charter version number (DEC-043).

    Charter uses versioned-identifier semantics, so the "next
    identifier" is the integer version a new ``PUT /charter`` would
    assign.
    """
    with readonly_session() as s:
        return ok({"next": charter.compute_next_version(s)})


@router.get("/versions/{version}")
def get_version(version: int):
    with readonly_session() as s:
        return ok(charter.get_version(s, version))


@router.put("")
def replace(body: CharterReplaceIn):
    with writable_session() as s:
        return ok(charter.replace(s, payload=body.payload))


@router.patch("/versions/{version}/make-current")
def make_version_current(version: int):
    with writable_session() as s:
        return ok(charter.make_version_current(s, version=version))
