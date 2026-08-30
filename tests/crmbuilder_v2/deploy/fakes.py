"""Fake ``requests.Session`` for the provider clients — PI-419 tests.

Routes ``(METHOD, path)`` to canned responses and records every call so a test
can assert on payloads (e.g. that a DNS record was created ``proxied: false``).
"""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from typing import Any

import requests


class FakeResponse:
    def __init__(self, status: int, body: Any = None) -> None:
        self.status_code = status
        self._body = body
        self.content = b"" if body is None else _json.dumps(body).encode()

    def json(self) -> Any:
        if self._body is None:
            raise ValueError("no body")
        return self._body


Handler = Callable[[dict[str, Any] | None, dict[str, Any] | None], FakeResponse]


class FakeSession(requests.Session):
    """``routes[(METHOD, path)]`` is a ``FakeResponse`` or a handler ``(params, json) -> FakeResponse``."""

    def __init__(self, routes: dict[tuple[str, str], Any] | None = None) -> None:
        super().__init__()
        self.routes = dict(routes or {})
        self.calls: list[dict[str, Any]] = []

    def request(self, method, url, params=None, json=None, timeout=None, **kw):  # type: ignore[override]
        path = url.split("/v2", 1)[-1] if "/v2" in url else url.split("/client/v4", 1)[-1]
        self.calls.append({"method": method, "path": path, "params": params, "json": json})
        route = self.routes.get((method, path))
        if route is None:
            return FakeResponse(404, {"message": f"no route {method} {path}"})
        if callable(route):
            return route(params, json)
        return route
