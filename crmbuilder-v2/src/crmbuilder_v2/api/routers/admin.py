"""Live-server administration endpoints — connection + schema introspection.

The API serves the single unified database; the active engagement is
selected per request by the ``X-Engagement`` header (PI-β). There is no
in-process engagement re-routing — switching engagements is a client-side
context change (the desktop sends a different header and refreshes).

* ``GET /admin/connection`` reports which DB the live server is bound to.
* ``GET /admin/version`` reports the API version and the unified DB's
  schema version.
"""

from __future__ import annotations

from fastapi import APIRouter

import crmbuilder_v2
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.migration.version_info import schema_version

router = APIRouter(prefix="/admin", tags=["meta"])


def _connection_payload() -> dict:
    """Snapshot of the DB the live process is currently bound to."""
    s = get_settings()
    db_path = s.db_path
    db_exists = db_path.exists()
    return {
        "db_path": str(db_path),
        "db_exists": db_exists,
        "db_size_bytes": db_path.stat().st_size if db_exists else None,
        "database_url_configured": bool(s.database_url),
        "api_base_url": s.api_base_url,
    }


@router.get("/connection")
def get_connection():
    """Report which DB the live API is currently bound to."""
    return ok(_connection_payload())


@router.get("/version")
def get_version():
    """Report API version and the unified DB's schema version.

    ``api_version`` is the running package version. ``schema`` carries
    ``current`` (the revision the DB is stamped at), ``head`` (the chain's
    latest), and ``up_to_date``.
    """
    return ok(
        {
            "api_version": crmbuilder_v2.__version__,
            "schema": schema_version().to_dict(),
        }
    )
