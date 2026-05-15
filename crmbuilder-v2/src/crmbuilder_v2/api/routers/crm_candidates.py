"""CRM Candidates endpoints — the fourth methodology entity type (UI v0.4 slice E).

The eight standard endpoints from ``crm_candidate.md`` section 3.5.1.
Each delegates to the
:mod:`crmbuilder_v2.access.repositories.crm_candidate` repository;
request/response bodies use the parent-prefixed ``crm_candidate_*``
field names. Error responses use the v2 envelope, except the two
dedicated-body access-layer errors:

* ``StatusTransitionError`` → HTTP 422 with
  ``{"error": "invalid_status_transition", "from": ..., "to": ...}``
* ``SelectedCandidateConflictError`` → HTTP 422 with
  ``{"error": "selected_candidate_already_exists", "existing": "CRM-NNN"}``

both rendered by their dedicated handlers registered in
:mod:`crmbuilder_v2.api.main`.

``crm_candidate`` has no outgoing references in v0.4 — there is no
inline-reference payload here; inbound governance-entity citations
attach via the existing ``POST /references`` route per the universal
vocab kinds.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import crm_candidate
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    CrmCandidateCreateIn,
    CrmCandidatePatchIn,
    CrmCandidateReplaceIn,
)

router = APIRouter(prefix="/crm_candidates", tags=["crm_candidates"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "crm_candidate_"


@router.get("")
def list_all(include_deleted: bool = False):
    with readonly_session() as s:
        return ok(
            crm_candidate.list_crm_candidates(
                s, include_deleted=include_deleted
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``CRM-NNN`` identifier."""
    with readonly_session() as s:
        return ok(
            {"next": crm_candidate.next_crm_candidate_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = crm_candidate.get_crm_candidate(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("crm_candidate", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: CrmCandidateCreateIn):
    with writable_session() as s:
        return ok(
            crm_candidate.create_crm_candidate(
                s,
                name=body.crm_candidate_name,
                fit_reason=body.crm_candidate_fit_reason,
                notes=body.crm_candidate_notes,
                status=body.crm_candidate_status,
                identifier=body.crm_candidate_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: CrmCandidateReplaceIn):
    with writable_session() as s:
        return ok(
            crm_candidate.update_crm_candidate(
                s,
                identifier,
                crm_candidate_identifier=body.crm_candidate_identifier,
                name=body.crm_candidate_name,
                fit_reason=body.crm_candidate_fit_reason,
                notes=body.crm_candidate_notes,
                status=body.crm_candidate_status,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: CrmCandidatePatchIn):
    # ``exclude_unset`` keeps an explicit ``crm_candidate_notes: null``
    # (clear) distinct from an omitted ``crm_candidate_notes`` (leave
    # unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            crm_candidate.patch_crm_candidate(s, identifier, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(crm_candidate.delete_crm_candidate(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(crm_candidate.restore_crm_candidate(s, identifier))
