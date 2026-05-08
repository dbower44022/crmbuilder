"""UI test fixtures.

Forces the offscreen Qt platform plugin so headless test runs (CI,
plain shells with no display) don't hang on a missing X server. Set
before any pytest-qt fixture imports a QApplication. ``qapp`` and
``qtbot`` themselves come from pytest-qt and are picked up
automatically without re-export.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from collections.abc import Callable  # noqa: E402
from typing import Any

import httpx  # noqa: E402
import pytest  # noqa: E402
from crmbuilder_v2.ui.client import StorageClient  # noqa: E402
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle  # noqa: E402


@pytest.fixture
def lifecycle_stub(qapp):
    """A real ``ServerLifecycle`` aimed at an unreachable URL.

    Tests that don't exercise lifecycle behavior directly need a real
    lifecycle for type compatibility but never call ``start()`` on it.
    Pointing it at port 1 guarantees no accidental network call
    resolves.
    """
    return ServerLifecycle(base_url="http://127.0.0.1:1")


def make_mock_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    """Build an httpx.MockTransport from a single handler callable."""
    return httpx.MockTransport(handler)


def build_client(
    handler: Callable[[httpx.Request], httpx.Response],
    base_url: str = "http://test.invalid",
) -> StorageClient:
    """Construct a StorageClient backed by an httpx.MockTransport."""
    transport = make_mock_transport(handler)
    httpx_client = httpx.Client(base_url=base_url, transport=transport)
    return StorageClient(base_url=base_url, client=httpx_client)


@pytest.fixture
def client_stub(qapp) -> StorageClient:
    """A StorageClient that returns an empty decisions list.

    For tests that need to construct a panel/window but don't care
    about the data.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/decisions" and request.method == "GET":
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [
                {"code": "not_found", "message": "no route"}
            ]}
        )

    return build_client(handler)


@pytest.fixture
def make_handler() -> Callable[..., Callable[[httpx.Request], httpx.Response]]:
    """Factory: build an httpx mock handler from a route → response map.

    Each route is a (method, path) tuple. The handler 404s any
    unmatched route.
    """

    def factory(routes: dict[tuple[str, str], httpx.Response]):
        def handler(request: httpx.Request) -> httpx.Response:
            key = (request.method, request.url.path)
            if key in routes:
                return routes[key]
            return httpx.Response(
                404,
                json={
                    "data": None,
                    "meta": {},
                    "errors": [{"code": "not_found", "message": "unknown route"}],
                },
            )

        return handler

    return factory


def envelope_ok(data: Any) -> dict:
    return {"data": data, "meta": {}, "errors": None}


def envelope_err(errors: list[dict]) -> dict:
    return {"data": None, "meta": {}, "errors": errors}
