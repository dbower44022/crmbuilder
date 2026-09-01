"""MCP HTTP transport host acceptance (REQ-548 / PI-446).

The MCP SDK enables DNS-rebinding protection for a loopback bind and, left
to its default, admits loopback ``Host`` names only. The server binds to
``127.0.0.1`` but is reached through the Cloudflare Tunnel as
``mcp.crmbuilder.ai``, so that default rejected every tunnelled request with
``421 Invalid Host header``. ``build_server`` now declares the accepted names
itself: the public URL's host plus the loopback forms, overridable through
``CRMBUILDER_V2_MCP_ALLOWED_HOSTS``.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from crmbuilder_v2.config import Settings
from crmbuilder_v2.mcp_server import server as server_mod
from mcp.server.transport_security import TransportSecuritySettings
from starlette.testclient import TestClient

PUBLIC_HOST = "mcp.crmbuilder.ai"
LOOPBACK = ["127.0.0.1:*", "localhost:*", "[::1]:*"]

_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


# --- Settings ---------------------------------------------------------------


def test_default_allowed_hosts_are_public_host_plus_loopback():
    settings = Settings(
        mcp_public_url="https://mcp.crmbuilder.ai", mcp_allowed_hosts=""
    )
    assert settings.mcp_allowed_host_list == [PUBLIC_HOST, *LOOPBACK]
    assert settings.mcp_allowed_origin_list == [
        "https://mcp.crmbuilder.ai",
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]


def test_configured_allowed_hosts_replace_the_default():
    settings = Settings(
        mcp_public_url="https://mcp.crmbuilder.ai",
        mcp_allowed_hosts=" a.example:* , b.example ,",
    )
    assert settings.mcp_allowed_host_list == ["a.example:*", "b.example"]
    assert settings.mcp_allowed_origin_list == [
        "https://a.example:*",
        "https://b.example",
    ]


def test_local_public_url_does_not_duplicate_loopback_entries():
    settings = Settings(mcp_public_url="http://localhost:8810", mcp_allowed_hosts="")
    assert settings.mcp_allowed_host_list == ["localhost:8810", *LOOPBACK]
    assert settings.mcp_allowed_origin_list[0] == "http://localhost:8810"


# --- build_server wiring ----------------------------------------------------


def _capture_fastmcp(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    class _FakeFastMCP:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            captured.update(kwargs)

        def run(self, *_a: Any, **_kw: Any) -> None:  # pragma: no cover
            pass

    monkeypatch.setattr(server_mod, "FastMCP", _FakeFastMCP)
    monkeypatch.setattr(server_mod, "register_tools", lambda *_a, **_kw: None)
    return captured


def test_build_server_passes_explicit_transport_security(
    monkeypatch: pytest.MonkeyPatch,
):
    captured = _capture_fastmcp(monkeypatch)
    monkeypatch.setattr(
        server_mod,
        "get_settings",
        lambda: Settings(
            mcp_public_url="https://mcp.crmbuilder.ai", mcp_allowed_hosts=""
        ),
    )
    server_mod.build_server()
    ts = captured["transport_security"]
    assert isinstance(ts, TransportSecuritySettings)
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == [PUBLIC_HOST, *LOOPBACK]
    assert "https://mcp.crmbuilder.ai" in ts.allowed_origins


def test_build_server_honours_configured_allowed_hosts(monkeypatch: pytest.MonkeyPatch):
    captured = _capture_fastmcp(monkeypatch)
    monkeypatch.setattr(
        server_mod,
        "get_settings",
        lambda: Settings(mcp_allowed_hosts="mcp.example.org,127.0.0.1:*"),
    )
    server_mod.build_server()
    assert captured["transport_security"].allowed_hosts == [
        "mcp.example.org",
        "127.0.0.1:*",
    ]


# --- end to end against the real transport ----------------------------------


@pytest.fixture
def http_app(monkeypatch: pytest.MonkeyPatch):
    """The real streamable-HTTP ASGI app, bound to loopback, auth off.

    ``TestClient`` as a context manager runs the app lifespan, which starts
    the StreamableHTTP session manager the transport needs.
    """
    monkeypatch.setattr(
        server_mod,
        "get_settings",
        lambda: Settings(
            mcp_public_url="https://mcp.crmbuilder.ai",
            mcp_allowed_hosts="",
            oauth_enabled=False,
        ),
    )
    unused = httpx.AsyncClient(base_url="http://unused.invalid")
    server = server_mod.build_server(http=unused, host="127.0.0.1", port=8810)
    with TestClient(server.streamable_http_app()) as client:
        yield client


def test_public_host_reaches_the_transport(http_app: TestClient):
    response = http_app.post(
        "/", json=_INITIALIZE, headers={**_MCP_HEADERS, "Host": PUBLIC_HOST}
    )
    assert response.status_code == 200, response.text


def test_loopback_host_still_reaches_the_transport(http_app: TestClient):
    response = http_app.post(
        "/", json=_INITIALIZE, headers={**_MCP_HEADERS, "Host": "127.0.0.1:8810"}
    )
    assert response.status_code == 200, response.text


def test_unlisted_host_is_still_rejected(http_app: TestClient):
    response = http_app.post(
        "/", json=_INITIALIZE, headers={**_MCP_HEADERS, "Host": "evil.example"}
    )
    assert response.status_code == 421
    assert "Invalid Host header" in response.text
