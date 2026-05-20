"""Live-server administration endpoints — connection introspection and
in-process engagement re-routing.

The API process binds to a single engagement's per-engagement SQLite DB,
fixed at spawn time via ``CRMBUILDER_V2_DB_PATH`` and the lru-cached
``Settings``. Switching engagements without restarting the process means
re-routing in place: :func:`route_settings_to_engagement` resets the
settings + engine caches and re-inits the meta-DB pool.

* ``POST /admin/active-engagement`` exposes that re-routing so the desktop
  UI's engagement switch works regardless of whether the API subprocess is
  owned by the UI or run externally (``crmbuilder-v2-api &``). Without it,
  the old kill-and-relaunch switch could not affect an externally-launched
  API (the UI does not own that process), so the displayed data never
  changed.
* ``GET /admin/connection`` lets the UI's Connection Info dialog verify
  which DB the live server is actually bound to.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import crmbuilder_v2
from crmbuilder_v2.api.envelope import err, ok
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.migration.version_info import (
    engagement_schema_version,
    meta_schema_version,
)
from crmbuilder_v2.runtime.engagement_routing import (
    UNCONFIGURED_SENTINEL,
    route_settings_to_engagement,
)
from crmbuilder_v2.runtime.exceptions import UnknownEngagementError

router = APIRouter(prefix="/admin", tags=["meta"])


class ActiveEngagementIn(BaseModel):
    engagement_code: str


def _connection_payload() -> dict:
    """Snapshot of the engagement DB the live process is currently bound to."""
    s = get_settings()
    db_path = s.db_path
    export_raw = str(s.export_dir)
    export_configured = export_raw != UNCONFIGURED_SENTINEL
    db_exists = db_path.exists()
    # Derive the code from the actually-bound DB filename
    # (``engagements/{code}.db``) rather than the marker file, so the
    # report reflects the live routing even if the marker lags.
    return {
        "engagement_code": db_path.stem,
        "db_path": str(db_path),
        "db_exists": db_exists,
        "db_size_bytes": db_path.stat().st_size if db_exists else None,
        "export_dir": export_raw if export_configured else None,
        "export_dir_configured": export_configured,
        "export_dir_exists": export_configured and s.export_dir.is_dir(),
        "api_base_url": s.api_base_url,
    }


@router.get("/connection")
def get_connection():
    """Report which engagement DB the live API is currently bound to."""
    return ok(_connection_payload())


@router.get("/version")
def get_version():
    """Report API version and the schema versions of the live + meta DBs.

    ``api_version`` is the running package version. ``engagement_schema``
    reflects the *active* engagement's DB; ``meta_schema`` the registry.
    Each schema block carries ``current`` (the revision the DB is stamped
    at), ``head`` (the chain's latest), and ``up_to_date``.
    """
    return ok(
        {
            "api_version": crmbuilder_v2.__version__,
            "engagement_schema": engagement_schema_version().to_dict(),
            "meta_schema": meta_schema_version().to_dict(),
        }
    )


@router.post("/active-engagement")
def set_active_engagement(body: ActiveEngagementIn):
    """Re-route the live API in-process to ``engagement_code``.

    Resets the settings + engine caches so subsequent requests read the
    target engagement's DB. No subprocess restart — works whether the API
    is UI-owned or externally launched.
    """
    try:
        route_settings_to_engagement(body.engagement_code)
    except UnknownEngagementError as exc:
        return JSONResponse(
            status_code=404,
            content=err([{"code": "unknown_engagement", "detail": str(exc)}]),
        )
    return ok(_connection_payload())
