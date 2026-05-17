"""Engagement-registry endpoints (v0.5 slice A — healthcheck only).

Slice A wires the two-database API so the meta-DB pool is exercised
via ``/engagements/healthcheck``. Slice B adds the full eight-endpoint
CRUD surface and removes the healthcheck (or keeps it alongside,
depending on slice B's choice). The healthcheck is the
minimum-viable endpoint to verify the meta-DB connection is alive.
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from crmbuilder_v2.api.deps import meta_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/engagements", tags=["engagements"])


@router.get("/healthcheck")
def healthcheck() -> dict:
    """Verify the meta-DB connection is alive; return engagement count."""
    with meta_session() as s:
        count = s.execute(
            text("SELECT COUNT(*) FROM engagements")
        ).scalar_one()
    return ok({"status": "ok", "engagement_count": int(count)})
