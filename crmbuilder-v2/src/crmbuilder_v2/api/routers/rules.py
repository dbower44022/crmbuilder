"""Rule endpoints (PRJ-025 PI-189 slice 2).

The eight standard methodology routes for the condition-carrying
required/visible/valid gate (``engine-neutral-design-model-and-adapters.md``
§8). Each delegates to :mod:`crmbuilder_v2.access.repositories.rule`; bodies
use the parent-prefixed ``rule_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import rule
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import RuleCreateIn, RulePatchIn, RuleReplaceIn

router = APIRouter(prefix="/rules", tags=["rules"])

_PREFIX = "rule_"


@router.get("")
def list_all(
    subject_type: str | None = None,
    subject_identifier: str | None = None,
    effect: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            rule.list_rules(
                s,
                subject_type=subject_type,
                subject_identifier=subject_identifier,
                effect=effect,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``RUL-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": rule.next_rule_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = rule.get_rule(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("rule", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: RuleCreateIn):
    with writable_session() as s:
        return ok(
            rule.create_rule(
                s,
                name=body.rule_name,
                subject_type=body.rule_subject_type,
                subject_identifier=body.rule_subject_identifier,
                effect=body.rule_effect,
                condition=body.rule_condition,
                message=body.rule_message,
                description=body.rule_description,
                notes=body.rule_notes,
                status=body.rule_status,
                identifier=body.rule_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: RuleReplaceIn):
    with writable_session() as s:
        return ok(
            rule.update_rule(
                s,
                identifier,
                rule_identifier=body.rule_identifier,
                name=body.rule_name,
                subject_type=body.rule_subject_type,
                subject_identifier=body.rule_subject_identifier,
                effect=body.rule_effect,
                condition=body.rule_condition,
                message=body.rule_message,
                description=body.rule_description,
                notes=body.rule_notes,
                status=body.rule_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: RulePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(rule.patch_rule(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(rule.delete_rule(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(rule.restore_rule(s, identifier))
