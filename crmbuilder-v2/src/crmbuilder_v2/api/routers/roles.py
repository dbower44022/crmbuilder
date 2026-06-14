"""Role endpoints — PI-194 (PRJ-027).

The eight standard methodology routes for the engine-neutral security role.
Each delegates to :mod:`crmbuilder_v2.access.repositories.roles`; bodies use the
parent-prefixed ``role_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import roles
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import RoleCreateIn, RolePatchIn, RoleReplaceIn

router = APIRouter(prefix="/roles", tags=["roles"])

_PREFIX = "role_"


@router.get("")
def list_all(include_deleted: bool = False, name: str | None = None):
    with readonly_session() as s:
        return ok(
            roles.list_roles(s, include_deleted=include_deleted, name=name)
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``ROL-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": roles.next_role_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = roles.get_role(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("role", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: RoleCreateIn):
    with writable_session() as s:
        return ok(
            roles.create_role(
                s,
                name=body.role_name,
                scope_access=body.role_scope_access,
                system_permissions=body.role_system_permissions,
                description=body.role_description,
                status=body.role_status or "candidate",
                notes=body.role_notes,
                identifier=body.role_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: RoleReplaceIn):
    with writable_session() as s:
        return ok(
            roles.update_role(
                s,
                identifier,
                role_identifier=body.role_identifier,
                name=body.role_name,
                scope_access=body.role_scope_access,
                system_permissions=body.role_system_permissions,
                description=body.role_description,
                status=body.role_status or "candidate",
                notes=body.role_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: RolePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(roles.patch_role(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(roles.delete_role(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(roles.restore_role(s, identifier))
