"""View endpoints (PRJ-025 PI-189 slice 2).

The eight standard methodology routes for the condition-carrying list view
(``engine-neutral-design-model-and-adapters.md`` §8). Each delegates to
:mod:`crmbuilder_v2.access.repositories.view`; bodies use the parent-prefixed
``view_*`` field names. Error responses use the v2 ``{data, meta, errors}``
envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import view
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import ViewCreateIn, ViewPatchIn, ViewReplaceIn

router = APIRouter(prefix="/views", tags=["views"])

_PREFIX = "view_"


@router.get("")
def list_all(entity: str | None = None, include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            view.list_views(
                s, entity=entity, include_deleted=include_deleted
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``VEW-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": view.next_view_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = view.get_view(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("view", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ViewCreateIn):
    with writable_session() as s:
        return ok(
            view.create_view(
                s,
                name=body.view_name,
                entity=body.view_entity,
                columns=body.view_columns,
                filter=body.view_filter,
                sort_field=body.view_sort_field,
                sort_direction=body.view_sort_direction,
                description=body.view_description,
                notes=body.view_notes,
                status=body.view_status,
                identifier=body.view_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ViewReplaceIn):
    with writable_session() as s:
        return ok(
            view.update_view(
                s,
                identifier,
                view_identifier=body.view_identifier,
                name=body.view_name,
                entity=body.view_entity,
                columns=body.view_columns,
                filter=body.view_filter,
                sort_field=body.view_sort_field,
                sort_direction=body.view_sort_direction,
                description=body.view_description,
                notes=body.view_notes,
                status=body.view_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ViewPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(view.patch_view(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(view.delete_view(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(view.restore_view(s, identifier))
