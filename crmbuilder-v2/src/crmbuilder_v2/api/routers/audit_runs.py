"""Audit-run read endpoints — PI-448 (REQ-551 / DEC-994).

An audit run (``ARN-NNN``) is the background-job record for an audit area too
long for one HTTP request — today the opt-in utilization area. It is started
by ``POST /instances/{id}/audit-runs`` (that route lives with the other
instance-audit endpoints); this router serves the polling side: the caller
reads progress while the run executes and the outcome afterwards, so a client
disconnect never touches the run itself. Responses use the ``{data, meta,
errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import audit_runs
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/audit-runs", tags=["audit-runs"])


@router.get("")
def list_all(
    instance: str | None = None,
    status: str | None = None,
    limit: int | None = None,
):
    """Audit runs newest first, optionally filtered by instance or status."""
    with readonly_session() as s:
        return ok(
            audit_runs.list_audit_runs(
                s, instance_identifier=instance, status=status, limit=limit
            )
        )


@router.get("/{identifier}")
def get(identifier: str):
    """One run in full: status, live progress counters, log, summary, error."""
    with readonly_session() as s:
        row = audit_runs.get_audit_run(s, identifier)
        if row is None:
            raise NotFoundError("audit_run", identifier)
        return ok(row)
