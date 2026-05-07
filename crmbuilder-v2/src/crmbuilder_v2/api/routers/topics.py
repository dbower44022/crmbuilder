"""Topics endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import topics
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import TopicCreateIn, TopicUpdateIn

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("")
def list_all():
    with readonly_session() as s:
        return ok(topics.list_all(s))


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        return ok(topics.get(s, identifier))


@router.post("", status_code=201)
def create(body: TopicCreateIn):
    with writable_session() as s:
        return ok(topics.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update(identifier: str, body: TopicUpdateIn):
    with writable_session() as s:
        payload = body.model_dump()
        parent_topic = payload.pop("parent_topic", None)
        fields = {k: v for k, v in payload.items() if v is not None}
        return ok(topics.update(s, identifier, parent_topic=parent_topic, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(topics.delete(s, identifier))
