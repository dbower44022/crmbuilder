"""Processes endpoints — the third methodology entity type (UI v0.4 slice D).

The eight standard endpoints from ``process.md`` section 3.5.1. Each
delegates to the :mod:`crmbuilder_v2.access.repositories.process`
repository; request/response bodies use the parent-prefixed
``process_*`` field names. Error responses use the v2 envelope, except
the two dedicated-body access-layer errors:

* ``ClassificationTransitionError`` → HTTP 422 with
  ``{"error": "invalid_classification_transition", "from": ..., "to": ...}``
* ``InvalidDomainReferenceError`` → HTTP 422 with
  ``{"error": "invalid_domain_reference", "domain_identifier": ...}``

both rendered by their dedicated handlers registered in
:mod:`crmbuilder_v2.api.main`.

Per ``process.md`` section 3.5.5 handoff handling is decomposed: there
is no ``/processes/{id}/handoffs`` shortcut and no inline-handoff field
in the create/update bodies. Process-to-process handoffs attach via the
existing ``POST /references`` route with the
``process_hands_off_to_process`` relationship kind.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import process
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.routers.utilization_evidence import embed_inline_evidence
from crmbuilder_v2.api.schemas import (
    ProcessCreateIn,
    ProcessPatchIn,
    ProcessReplaceIn,
)

router = APIRouter(prefix="/processes", tags=["processes"])

# The REST bodies carry parent-prefixed field names; the repository
# functions take the unprefixed kwargs. This is the prefix the router
# strips when forwarding a PATCH body.
_FIELD_PREFIX = "process_"


@router.get("")
def list_all(include_deleted: bool = False, include_evidence: str | None = None):
    with readonly_session() as s:
        records = process.list_processes(s, include_deleted=include_deleted)
        return ok(
            embed_inline_evidence(
                s,
                records,
                subject_type="process",
                identifier_key="process_identifier",
                include_evidence=include_evidence,
                is_list=True,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``PROC-NNN`` identifier."""
    with readonly_session() as s:
        return ok({"next": process.next_process_identifier(s)})


@router.get("/{identifier}")
def get(
    identifier: str,
    include_deleted: bool = False,
    include_evidence: str | None = None,
):
    with readonly_session() as s:
        record = process.get_process(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("process", identifier)
        embed_inline_evidence(
            s,
            [record],
            subject_type="process",
            identifier_key="process_identifier",
            include_evidence=include_evidence,
            is_list=False,
        )
        return ok(record)


@router.post("", status_code=201)
def create(body: ProcessCreateIn):
    with writable_session() as s:
        return ok(
            process.create_process(
                s,
                name=body.process_name,
                domain_identifier=body.process_domain_identifier,
                purpose=body.process_purpose,
                classification=body.process_classification,
                classification_rationale=body.process_classification_rationale,
                notes=body.process_notes,
                identifier=body.process_identifier,
                steps=body.process_steps,
                triggers=body.process_triggers,
                outcomes=body.process_outcomes,
                edge_cases=body.process_edge_cases,
                frequency=body.process_frequency,
                duration_estimate=body.process_duration_estimate,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ProcessReplaceIn):
    with writable_session() as s:
        return ok(
            process.update_process(
                s,
                identifier,
                process_identifier=body.process_identifier,
                name=body.process_name,
                domain_identifier=body.process_domain_identifier,
                purpose=body.process_purpose,
                classification=body.process_classification,
                classification_rationale=body.process_classification_rationale,
                notes=body.process_notes,
                steps=body.process_steps,
                triggers=body.process_triggers,
                outcomes=body.process_outcomes,
                edge_cases=body.process_edge_cases,
                frequency=body.process_frequency,
                duration_estimate=body.process_duration_estimate,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ProcessPatchIn):
    # ``exclude_unset`` keeps an explicit ``process_notes: null`` (clear)
    # distinct from an omitted ``process_notes`` (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(process.patch_process(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(process.delete_process(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(process.restore_process(s, identifier))
