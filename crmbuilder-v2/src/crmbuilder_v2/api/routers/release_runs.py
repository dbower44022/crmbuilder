"""Release-run endpoints — the run-outcome satellite (PI-326, DEC-742).

Reduced API surface, mirroring ``deposit_event``: POST and GET only. PUT, PATCH,
DELETE, and restore are intentionally NOT registered — the record is born-terminal
append-only, so the framework returns HTTP 405 for those methods. POST is the only
write; the access layer makes it atomic (record + ``release_run_relates_to_finding``
edges). See preserve-failed-run-history-design.md §3.3.

Two routers: ``router`` owns ``/release-runs`` (create + get-by-id);
``release_scoped_router`` adds the release-nested ``GET /releases/{id}/runs`` list
(a release may have run the lane more than once — not 1:1).
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import release_runs
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import ReleaseRunCreateIn

router = APIRouter(prefix="/release-runs", tags=["release-runs"])
release_scoped_router = APIRouter(prefix="/releases", tags=["release-runs"])


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": release_runs.next_release_run_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        record = release_runs.get(s, identifier)
        if record is None:
            raise NotFoundError("release_run", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ReleaseRunCreateIn):
    with writable_session() as s:
        return ok(
            release_runs.record(
                s,
                release_identifier=body.release_identifier,
                outcome=body.release_run_outcome,
                scope=body.release_run_scope,
                phases_run=body.release_run_phases_run,
                halt_point=body.release_run_halt_point,
                cause=body.release_run_cause,
                cause_code=body.release_run_cause_code,
                finding_identifiers=body.finding_identifiers,
                identifier=body.release_run_identifier,
            )
        )


@release_scoped_router.get("/{release_identifier}/runs")
def list_for_release(release_identifier: str):
    with readonly_session() as s:
        return ok(release_runs.list_for_release(s, release_identifier))
