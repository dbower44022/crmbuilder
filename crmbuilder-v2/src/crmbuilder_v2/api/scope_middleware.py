"""Per-request engagement-scope middleware (PI-123 Slice 2c, DEC-375 / D6).

Resolves the active engagement for each request and sets it on the
``engagement_scope`` ``ContextVar`` for the duration of the request, so the
row-level read filter / write stamp (Slice 2b) scope every query and insert to
that engagement.

Resolution order (D6):

1. The ``X-Engagement`` request header — its value may be either the engagement
   **identifier** (``ENG-NNN``) or the user-facing **code** (e.g. ``CRMBUILDER``).
2. Otherwise the ``current_engagement.json`` marker (the existing single-active
   default), so a bare request keeps working exactly as today.

A pure **ASGI** middleware (not ``BaseHTTPMiddleware``): ``BaseHTTPMiddleware``
runs the endpoint in a child task where a ``ContextVar`` set in ``dispatch`` does
not reliably reach the handler, whereas a pure ASGI middleware shares the
request's context, so the active engagement reaches the handler's DB session.

Gated by ``Settings.engagement_scoping_enabled`` — when off, the middleware is a
straight pass-through (one cheap check per request) and sets nothing, so the
current runtime is unchanged.
"""

from __future__ import annotations

import logging

from crmbuilder_v2.access import engagement as engagement_repo
from crmbuilder_v2.access.engagement_scope import (
    reset_active_engagement,
    set_active_engagement,
)
from crmbuilder_v2.config import get_settings
from crmbuilder_v2.runtime.engagement_routing import resolve_active_engagement

_log = logging.getLogger("crmbuilder_v2.api.scope_middleware")


def resolve_engagement_identifier(header_value: str | None) -> str | None:
    """Resolve a header value (identifier *or* code) or the marker to ``ENG-NNN``.

    Returns the canonical engagement identifier, or ``None`` when nothing
    resolves (no header, no marker, or an unknown value). A ``None`` result
    leaves the request unscoped — the filter stays dormant (and, once
    enforcement is enabled at cutover, an unscoped scoped-query fails loud).
    """
    candidate = (header_value or "").strip() or resolve_active_engagement()
    if not candidate:
        return None
    candidate_upper = candidate.upper()
    try:
        engagements = engagement_repo.list_engagements_in_meta(include_deleted=False)
    except Exception:  # pragma: no cover - registry unavailable
        _log.warning("scope_middleware: engagement registry lookup failed")
        return None
    for e in engagements:
        if (
            e.engagement_identifier == candidate
            or e.engagement_code.upper() == candidate_upper
        ):
            return e.engagement_identifier
    _log.warning("scope_middleware: unknown engagement %r", candidate)
    return None


class EngagementScopeMiddleware:
    """Pure-ASGI middleware that sets the active engagement per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not get_settings().engagement_scoping_enabled:
            await self.app(scope, receive, send)
            return

        header_value = None
        for key, value in scope.get("headers", ()):
            if key == b"x-engagement":
                header_value = value.decode("latin-1")
                break

        identifier = resolve_engagement_identifier(header_value)
        token = set_active_engagement(identifier)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_active_engagement(token)
