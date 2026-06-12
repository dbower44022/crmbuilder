"""UI test fixtures.

Forces the offscreen Qt platform plugin so headless test runs (CI,
plain shells with no display) don't hang on a missing X server. Set
before any pytest-qt fixture imports a QApplication. ``qapp`` and
``qtbot`` themselves come from pytest-qt and are picked up
automatically without re-export. (The repo-root ``tests/conftest.py``
also pins the platform, so every collection order is covered.)

**Widget-cleanup conventions (PI-159 §5.3).** Every UI test in this
subtree follows three ownership rules:

1. every top-level widget goes through ``qtbot.addWidget`` — close +
   ``deleteLater`` are handled centrally; never scatter manual
   ``widget.close()`` calls in tests;
2. ``qtbot.addWidget`` holds only a **weakref** — registration is
   cleanup, not ownership. Tests and helpers must keep a strong
   reference to the widget-tree root for the test's duration;
3. models and proxies are parented to their view/panel; no parentless
   QObject may outlive the function that created it unless the test
   holds it.

The ``pytest_runtest_teardown`` hook below is the deterministic
counterpart: it drains ``DeferredDelete`` events inside each test's own
teardown, so destruction never drifts across test boundaries into a
later test's event processing (the SIGSEGV window PI-159 closes).
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
from PySide6.QtCore import QEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item):
    """Drain deferred deletions inside the test that posted them.

    pytest-qt's teardown closes then ``deleteLater()``s every registered
    widget; ``DeferredDelete`` delivery rules can defer the actual
    destruction into a *later* test's event processing, where a paint on
    a half-destructed widget segfaults. Runs ``trylast`` so it executes
    after fixture finalization (where pytest-qt posts the deletions); the
    bounded double pass settles deletions that themselves post more.
    """
    app = QApplication.instance()
    if app is None:
        return
    for _ in range(2):
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()


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
    """A StorageClient that returns empty lists for decisions/sessions/risks.

    For tests that need to construct a panel/window but don't care
    about the data.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path in (
            "/decisions",
            "/sessions",
            "/risks",
            "/topics",
            "/planning-items",
            "/references",
            "/charter/versions",
            "/status/versions",
            "/engagements",
        ):
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        if request.method == "GET" and request.url.path.startswith(
            "/references/touching/"
        ):
            return httpx.Response(
                200,
                json={
                    "data": {"as_source": [], "as_target": []},
                    "meta": {},
                    "errors": None,
                },
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
