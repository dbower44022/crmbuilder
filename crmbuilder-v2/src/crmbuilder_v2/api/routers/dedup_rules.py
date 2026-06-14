"""Dedup-rule endpoints (PRJ-025 PI-189 slice 3).

The eight standard methodology routes for the duplicate-detection design record
(``engine-neutral-design-model-and-adapters.md`` §8). Each delegates to
:mod:`crmbuilder_v2.access.repositories.dedup_rule`; bodies use the
parent-prefixed ``dedup_rule_*`` field names. Error responses use the v2
``{data, meta, errors}`` envelope, except disallowed status transitions (the
``status_transition_handler`` flat shape).

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import dedup_rule
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    DedupRuleCreateIn,
    DedupRulePatchIn,
    DedupRuleReplaceIn,
)

router = APIRouter(prefix="/dedup-rules", tags=["dedup-rules"])

_PREFIX = "dedup_rule_"


@router.get("")
def list_all(entity: str | None = None, include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            dedup_rule.list_dedup_rules(
                s, entity=entity, include_deleted=include_deleted
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``DUP-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": dedup_rule.next_dedup_rule_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = dedup_rule.get_dedup_rule(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("dedup_rule", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: DedupRuleCreateIn):
    with writable_session() as s:
        return ok(
            dedup_rule.create_dedup_rule(
                s,
                name=body.dedup_rule_name,
                entity=body.dedup_rule_entity,
                match_fields=body.dedup_rule_match_fields,
                on_match=body.dedup_rule_on_match,
                normalize=body.dedup_rule_normalize,
                message=body.dedup_rule_message,
                description=body.dedup_rule_description,
                notes=body.dedup_rule_notes,
                status=body.dedup_rule_status,
                identifier=body.dedup_rule_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: DedupRuleReplaceIn):
    with writable_session() as s:
        return ok(
            dedup_rule.update_dedup_rule(
                s,
                identifier,
                dedup_rule_identifier=body.dedup_rule_identifier,
                name=body.dedup_rule_name,
                entity=body.dedup_rule_entity,
                match_fields=body.dedup_rule_match_fields,
                on_match=body.dedup_rule_on_match,
                normalize=body.dedup_rule_normalize,
                message=body.dedup_rule_message,
                description=body.dedup_rule_description,
                notes=body.dedup_rule_notes,
                status=body.dedup_rule_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: DedupRulePatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(dedup_rule.patch_dedup_rule(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(dedup_rule.delete_dedup_rule(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(dedup_rule.restore_dedup_rule(s, identifier))
