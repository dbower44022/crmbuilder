"""PI-045 slice B — SharedSecretMiddleware unit tests.

Cover the header-validation middleware that gates the FastMCP HTTP
transport. Uses Starlette's ``TestClient`` against a minimal Starlette
app with the middleware applied, so the test exercises the actual
ASGI middleware machinery without standing up FastMCP itself.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from crmbuilder_v2.mcp_server.middleware import (
    SECRET_HEADER,
    SharedSecretMiddleware,
)

SECRET = "abc"


def _build_app(secret: str = SECRET) -> Starlette:
    async def ok(_request):
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", ok)])
    app.add_middleware(SharedSecretMiddleware, expected_secret=secret)
    return app


def test_correct_secret_passes() -> None:
    with TestClient(_build_app()) as client:
        resp = client.get("/", headers={SECRET_HEADER: SECRET})
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_missing_header_returns_401() -> None:
    with TestClient(_build_app()) as client:
        resp = client.get("/")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_wrong_secret_returns_401() -> None:
    with TestClient(_build_app()) as client:
        resp = client.get("/", headers={SECRET_HEADER: "nope"})
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_empty_secret_constructor_raises() -> None:
    async def _noop(_scope, _receive, _send):  # pragma: no cover
        pass

    with pytest.raises(ValueError, match="non-empty expected_secret"):
        SharedSecretMiddleware(_noop, expected_secret="")
