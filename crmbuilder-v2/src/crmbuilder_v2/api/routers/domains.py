"""Domains endpoints — the first methodology entity type (UI v0.4 slice B).

The eight standard endpoints from ``domain.md`` section 3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.domain`
repository; request/response bodies use the parent-prefixed
``domain_*`` field names. Error responses use the v2 envelope, except
disallowed status transitions, which the dedicated
``status_transition_handler`` renders with the spec's
``{"error": ..., "from": ..., "to": ...}`` shape.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import domain
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    DomainCreateIn,
    DomainPatchIn,
    DomainReplaceIn,
)

router = APIRouter(prefix="/domains", tags=["domains"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "domain_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(domain.list_domains(s, include_deleted=include_deleted))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``DOM-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": domain.next_domain_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = domain.get_domain(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("domain", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: DomainCreateIn):
    with writable_session() as s:
        return ok(
            domain.create_domain(
                s,
                name=body.domain_name,
                purpose=body.domain_purpose,
                description=body.domain_description,
                notes=body.domain_notes,
                status=body.domain_status,
                identifier=body.domain_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: DomainReplaceIn):
    with writable_session() as s:
        return ok(
            domain.update_domain(
                s,
                identifier,
                domain_identifier=body.domain_identifier,
                name=body.domain_name,
                purpose=body.domain_purpose,
                description=body.domain_description,
                notes=body.domain_notes,
                status=body.domain_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: DomainPatchIn):
    # ``exclude_unset`` keeps an explicit ``domain_notes: null`` (clear)
    # distinct from an omitted ``domain_notes`` (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(domain.patch_domain(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(domain.delete_domain(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(domain.restore_domain(s, identifier))
