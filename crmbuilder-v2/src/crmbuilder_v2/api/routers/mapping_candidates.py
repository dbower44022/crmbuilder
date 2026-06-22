"""Mapping candidate endpoints — PI-255 (PRJ-027).

Reconciler output: unmatched source entities / fields / values surfaced by an
audit, optionally carrying a confidence-ranked suggested mapping, that a human
resolves into a real mapping (integer PK, no prefixed identifier). Each delegates
to :mod:`crmbuilder_v2.access.repositories.mapping_candidate`; responses use the
v2 ``{data, meta, errors}`` envelope.

The static ``/bulk`` route is declared before ``/{id_}`` — route order is
load-bearing, the ``layouts.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import mapping_candidate
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    MappingCandidateBulkIn,
    MappingCandidateCreateIn,
    MappingCandidateResolveIn,
)

router = APIRouter(prefix="/mapping-candidates", tags=["mapping-candidates"])


@router.get("")
def list_all(
    instance_identifier: str | None = None,
    candidate_type: str | None = None,
    resolved: bool | None = None,
):
    with readonly_session() as s:
        return ok(
            mapping_candidate.list_candidates(
                s,
                instance_identifier=instance_identifier,
                candidate_type=candidate_type,
                resolved=resolved,
            )
        )


@router.post("/bulk", status_code=201)
def bulk(body: MappingCandidateBulkIn):
    """Batch-insert reconciler candidates (no per-row change_log)."""
    candidates = [c.model_dump() for c in body.candidates]
    with writable_session() as s:
        return ok(mapping_candidate.bulk_create_candidates(s, candidates))


@router.get("/{id_}")
def get(id_: int):
    with readonly_session() as s:
        record = mapping_candidate.get_candidate(s, id_)
        if record is None:
            raise NotFoundError("mapping_candidate", str(id_))
        return ok(record)


@router.post("", status_code=201)
def create(body: MappingCandidateCreateIn):
    with writable_session() as s:
        return ok(mapping_candidate.create_candidate(s, **body.model_dump()))


@router.post("/{id_}/resolve")
def resolve(id_: int, body: MappingCandidateResolveIn):
    """Resolve a candidate into a real source / field mapping."""
    with writable_session() as s:
        return ok(
            mapping_candidate.resolve_candidate(s, id_, **body.model_dump())
        )
