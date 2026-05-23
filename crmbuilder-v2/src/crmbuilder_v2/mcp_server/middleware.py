"""Shared-secret header middleware for the FastMCP HTTP transport.

Validates the ``X-CRMBuilder-Secret`` header against the configured
value on every request. Missing or mismatched → 401 before route
dispatch. Constant-time comparison prevents timing oracles.

Registered only when the transport is ``streamable-http`` (see
:func:`crmbuilder_v2.mcp_server.server.build_server`); stdio bypasses
the middleware entirely.
"""

from __future__ import annotations

import hmac
import logging
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.types import ASGIApp

_log = logging.getLogger("crmbuilder_v2.mcp_server.middleware")

SECRET_HEADER = "X-CRMBuilder-Secret"


class SharedSecretMiddleware(BaseHTTPMiddleware):
    """Reject requests whose ``X-CRMBuilder-Secret`` does not match.

    :param app: Downstream ASGI app (set by Starlette during registration).
    :param expected_secret: The value the client must present. Must be
        non-empty — an empty configured secret would mean any client
        sending an empty header passes, defeating the purpose.
    :raises ValueError: If ``expected_secret`` is empty.
    """

    def __init__(self, app: ASGIApp, *, expected_secret: str) -> None:
        super().__init__(app)
        if not expected_secret:
            raise ValueError(
                "SharedSecretMiddleware requires a non-empty expected_secret"
            )
        self._expected = expected_secret

    async def dispatch(self, request: Request, call_next):
        provided = request.headers.get(SECRET_HEADER, "")
        if not hmac.compare_digest(provided, self._expected):
            _log.warning(
                "rejected request %s %s — missing or wrong %s header",
                request.method,
                request.url.path,
                SECRET_HEADER,
            )
            return JSONResponse(
                {"error": "unauthorized"},
                status_code=401,
            )
        return await call_next(request)
