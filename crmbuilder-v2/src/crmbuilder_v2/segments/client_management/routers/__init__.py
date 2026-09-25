"""The Client Management routers, declared for the segment registry
(PI-508 / REQ-591). ``api.main`` includes every router in ``routers``.
"""

from __future__ import annotations

from crmbuilder_v2.segments.client_management.routers import (
    applications,
    clients,
    engagements,
    participant,
    principals,
)

routers = (
    principals.router,
    engagements.router,
    applications.router,
    participant.router,
    clients.router,
)
