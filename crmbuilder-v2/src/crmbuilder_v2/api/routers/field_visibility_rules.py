"""Field-visibility-rule endpoints (PI-051 / REQ-128, DEC-698).

The eight standard methodology routes for the security design record declaring
one atomic ``(role, field) -> visible?`` decision. Each delegates to
:mod:`crmbuilder_v2.access.repositories.field_visibility_rule`; bodies use the
parent-prefixed ``field_visibility_rule_*`` field names. Error responses use the
v2 ``{data, meta, errors}`` envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import field_visibility_rule
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FieldVisibilityRuleCreateIn,
    FieldVisibilityRulePatchIn,
    FieldVisibilityRuleReplaceIn,
)

router = APIRouter(
    prefix="/field-visibility-rules", tags=["field-visibility-rules"]
)

_PREFIX = "field_visibility_rule_"


@router.get("")
def list_all(
    role: str | None = None,
    target_field: str | None = None,
    deployment_status: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            field_visibility_rule.list_field_visibility_rules(
                s,
                role=role,
                target_field=target_field,
                deployment_status=deployment_status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``FVR-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {
                "next": (
                    field_visibility_rule
                    .next_field_visibility_rule_identifier(s)
                )
            }
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = field_visibility_rule.get_field_visibility_rule(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("field_visibility_rule", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FieldVisibilityRuleCreateIn):
    with writable_session() as s:
        return ok(
            field_visibility_rule.create_field_visibility_rule(
                s,
                name=body.field_visibility_rule_name,
                role=body.field_visibility_rule_role,
                target_field=body.field_visibility_rule_target_field,
                visible=body.field_visibility_rule_visible,
                status=body.field_visibility_rule_status,
                deployment_status=(
                    body.field_visibility_rule_deployment_status
                ),
                description=body.field_visibility_rule_description,
                notes=body.field_visibility_rule_notes,
                identifier=body.field_visibility_rule_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FieldVisibilityRuleReplaceIn):
    with writable_session() as s:
        return ok(
            field_visibility_rule.update_field_visibility_rule(
                s,
                identifier,
                field_visibility_rule_identifier=(
                    body.field_visibility_rule_identifier
                ),
                name=body.field_visibility_rule_name,
                role=body.field_visibility_rule_role,
                target_field=body.field_visibility_rule_target_field,
                visible=body.field_visibility_rule_visible,
                status=body.field_visibility_rule_status,
                deployment_status=(
                    body.field_visibility_rule_deployment_status
                ),
                description=body.field_visibility_rule_description,
                notes=body.field_visibility_rule_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FieldVisibilityRulePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            field_visibility_rule.patch_field_visibility_rule(
                s, identifier, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(
            field_visibility_rule.delete_field_visibility_rule(s, identifier)
        )


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(
            field_visibility_rule.restore_field_visibility_rule(s, identifier)
        )
