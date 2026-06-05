"""Glossary term endpoints (PI-061 — DEC-403/DEC-390).

The standard list / next-identifier / get / create (POST) / update (PATCH) /
delete set under the ``{data, meta, errors}`` envelope. A ``term`` is a
system/shared record with a nullable ``engagement_id`` scope: ``scope`` is
``system`` for a universal term, or an engagement identifier for an overlay.
The MCP tool surface for terms is deferred to a later task (DEC-404).
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import terms
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import TermCreateIn, TermUpdateIn

router = APIRouter(prefix="/terms", tags=["terms"])


@router.get("")
def list_terms(status: str | None = None, scope: str | None = None):
    with readonly_session() as s:
        return ok(terms.list_all(s, status=status, scope=scope))


@router.get("/next-identifier")
def term_next_identifier():
    with readonly_session() as s:
        return ok({"next": terms.compute_next_identifier(s)})


@router.get("/{identifier}")
def get_term(identifier: str):
    with readonly_session() as s:
        return ok(terms.get(s, identifier))


@router.post("", status_code=201)
def create_term(body: TermCreateIn):
    with writable_session() as s:
        return ok(terms.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update_term(identifier: str, body: TermUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(terms.update(s, identifier, scope=scope, **provided))


@router.delete("/{identifier}")
def delete_term(identifier: str):
    with writable_session() as s:
        return ok(terms.delete(s, identifier))
