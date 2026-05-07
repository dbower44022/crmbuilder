"""Sessions endpoints (append-only — POST + DELETE only)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from crmbuilder_v2.access.repositories import sessions
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import SessionCreateIn

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_all(limit: int | None = Query(default=None, ge=1, le=1000)):
    with readonly_session() as s:
        return ok(sessions.list_all(s, limit=limit))


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        return ok(sessions.get(s, identifier))


@router.post("", status_code=201)
def create(body: SessionCreateIn):
    with writable_session() as s:
        return ok(sessions.create(s, **body.model_dump()))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(sessions.delete(s, identifier))
