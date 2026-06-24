"""Field-permission-rule endpoints (PI-051 / REQ-129, DEC-698).

The eight standard methodology routes for the security design record declaring
one unconditional (role × target_field) -> permission level. Each delegates to
:mod:`crmbuilder_v2.access.repositories.field_permission_rule`; bodies use the
parent-prefixed ``field_permission_rule_*`` field names. Error responses use the
v2 ``{data, meta, errors}`` envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import field_permission_rule
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FieldPermissionRuleCreateIn,
    FieldPermissionRulePatchIn,
    FieldPermissionRuleReplaceIn,
)

router = APIRouter(
    prefix="/field-permission-rules", tags=["field-permission-rules"]
)

_PREFIX = "field_permission_rule_"


@router.get("")
def list_all(
    role: str | None = None,
    target_field: str | None = None,
    deployment_status: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            field_permission_rule.list_field_permission_rules(
                s,
                role=role,
                target_field=target_field,
                deployment_status=deployment_status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FPR-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {
                "next": (
                    field_permission_rule
                    .next_field_permission_rule_identifier(s)
                )
            }
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = field_permission_rule.get_field_permission_rule(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("field_permission_rule", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FieldPermissionRuleCreateIn):
    with writable_session() as s:
        return ok(
            field_permission_rule.create_field_permission_rule(
                s,
                name=body.field_permission_rule_name,
                role=body.field_permission_rule_role,
                target_field=body.field_permission_rule_target_field,
                permission_level=(
                    body.field_permission_rule_permission_level
                ),
                status=body.field_permission_rule_status,
                deployment_status=(
                    body.field_permission_rule_deployment_status
                ),
                description=body.field_permission_rule_description,
                notes=body.field_permission_rule_notes,
                identifier=body.field_permission_rule_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FieldPermissionRuleReplaceIn):
    with writable_session() as s:
        return ok(
            field_permission_rule.update_field_permission_rule(
                s,
                identifier,
                field_permission_rule_identifier=(
                    body.field_permission_rule_identifier
                ),
                name=body.field_permission_rule_name,
                role=body.field_permission_rule_role,
                target_field=body.field_permission_rule_target_field,
                permission_level=(
                    body.field_permission_rule_permission_level
                ),
                status=body.field_permission_rule_status,
                deployment_status=(
                    body.field_permission_rule_deployment_status
                ),
                description=body.field_permission_rule_description,
                notes=body.field_permission_rule_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FieldPermissionRulePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            field_permission_rule.patch_field_permission_rule(
                s, identifier, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(
            field_permission_rule.delete_field_permission_rule(s, identifier)
        )


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(
            field_permission_rule.restore_field_permission_rule(s, identifier)
        )
