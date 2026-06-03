"""Per-request principal-resolution middleware (PI-γ — PRJ-019 / PI-127).

The ``resolve_principal`` chokepoint + bearer-token middleware. Mirrors
:mod:`crmbuilder_v2.api.scope_middleware`: a pure-ASGI middleware that resolves
the authenticated principal for each request and sets it on the
``principal_scope`` ``ContextVar`` for the request's duration.

**Outermost middleware.** Added to the app *after* the engagement-scope
middleware so it wraps it (Starlette applies the last-added middleware first),
ensuring the principal is set before engagement resolution — so engagement
selection can be validated against the principal's assignments (slice 3 /
D5-final).

**Auth gated by ``Settings.principal_auth_enabled``:**

* **off** (default, single-operator localhost): every request resolves
  :data:`DEFAULT_OWNER` — a synthetic owner allowed on every engagement. Zero
  tokens, behavior unchanged.
* **on** (deployed): a valid ``Authorization: Bearer <token>`` is required. A
  missing/invalid/expired/revoked token yields a ``401`` envelope, except for
  the unauthenticated allowlist (root, health, docs, OpenAPI schema).
"""

from __future__ import annotations

import json
import logging

from crmbuilder_v2.access.principal_scope import (
    DEFAULT_OWNER,
    Principal,
    reset_active_principal,
    set_active_principal,
)
from crmbuilder_v2.config import get_settings

_log = logging.getLogger("crmbuilder_v2.api.principal_middleware")

# Paths reachable without a bearer token even when auth is on. Health and the
# API metadata/docs surface must stay open so liveness probes and the schema
# explorer work before a token is provisioned.
_PUBLIC_PATH_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")


def _is_public_path(path: str) -> bool:
    if path == "/":
        return True
    return any(path == p or path.startswith(p) for p in _PUBLIC_PATH_PREFIXES)


def _bearer_token(headers) -> str | None:
    """Extract the bearer token from the ASGI ``Authorization`` header, if any."""
    for key, value in headers:
        if key == b"authorization":
            raw = value.decode("latin-1").strip()
            if raw.lower().startswith("bearer "):
                return raw[7:].strip()
            return None
    return None


def resolve_principal(token: str | None) -> Principal | None:
    """Resolve a bearer-token plaintext to a :class:`Principal`.

    The single auth chokepoint (a future OIDC/SSO issuer becomes a second
    implementation feeding the same ``Principal``). When auth is disabled,
    returns :data:`DEFAULT_OWNER` regardless of ``token``. When enabled,
    validates the token against the DB (active, unexpired, unrevoked, active
    principal); returns ``None`` on any miss.
    """
    if not get_settings().principal_auth_enabled:
        return DEFAULT_OWNER
    if not token:
        return None
    # Imported lazily to keep the access layer out of the import path until a
    # request actually needs token validation.
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.principal import validate_token

    try:
        with session_scope() as s:
            return validate_token(s, token)
    except Exception:  # pragma: no cover - DB unavailable
        _log.warning("principal_middleware: token validation failed", exc_info=True)
        return None


async def _send_401(send) -> None:
    body = json.dumps(
        {
            "data": None,
            "meta": {},
            "errors": [
                {
                    "code": "unauthenticated",
                    "message": (
                        "A valid bearer token is required "
                        "(Authorization: Bearer <token>)."
                    ),
                }
            ],
        }
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class PrincipalMiddleware:
    """Pure-ASGI middleware that resolves + sets the active principal per request."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        token = _bearer_token(scope.get("headers", ()))
        principal = resolve_principal(token)

        if (
            settings.principal_auth_enabled
            and principal is None
            and not _is_public_path(scope.get("path", ""))
        ):
            await _send_401(send)
            return

        ctx_token = set_active_principal(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_active_principal(ctx_token)
