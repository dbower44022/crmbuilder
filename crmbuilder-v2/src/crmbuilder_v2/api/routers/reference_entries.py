"""Reference Entry endpoints (REL-016 / PI-063, REQ-398; DEC-886/887).

The cross-engagement reference-library records (Domain Knowledge / Organization
Structure / Inventory Items). Standard registry-style surface — list /
next-identifier / get / create (POST) / update (PATCH) / delete — under the
``{data, meta, errors}`` envelope. A system/shared row with a nullable
``engagement_id`` scope, reusing the Agent Profile Registry store pattern
(DEC-886); the contextual loader (PI-066) and authoring panel (PI-067) build on
this.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.engagement_scope import get_active_engagement
from crmbuilder_v2.access.repositories import reference_entries
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ReferenceEntryCreateIn,
    ReferenceEntryUpdateIn,
)

router = APIRouter(prefix="/reference-entries", tags=["reference_entries"])


@router.get("")
def list_reference_entries(
    kind: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    with readonly_session() as s:
        return ok(
            reference_entries.list_all(s, kind=kind, status=status, scope=scope)
        )


@router.get("/next-identifier")
def reference_entry_next_identifier():
    with readonly_session() as s:
        return ok({"next": reference_entries.compute_next_identifier(s)})


@router.get("/search")
def search_reference_entries(
    q: str | None = None,
    keywords: str | None = None,
    kind: str | None = None,
    status: str = "active",
    engagement: str | None = None,
):
    """Contextual loader (PI-066 / REQ-401): match a client's defining
    statements against reference-entry ``trigger_keywords`` + ``applies_to``,
    ranked by overlap. ``q`` is the free-text statement; ``keywords`` is an
    optional comma-separated list; ``kind`` narrows to one kind (else all).
    The scope merge keeps system rows ∪ the active engagement's overlay (the
    ``engagement`` query param, else the request's active engagement)."""
    kw_list = (
        [k.strip() for k in keywords.split(",") if k.strip()] if keywords else None
    )
    active = engagement if engagement is not None else get_active_engagement()
    with readonly_session() as s:
        return ok(
            reference_entries.search_reference_entries(
                s,
                text=q,
                keywords=kw_list,
                kind=kind,
                status=status,
                engagement_id=active,
            )
        )


@router.get("/{identifier}")
def get_reference_entry(identifier: str):
    with readonly_session() as s:
        return ok(reference_entries.get(s, identifier))


@router.post("", status_code=201)
def create_reference_entry(body: ReferenceEntryCreateIn):
    with writable_session() as s:
        return ok(reference_entries.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update_reference_entry(identifier: str, body: ReferenceEntryUpdateIn):
    provided = body.model_dump(exclude_unset=True)
    scope = provided.pop("scope", None)
    with writable_session() as s:
        return ok(reference_entries.update(s, identifier, scope=scope, **provided))


@router.delete("/{identifier}")
def delete_reference_entry(identifier: str):
    with writable_session() as s:
        return ok(reference_entries.delete(s, identifier))
