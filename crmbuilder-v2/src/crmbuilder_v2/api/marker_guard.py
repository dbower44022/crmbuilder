"""Engagement-marker fail-loud guard (DEC-205).

The API binds to one engagement's database for the lifetime of the
process. The active engagement is read from current_engagement.json
once at process start. If Doug switches engagements via the desktop
UI mid-process, this middleware fails every subsequent request with
HTTP 409 rather than silently rerouting writes to the wrong database.

The marker is read on every non-exempt request via
runtime.engagement_routing.resolve_active_engagement(); the cost is a
file stat plus a small JSON read, both warm in the OS page cache after
the first request, so the per-request overhead is on the order of
single-digit microseconds.

Restart mechanism (manual ``pkill + relaunch`` in v1) is out of scope
for this guard. A desktop-UI "Restart API" button is a follow-up if
friction surfaces in actual use.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from crmbuilder_v2.runtime.engagement_routing import resolve_active_engagement

_log = logging.getLogger("crmbuilder_v2.api.marker_guard")

# Set by cli.run_api() after resolve_active_engagement() returns and
# before uvicorn boots. None means "no active engagement at start" —
# treated as a valid starting state; the guard still trips if a marker
# appears later (string != None).
_MARKER_AT_START: str | None = None

# Paths exempt from the marker guard. These must remain available even
# when the API process is bound to a stale engagement so operators can
# probe liveness and inspect schema without restarting first.
EXEMPT_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/openapi.json",
        "/docs",
        "/redoc",
    }
)


def set_marker_at_start(value: str | None) -> None:
    """Set the captured marker. Called by cli.run_api() at startup."""
    global _MARKER_AT_START
    _MARKER_AT_START = value
    _log.info("marker_guard: captured engagement at start = %r", value)


def get_marker_at_start() -> str | None:
    """Return the captured marker. Used by tests."""
    return _MARKER_AT_START


class EngagementMarkerGuardMiddleware(BaseHTTPMiddleware):
    """Reject requests when the live marker differs from the start marker."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        live_marker = resolve_active_engagement()
        if live_marker != _MARKER_AT_START:
            _log.warning(
                "marker_guard: request %s %s rejected — "
                "marker_at_start=%r marker_now=%r",
                request.method,
                request.url.path,
                _MARKER_AT_START,
                live_marker,
            )
            return JSONResponse(
                {
                    "error": "engagement_marker_changed",
                    "marker_at_start": _MARKER_AT_START,
                    "marker_now": live_marker,
                    "action": "restart API to bind to new engagement",
                },
                status_code=409,
            )
        return await call_next(request)
