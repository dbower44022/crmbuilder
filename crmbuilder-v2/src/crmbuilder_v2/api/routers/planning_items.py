"""Planning items endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import planning_items
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import PlanningItemCreateIn, PlanningItemUpdateIn

router = APIRouter(prefix="/planning-items", tags=["planning_items"])


@router.get("")
def list_all():
    with readonly_session() as s:
        return ok(planning_items.list_all(s))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``PI-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": planning_items.compute_next_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        return ok(planning_items.get(s, identifier))


@router.post("", status_code=201)
def create(body: PlanningItemCreateIn):
    with writable_session() as s:
        return ok(planning_items.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update(identifier: str, body: PlanningItemUpdateIn):
    with writable_session() as s:
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        return ok(planning_items.update(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(planning_items.delete(s, identifier))
