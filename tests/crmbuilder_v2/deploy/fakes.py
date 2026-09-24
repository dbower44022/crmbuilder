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


class FakeDnsLookup:
    """Stands in for :class:`crmbuilder_v2.deploy.dns_check.PublicDnsLookup` — PI-571.

    ``records[(name, type)]`` is what the domain's own name servers hold: a
    list of values; ``records[(name, "CNAME")]`` is an alias target instead.
    ``public[(name, type)]`` is what
    public resolvers return (defaults to the authoritative values).
    ``unreachable`` makes every authoritative query fail.
    """

    def __init__(self, *, zone="example.org", name_servers=("ana.ns.cloudflare.com", "bob.ns.cloudflare.com"),
                 records=None, public=None, negative_ttl=1800, ttl=300, unreachable=False):
        self.zone = zone
        self.name_servers = list(name_servers)
        self.records = dict(records or {})
        self.public_answers = dict(public or {})
        self.neg = negative_ttl
        self.ttl = ttl
        self.unreachable = unreachable

    def zone_and_name_servers(self, domain):
        if self.zone and (domain == self.zone or domain.endswith("." + self.zone)):
            return self.zone, list(self.name_servers)
        return None, []

    def authoritative(self, name_servers, name, rdtype):
        from crmbuilder_v2.deploy.dns_check import AuthAnswer

        if self.unreachable:
            return None
        value = self.records.get((name, rdtype))
        cname = self.records.get((name, "CNAME"))
        if cname:
            return AuthAnswer(cname=cname, ttl=self.ttl)
        if value is None:
            return AuthAnswer()
        return AuthAnswer(values=list(value), ttl=self.ttl)

    def public(self, name, rdtype="A"):
        if (name, rdtype) in self.public_answers:
            return set(self.public_answers[(name, rdtype)])
        return set(self.records.get((name, rdtype)) or [])

    def negative_ttl(self, name_servers, zone):
        return self.neg
