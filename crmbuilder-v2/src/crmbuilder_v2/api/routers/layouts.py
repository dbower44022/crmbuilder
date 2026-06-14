"""Layout endpoints — PI-193 (PRJ-027).

The eight standard methodology routes for the engine-neutral entity layout.
Each delegates to :mod:`crmbuilder_v2.access.repositories.layouts`; bodies use
the parent-prefixed ``layout_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import layouts
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    LayoutCreateIn,
    LayoutPatchIn,
    LayoutReplaceIn,
)

router = APIRouter(prefix="/layouts", tags=["layouts"])

_PREFIX = "layout_"


@router.get("")
def list_all(
    include_deleted: bool = False,
    entity_identifier: str | None = None,
    layout_type: str | None = None,
):
    with readonly_session() as s:
        return ok(
            layouts.list_layouts(
                s,
                include_deleted=include_deleted,
                entity_identifier=entity_identifier,
                layout_type=layout_type,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``LAY-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": layouts.next_layout_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = layouts.get_layout(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("layout", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: LayoutCreateIn):
    with writable_session() as s:
        return ok(
            layouts.create_layout(
                s,
                entity_identifier=body.layout_entity_identifier,
                layout_type=body.layout_type,
                content=body.layout_content,
                status=body.layout_status or "candidate",
                notes=body.layout_notes,
                identifier=body.layout_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: LayoutReplaceIn):
    with writable_session() as s:
        return ok(
            layouts.update_layout(
                s,
                identifier,
                layout_identifier=body.layout_identifier,
                entity_identifier=body.layout_entity_identifier,
                layout_type=body.layout_type,
                content=body.layout_content,
                status=body.layout_status or "candidate",
                notes=body.layout_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: LayoutPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged). The prefix is stripped to the repo's
    # patchable kwargs, except ``layout_type`` which the repo keeps verbatim.
    provided = body.model_dump(exclude_unset=True)
    fields = {}
    for key, value in provided.items():
        short = key[len(_PREFIX):] if key.startswith(_PREFIX) else key
        if short == "type":
            short = "layout_type"
        fields[short] = value
    with writable_session() as s:
        return ok(layouts.patch_layout(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(layouts.delete_layout(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(layouts.restore_layout(s, identifier))
