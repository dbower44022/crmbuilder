"""Decisions endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import decisions
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import DecisionCreateIn, DecisionUpdateIn

router = APIRouter(prefix="/decisions", tags=["decisions"])


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(decisions.list_all(s, include_deleted=include_deleted))


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        return ok(decisions.get(s, identifier))


@router.post("", status_code=201)
def create(body: DecisionCreateIn):
    with writable_session() as s:
        return ok(decisions.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update(identifier: str, body: DecisionUpdateIn):
    with writable_session() as s:
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        supersedes = fields.pop("supersedes", None)
        superseded_by = fields.pop("superseded_by", None)
        return ok(
            decisions.update(
                s,
                identifier,
                supersedes=supersedes,
                superseded_by=superseded_by,
                **fields,
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(decisions.delete(s, identifier))
