"""Tests for MCP per-engagement selection (PI-β follow-on A1).

The MCP server names the active engagement on its REST calls via the
``X-Engagement`` header — a config default
(``CRMBUILDER_V2_MCP_ENGAGEMENT``) plus a per-session ``select_engagement``
tool — mirroring the desktop's active-engagement context.
"""

from __future__ import annotations

import httpx
from crmbuilder_v2.config import Settings
from crmbuilder_v2.mcp_server import server as server_module
from crmbuilder_v2.mcp_server.tools import tool_definitions


def _tool(funcs, name):
    return next(f for f in funcs if f.name == name)


async def test_select_and_get_active_engagement_round_trip():
    """select_engagement sets the header; get_active_engagement reads it;
    an empty string clears it."""
    http = httpx.AsyncClient(base_url="http://testserver")
    try:
        funcs = tool_definitions(http)
        select = _tool(funcs, "select_engagement").func
        get_active = _tool(funcs, "get_active_engagement").func

        assert (await get_active())["active_engagement"] is None

        out = await select("ENG-002")
        assert out["active_engagement"] == "ENG-002"
        assert http.headers["X-Engagement"] == "ENG-002"
        assert (await get_active())["active_engagement"] == "ENG-002"

        out = await select("")
        assert out["active_engagement"] is None
        assert "X-Engagement" not in http.headers
        assert (await get_active())["active_engagement"] is None
    finally:
        await http.aclose()


def _headers_built_with(monkeypatch, **settings) -> dict | None:
    """The headers ``build_server`` gives the REST client it builds.

    ``mcp_token`` is pinned empty (REQ-631). Settings reads the working
    credentials file by absolute path, so a test that does not say otherwise
    loads the live tokens — and these two printed one into the failure message
    on every run, because they compared the whole header set and a bearer
    token had been added to it.
    """
    captured: dict = {}
    real_async_client = httpx.AsyncClient

    def _fake_async_client(*args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return real_async_client(base_url="http://testserver")

    settings.setdefault("mcp_token", "")
    monkeypatch.setattr(
        server_module, "get_settings", lambda: Settings(**settings)
    )
    monkeypatch.setattr(server_module.httpx, "AsyncClient", _fake_async_client)
    server_module.build_server()
    return captured["headers"]


def test_build_server_sends_configured_engagement(monkeypatch):
    """With CRMBUILDER_V2_MCP_ENGAGEMENT set, the default REST client the
    server builds carries the X-Engagement header.

    Asserts that header and not the whole set: what else the client sends is
    another test's business, and comparing the whole set is what broke this
    one when the connector began forwarding a bearer token.
    """
    headers = _headers_built_with(monkeypatch, mcp_engagement="CRMBUILDER")
    assert headers["X-Engagement"] == "CRMBUILDER"


def test_build_server_unscoped_when_engagement_unset(monkeypatch):
    """With the setting empty (default), no X-Engagement header is sent —
    the unscoped single-engagement-dogfood behavior is preserved."""
    headers = _headers_built_with(monkeypatch, mcp_engagement="")
    assert "X-Engagement" not in (headers or {})


def test_a_configured_token_is_forwarded_and_never_read_from_the_real_file(
    monkeypatch,
):
    """The header that broke the two above, asserted on purpose rather than
    met by accident — and with a value supplied here, so the live one is
    neither loaded nor printable (REQ-631)."""
    headers = _headers_built_with(
        monkeypatch, mcp_engagement="", mcp_token="not-a-real-token"
    )
    assert headers == {"Authorization": "Bearer not-a-real-token"}
