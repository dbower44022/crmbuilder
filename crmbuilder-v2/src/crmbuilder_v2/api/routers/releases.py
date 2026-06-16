"""Releases endpoints — the multi-agent release pipeline keystone (PI-205).

PRJ-031. Delegates to :mod:`crmbuilder_v2.access.repositories.releases`. The
Release's ``release_status`` is mutated only through ``POST /releases/{id}/
transition`` (the guarded lifecycle move running the freeze / planned-completely
/ single-occupancy gates); ``PATCH`` handles non-status fields only. All
responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import releases
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ReleaseCreateIn,
    ReleaseLaneOrderIn,
    ReleasePatchIn,
    ReleaseTransitionIn,
)

router = APIRouter(prefix="/releases", tags=["releases"])
_FIELD_PREFIX = "release_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            releases.list_releases(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": releases.next_release_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = releases.get_release(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("release", identifier)
        return ok(record)


@router.get("/{identifier}/composition")
def composition(identifier: str):
    """The release's release-scoped Projects and their Planning Items (derived)."""
    with readonly_session() as s:
        return ok(releases.composition(s, identifier))


@router.post("", status_code=201)
def create(body: ReleaseCreateIn):
    with writable_session() as s:
        return ok(
            releases.create_release(
                s,
                title=body.release_title,
                description=body.release_description,
                notes=body.release_notes,
                status=body.release_status or "preliminary_planning",
                lane_order=body.release_lane_order,
                identifier=body.release_identifier,
                references=_edges(body),
            )
        )


@router.post("/{identifier}/transition")
def transition(identifier: str, body: ReleaseTransitionIn):
    """The guarded lifecycle move — runs the freeze / planned-completely /
    single-occupancy gates. 409 on an illegal or ungated transition."""
    with writable_session() as s:
        return ok(
            releases.transition(s, identifier, body.to_status, actor=body.actor)
        )


@router.post("/{identifier}/lane-order")
def lane_order(identifier: str, body: ReleaseLaneOrderIn):
    with writable_session() as s:
        return ok(releases.set_lane_order(s, identifier, body.order))


@router.patch("/{identifier}")
def patch(identifier: str, body: ReleasePatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            releases.patch_release(s, identifier, references=references, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(releases.delete_release(s, identifier))
