"""The Client Management routers, declared for the segment registry
(PI-508 / REQ-591). ``api.main`` includes every router in ``routers``.
"""

from __future__ import annotations

from crmbuilder_v2.segments.client_management.routers import (
    engagements,
    participant,
    principals,
)

routers = (principals.router, engagements.router, participant.router)
