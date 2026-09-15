"""Tests for MCP per-engagement selection (PI-β follow-on A1).

The MCP server names the active engagement on its REST calls via the
``X-Engagement`` header — a config default
(``CRMBUILDER_V2_MCP_ENGAGEMENT``) plus a per-session ``select_engagement``
tool — mirroring the desktop's active-engagement context.
"""

from __future__ import annotations

import httpx
import pytest
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


def test_build_server_sends_configured_engagement(monkeypatch):
    """With CRMBUILDER_V2_MCP_ENGAGEMENT set, the default REST client the
    server builds carries the X-Engagement header."""
    captured = {}
    real_async_client = httpx.AsyncClient

    def _fake_async_client(*args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return real_async_client(base_url="http://testserver")

    monkeypatch.setattr(
        server_module, "get_settings", lambda: Settings(mcp_engagement="CRMBUILDER")
    )
    monkeypatch.setattr(server_module.httpx, "AsyncClient", _fake_async_client)
    server_module.build_server()
    assert captured["headers"] == {"X-Engagement": "CRMBUILDER"}


def test_build_server_unscoped_when_engagement_unset(monkeypatch):
    """With the setting empty (default), no X-Engagement header is sent —
    the unscoped single-engagement-dogfood behavior is preserved."""
    captured = {}
    real_async_client = httpx.AsyncClient

    def _fake_async_client(*args, **kwargs):
        captured["headers"] = kwargs.get("headers")
        return real_async_client(base_url="http://testserver")

    monkeypatch.setattr(
        server_module, "get_settings", lambda: Settings(mcp_engagement="")
    )
    monkeypatch.setattr(server_module.httpx, "AsyncClient", _fake_async_client)
    server_module.build_server()
    assert captured["headers"] is None
