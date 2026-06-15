"""Filtered-tab endpoints — PI-195 (PRJ-027).

The eight standard methodology routes for the engine-neutral filtered tab. Each
delegates to :mod:`crmbuilder_v2.access.repositories.filtered_tabs`; bodies use
the parent-prefixed ``filtered_tab_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope. Static routes (``next-identifier``) precede
``/{identifier}`` — route order is load-bearing.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import filtered_tabs
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FilteredTabCreateIn,
    FilteredTabPatchIn,
    FilteredTabReplaceIn,
)

router = APIRouter(prefix="/filtered-tabs", tags=["filtered-tabs"])

_PREFIX = "filtered_tab_"


@router.get("")
def list_all(
    include_deleted: bool = False,
    entity_identifier: str | None = None,
    label: str | None = None,
):
    with readonly_session() as s:
        return ok(
            filtered_tabs.list_filtered_tabs(
                s,
                include_deleted=include_deleted,
                entity_identifier=entity_identifier,
                label=label,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FTB-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": filtered_tabs.next_filtered_tab_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = filtered_tabs.get_filtered_tab(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("filtered_tab", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FilteredTabCreateIn):
    with writable_session() as s:
        return ok(
            filtered_tabs.create_filtered_tab(
                s,
                entity_identifier=body.filtered_tab_entity_identifier,
                label=body.filtered_tab_label,
                filter=body.filtered_tab_filter,
                status=body.filtered_tab_status or "candidate",
                notes=body.filtered_tab_notes,
                identifier=body.filtered_tab_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FilteredTabReplaceIn):
    with writable_session() as s:
        return ok(
            filtered_tabs.update_filtered_tab(
                s,
                identifier,
                filtered_tab_identifier=body.filtered_tab_identifier,
                entity_identifier=body.filtered_tab_entity_identifier,
                label=body.filtered_tab_label,
                filter=body.filtered_tab_filter,
                status=body.filtered_tab_status or "candidate",
                notes=body.filtered_tab_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FilteredTabPatchIn):
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(filtered_tabs.patch_filtered_tab(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(filtered_tabs.delete_filtered_tab(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(filtered_tabs.restore_filtered_tab(s, identifier))
