"""Publish-run history endpoints — PI-266 (PRJ-042 / REQ-293).

Read-only surfaces over the ``publish_runs`` log recorded by the publish path
(PI-262 / REQ-292). ``GET /publish-runs`` lists runs newest-first (optionally
filtered by target instance); ``GET /publish-runs/{identifier}`` returns one
run's full detail including its pre-publish backup snapshot. Runs are written
only by the publish service — there is no create/update/delete here. All
responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import publish_runs
from crmbuilder_v2.api.deps import readonly_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/publish-runs", tags=["publish-runs"])


@router.get("")
def list_all(instance: str | None = None, limit: int | None = None):
    """List publish runs, newest first, optionally filtered by target instance."""
    with readonly_session() as s:
        return ok(
            publish_runs.list_publish_runs(
                s, instance_identifier=instance, limit=limit
            )
        )


@router.get("/{identifier}")
def get(identifier: str):
    """Return one publish run's full detail (incl. its backup snapshot)."""
    with readonly_session() as s:
        record = publish_runs.get_publish_run(s, identifier)
        if record is None:
            raise NotFoundError("publish_run", identifier)
        return ok(record)
