"""The Operate routers, declared for the segment registry (PI-513 / REQ-591).
``api.main`` includes every router in ``routers``.

The instances router also serves Build's operations on an instance (audit,
publish, conformance, memberships, record export); they move to the Build
package when Build moves. Until then the whole file lives here because the
instance is created here.
"""

from __future__ import annotations

from crmbuilder_v2.segments.operate.routers import (
    deploy_runs,
    instances,
    provider_credentials,
)

routers = (instances.router, deploy_runs.router, provider_credentials.router)
