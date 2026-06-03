"""Per-request engagement-scope middleware (PI-123 Slice 2c, DEC-375 / D6).

Resolves the active engagement for each request and sets it on the
``engagement_scope`` ``ContextVar`` for the duration of the request, so the
row-level read filter / write stamp (Slice 2b) scope every query and insert to
that engagement.

Resolution (PI-β D5): the active engagement is named per request by the
``X-Engagement`` request header — its value may be either the engagement
**identifier** (``ENG-NNN``) or the user-facing **code** (e.g. ``CRMBUILDER``).
There is no marker fallback: a request that names no engagement and hits a
scoped table is unscoped (and fails loud once enforcement is on). The desktop
sends the header on every request; switching engagements is a client-side
context change.

A pure **ASGI** middleware (not ``BaseHTTPMiddleware``): ``BaseHTTPMiddleware``
runs the endpoint in a child task where a ``ContextVar`` set in ``dispatch`` does
not reliably reach the handler, whereas a pure ASGI middleware shares the
request's context, so the active engagement reaches the handler's DB session.

Gated by ``Settings.engagement_scoping_enabled`` — when off, the middleware is a
straight pass-through (one cheap check per request) and sets nothing, so the
current runtime is unchanged.
"""

from __future__ import annotations

import json
import logging

from crmbuilder_v2.access import engagement as engagement_repo
from crmbuilder_v2.access.engagement_scope import (
    reset_active_engagement,
    set_active_engagement,
)
from crmbuilder_v2.access.principal_scope import get_active_principal
from crmbuilder_v2.config import get_settings

_log = logging.getLogger("crmbuilder_v2.api.scope_middleware")


def resolve_engagement_identifier(header_value: str | None) -> str | None:
    """Resolve an ``X-Engagement`` header value (identifier *or* code) to ``ENG-NNN``.

    Returns the canonical engagement identifier, or ``None`` when nothing
    resolves (no header or an unknown value). A ``None`` result leaves the
    request unscoped — the filter stays dormant (and, when enforcement is on,
    an unscoped scoped-query fails loud).
    """
    candidate = (header_value or "").strip()
    if not candidate:
        return None
    candidate_upper = candidate.upper()
    try:
        # PI-123: resolve against the unified DB's engagements table (the
        # cutover registry the engagement_id FKs point at), not the meta DB.
        engagements = engagement_repo.list_engagements_unified(include_deleted=False)
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


async def _send_403(send, engagement: str | None) -> None:
    body = json.dumps(
        {
            "data": None,
            "meta": {},
            "errors": [
                {
                    "code": "engagement_forbidden",
                    "message": (
                        "The authenticated principal is not assigned to "
                        f"engagement {engagement or '<none>'}."
                    ),
                }
            ],
        }
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": body})


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

        # PI-γ (D5-final): when auth is on, validate the selected engagement
        # against the authenticated principal's assignments. The principal was
        # set by the outer PrincipalMiddleware. Only enforced when a principal
        # is present — a ``None`` principal here means a public/allowlisted path
        # the principal middleware let through unauthenticated, which carries no
        # engagement claim. An owner / all-engagements principal passes; an
        # unscoped request (identifier None) is allowed.
        if get_settings().principal_auth_enabled:
            principal = get_active_principal()
            if principal is not None and not principal.is_engagement_allowed(
                identifier
            ):
                await _send_403(send, identifier)
                return

        token = set_active_engagement(identifier)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_active_engagement(token)
